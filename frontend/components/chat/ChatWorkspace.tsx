"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { useRouter } from "next/navigation";

import { deleteSession, getSession, listSessions, submitChatMessage } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { useChatStore } from "@/store/chatStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { AppSidebar } from "@/components/chat/AppSidebar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import type { SessionResponse } from "@/lib/types";

type Props = {
  sessionId: string;
};

export function ChatWorkspace({ sessionId }: Props) {
  const router = useRouter();
  const [streamId, setStreamId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loadingSession, setLoadingSession] = useState(true);
  const [isResizingWorkspace, setIsResizingWorkspace] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const {
    sessionId: currentSessionId,
    messages,
    streamState,
    activeToolStatus,
    generationPreviews,
    errorMessage,
    setSessionId,
    setMessages,
    addUserMessage,
    beginAssistantMessage,
    appendAssistantText,
    finalizeAssistantMessage,
    setStreamState,
    setToolStatus,
    upsertGenerationPreview,
    setErrorMessage,
    resetConversation,
  } = useChatStore();
  const {
    sidebarCollapsed,
    toggleSidebar,
    activeTab,
    setActiveTab,
    workspaceCollapsed,
    workspaceWidthRatio,
    toggleWorkspace,
    setWorkspaceWidthRatio,
  } = useWorkspaceStore();

  const refreshSessions = useCallback(async () => {
    const sessionItems = await listSessions();
    return sessionItems;
  }, []);

  useEffect(() => {
    let active = true;

    async function loadSessionData() {
      setLoadingSession(true);
      resetConversation();
      setSessionId(sessionId);
      setErrorMessage(null);

      try {
        const [sessionDetail, sessionItems] = await Promise.all([
          getSession(sessionId),
          refreshSessions(),
        ]);
        if (!active) {
          return;
        }
        setMessages(sessionDetail.messages ?? []);
        setSessions(sessionItems);
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "加载会话失败");
      } finally {
        if (active) {
          setLoadingSession(false);
        }
      }
    }

    loadSessionData();
    return () => {
      active = false;
    };
  }, [refreshSessions, resetConversation, sessionId, setErrorMessage, setMessages, setSessionId]);

  const sessionTitle =
    sessions.find((session) => session.id === sessionId)?.title?.trim() || "Unnamed Chat";

  useEffect(() => {
    if (!isResizingWorkspace) {
      return;
    }

    function handlePointerMove(event: PointerEvent) {
      if (!containerRef.current) {
        return;
      }

      const rect = containerRef.current.getBoundingClientRect();
      const nextWidth = rect.right - event.clientX;
      const nextRatio = nextWidth / rect.width;
      setWorkspaceWidthRatio(nextRatio);
    }

    function handlePointerUp() {
      setIsResizingWorkspace(false);
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isResizingWorkspace, setWorkspaceWidthRatio]);

  useSSE({
    sessionId,
    streamId,
    enabled: Boolean(streamId),
    onTextDelta: (content) => {
      setStreamState("streaming");
      appendAssistantText(content);
    },
    onToolStart: (_tool, summary) => {
      setToolStatus({ tool: _tool, summary });
    },
    onToolEnd: (_tool, summary) => {
      setToolStatus({ tool: _tool, summary });
    },
    onGenerationStart: (taskId, runId) => {
      upsertGenerationPreview({ taskId, imageUrl: "", runId });
    },
    onGenerationDone: (taskId, imageUrl, runId) => {
      upsertGenerationPreview({ taskId, imageUrl, runId });
      setActiveTab("images");
    },
    onError: (_code, message) => {
      setStreamState("error");
      setErrorMessage(message);
    },
    onDone: () => {
      setStreamState("idle");
      finalizeAssistantMessage();
      setStreamId(null);
    },
  });

  async function handleSubmit(content: string) {
    setErrorMessage(null);
    setToolStatus(null);
    setStreamState("submitting");
    addUserMessage(content);
    beginAssistantMessage();

    try {
      const response = await submitChatMessage(sessionId, content);
      setStreamId(response.stream_id);
      setStreamState("streaming");
    } catch (error) {
      setStreamState("error");
      finalizeAssistantMessage();
      setErrorMessage(error instanceof Error ? error.message : "发送消息失败");
    }
  }

  const handleWorkspaceResizeStart = useCallback(() => {
    setIsResizingWorkspace(true);
  }, []);

  const handleDeleteSession = useCallback(
    async (targetSessionId: string) => {
      try {
        await deleteSession(targetSessionId);
        const nextSessions = await refreshSessions();
        setSessions(nextSessions);

        if (targetSessionId !== sessionId) {
          return;
        }

        const fallbackSession = nextSessions.find((session) => session.id !== targetSessionId)?.id ?? "new";
        router.replace(`/chat/${fallbackSession}`);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "删除会话失败");
      }
    },
    [refreshSessions, router, sessionId, setErrorMessage],
  );

  const workspacePanel = useMemo(() => {
    if (workspaceCollapsed) {
      return (
        <aside className="hidden w-14 shrink-0 border-l border-black/6 bg-white xl:flex xl:flex-col">
          <div className="flex flex-1 flex-col items-center gap-3 px-2 py-4">
            <button
              type="button"
              onClick={toggleWorkspace}
              className="inline-flex size-9 items-center justify-center rounded-md border border-black/8 bg-white text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
              aria-label="展开工作区"
            >
              <PanelRightOpen className="size-4" />
            </button>
            <div className="writing-mode-vertical text-xs text-muted-foreground [writing-mode:vertical-rl] [text-orientation:mixed]">
              工作区
            </div>
          </div>
        </aside>
      );
    }

    return (
      <>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="调整工作区宽度"
          onPointerDown={handleWorkspaceResizeStart}
          className={`hidden w-1 shrink-0 cursor-col-resize bg-transparent transition-colors xl:block ${
            isResizingWorkspace ? "bg-black/8" : "hover:bg-black/[0.05]"
          }`}
        />
        <aside
          className="hidden shrink-0 border-l border-black/6 bg-white xl:flex xl:flex-col"
          style={{ width: `${workspaceWidthRatio * 100}%` }}
        >
          <div className="flex h-[72px] items-center justify-between gap-3 border-b border-black/6 px-4 py-4">
            <div>
              <div className="text-sm font-semibold">工作区</div>
              <div className="text-xs text-muted-foreground">E-1 先落三栏骨架和纯文字对话</div>
            </div>
            <button
              type="button"
              onClick={toggleWorkspace}
              className="inline-flex size-8 items-center justify-center rounded-md border border-black/8 bg-white text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
              aria-label="折叠工作区"
            >
              <PanelRightClose className="size-4" />
            </button>
          </div>

          <div className="flex gap-2 border-b border-black/6 px-4 py-3">
            <button
              type="button"
              onClick={() => setActiveTab("prompt")}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeTab === "prompt" ? "bg-black text-white" : "border border-black/8 bg-white"
              }`}
            >
              提示词
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("images")}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeTab === "images" ? "bg-black text-white" : "border border-black/8 bg-white"
              }`}
            >
              生成图片
            </button>
          </div>

          <div className="flex-1 px-4 py-4">
            {activeTab === "prompt" ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-black/8 bg-white p-4">
                  <div className="text-sm font-medium">Prompt 工作区</div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    E-1 只提供三栏结构，占位等待 E-2/E-3 接入提示词、参考图和参数滑块。
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {generationPreviews.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-black/8 bg-white p-4 text-sm text-muted-foreground">
                    生成结果会在这里出现
                  </div>
                ) : (
                  generationPreviews
                    .filter((item) => item.imageUrl)
                    .map((item) => (
                      <div key={item.taskId} className="overflow-hidden rounded-xl border border-black/8 bg-white">
                        {/* Generated images may come from arbitrary remote providers; keep raw img in E-1. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={item.imageUrl} alt="生成结果" className="h-44 w-full object-cover" />
                        <div className="border-t border-black/6 px-3 py-2 text-xs text-muted-foreground">
                          {item.taskId}
                        </div>
                      </div>
                    ))
                )}
              </div>
            )}
          </div>
        </aside>
      </>
    );
  }, [
    activeTab,
    generationPreviews,
    handleWorkspaceResizeStart,
    isResizingWorkspace,
    setActiveTab,
    toggleWorkspace,
    workspaceCollapsed,
    workspaceWidthRatio,
  ]);

  return (
    <div
      ref={containerRef}
      className={`flex min-h-screen items-stretch flex-1 overflow-hidden ${isResizingWorkspace ? "select-none" : ""}`}
    >
      <AppSidebar
        collapsed={sidebarCollapsed}
        sessionId={sessionId}
        sessions={sessions}
        onToggle={toggleSidebar}
        onDeleteSession={handleDeleteSession}
      />
      <ChatPanel
        sessionTitle={sessionTitle}
        messages={loadingSession && currentSessionId !== sessionId ? [] : messages}
        activeToolStatus={activeToolStatus}
        generationPreviews={generationPreviews.filter((item) => item.imageUrl)}
        streamState={streamState}
        errorMessage={errorMessage}
        onSubmit={handleSubmit}
      />
      {workspacePanel}
    </div>
  );
}
