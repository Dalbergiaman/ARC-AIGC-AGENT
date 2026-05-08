"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { deleteSession, getSession, listSessions, submitChatMessage } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { useChatStore } from "@/store/chatStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { AppSidebar } from "@/components/chat/AppSidebar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import type { SessionResponse } from "@/lib/types";

type Props = {
  sessionId: string;
};

function extractReply(raw: string): string | null {
  let text = raw.trim();
  if (text.startsWith("```")) {
    const lines = text.split("\n");
    text = lines.slice(1, lines.length - 1).join("\n").trim();
  }
  try {
    const data = JSON.parse(text) as Record<string, unknown>;
    if (typeof data.reply === "string" && data.reply.trim()) {
      return data.reply.trim();
    }
  } catch {
    // not valid JSON — keep original streamed content
  }
  return null;
}

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
    currentAssistantText,
    setSessionId,
    setMessages,
    addUserMessage,
    beginAssistantMessage,
    appendAssistantText,
    replaceAssistantText,
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
    getReferenceImages,
    promptDraft,
    negativePromptDraft,
    updateReferenceImage,
  } = useWorkspaceStore();

  const referenceImages = getReferenceImages(sessionId);

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
      const reply = extractReply(currentAssistantText);
      if (reply) {
        replaceAssistantText(reply);
      }
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

    // Build payload — only include images not yet sent
    const readyImages = referenceImages.filter((img) => !img.uploading && !img.error && img.url && !img.sent);
    const payload = {
      content,
      ...(readyImages.length > 0 && {
        reference_images: readyImages.map((img) => ({
          file_id: img.fileId,
          url: img.url,
          intent: img.intent,
          note: img.note ?? "",
        })),
      }),
      ...((promptDraft || negativePromptDraft) && {
        workspace: {
          prompt: promptDraft,
          negative_prompt: negativePromptDraft,
        },
      }),
    };

    try {
      const response = await submitChatMessage(sessionId, payload);
      // Mark submitted images as sent (keep them visible, don't clear)
      readyImages.forEach((img) => updateReferenceImage(sessionId, img.fileId, { sent: true }));
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

  const workspacePanel = (
    <WorkspacePanel
      sessionId={sessionId}
      activeTab={activeTab}
      collapsed={workspaceCollapsed}
      widthRatio={workspaceWidthRatio}
      generationPreviews={generationPreviews.filter((item) => item.imageUrl)}
      isResizing={isResizingWorkspace}
      onTabChange={setActiveTab}
      onToggle={toggleWorkspace}
      onResizeStart={handleWorkspaceResizeStart}
    />
  );

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
