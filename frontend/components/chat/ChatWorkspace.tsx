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
  const [workspaceHydrated, setWorkspaceHydrated] = useState(false);
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
    setGenerationPreviews,
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
    setWorkspaceCollapsed,
    setWorkspaceWidthRatio,
    getControlImage,
    getAnnotatedImage,
    getReferenceImages,
    getPromptDraft,
    promptDraft,
    setSessionPromptDraft,
    setSessionReferenceImages,
    updateControlImage,
    updateAnnotatedImage,
    updateReferenceImage,
  } = useWorkspaceStore();

  const controlImage = getControlImage(sessionId);
  const annotatedImage = getAnnotatedImage(sessionId);
  const referenceImages = getReferenceImages(sessionId);

  useEffect(() => {
    let active = true;

    Promise.resolve(useWorkspaceStore.persist.rehydrate()).then(() => {
      if (active) {
        setWorkspaceHydrated(true);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  const refreshSessions = useCallback(async () => {
    const sessionItems = await listSessions();
    return sessionItems;
  }, []);

  useEffect(() => {
    let active = true;

    async function loadSessionData() {
      if (!workspaceHydrated) {
        return;
      }

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
        if (sessionDetail.workspace_state) {
          setSessionPromptDraft(sessionId, {
            keywords: sessionDetail.workspace_state.keywords ?? {},
            llm_description: sessionDetail.workspace_state.llm_description ?? "",
            custom_description: sessionDetail.workspace_state.custom_description ?? "",
            negative_prompt: sessionDetail.workspace_state.negative_prompt ?? "",
            prompt_template: sessionDetail.workspace_state.prompt_template ?? null,
          });
        } else {
          setSessionPromptDraft(sessionId, getPromptDraft(sessionId));
        }
        setSessionReferenceImages(
          sessionId,
          (sessionDetail.reference_images ?? []).map((item) => ({
            fileId: item.file_id,
            url: item.url,
            intent: item.analysis?.reference_intent ?? "composition",
            note: typeof item.analysis?.intent_note === "string" ? item.analysis.intent_note : "",
            sent: Boolean(item.analysis?.sent),
            analysis: item.analysis ?? null,
          })),
        );
        setGenerationPreviews(
          (() => {
            const msgs = sessionDetail.messages ?? [];
            const previews = (sessionDetail.generation_tasks ?? []).map((item) => ({
              taskId: item.task_id ?? item.id,
              imageUrl: item.image_url ?? "",
              runId: undefined,
              score: item.score ?? null,
              provider: item.provider ?? null,
              status: item.status,
              prompt: item.prompt,
              negativePrompt: item.negative_prompt ?? null,
              rawResponse: item.raw_response ?? null,
              created_at: item.created_at,
            }));

            const assistantMsgs = msgs.filter((m) => m.role === "assistant" && m.created_at);
            return previews.map((preview) => {
              if (!preview.created_at || assistantMsgs.length === 0) return preview;
              const previewTime = new Date(preview.created_at).getTime();
              let bestMatch: (typeof assistantMsgs)[0] | null = null;
              let bestDiff = Infinity;
              for (const msg of assistantMsgs) {
                const diff = previewTime - new Date(msg.created_at!).getTime();
                if (diff >= 0 && diff < bestDiff) {
                  bestDiff = diff;
                  bestMatch = msg;
                }
              }
              if (!bestMatch) bestMatch = assistantMsgs[assistantMsgs.length - 1];
              return { ...preview, assistantMessageId: bestMatch.id };
            });
          })(),
        );
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
  }, [
    getPromptDraft,
    refreshSessions,
    resetConversation,
    sessionId,
    setErrorMessage,
    setMessages,
    setSessionId,
    setSessionPromptDraft,
    setSessionReferenceImages,
    setGenerationPreviews,
    workspaceHydrated,
  ]);

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
      upsertGenerationPreview({ taskId, imageUrl: "", runId, status: "running" });
    },
    onGenerationDone: (payload) => {
      upsertGenerationPreview({
        taskId: payload.taskId,
        imageUrl: payload.imageUrl,
        runId: payload.runId,
        status: payload.status ?? "done",
        provider: payload.provider,
        score: payload.score,
        prompt: payload.prompt,
        negativePrompt: payload.negativePrompt,
        rawResponse: payload.rawResponse,
      });
      setActiveTab("images");
    },
    onPromptUpdate: (keywords, llmDescription, customDescription, negativePrompt, promptTemplate) => {
      setSessionPromptDraft(sessionId, {
        keywords,
        llm_description: llmDescription,
        custom_description: customDescription,
        negative_prompt: negativePrompt,
        prompt_template: promptTemplate ?? useWorkspaceStore.getState().promptTemplateBySession[sessionId] ?? null,
      });
      setActiveTab("prompt");
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
      // Title generation runs in the background on the server; refresh after a delay.
      setTimeout(() => {
        refreshSessions().then(setSessions).catch(() => undefined);
      }, 3000);
    },
  });

  async function handleSubmit(content: string) {
    setErrorMessage(null);
    setToolStatus(null);
    setStreamState("submitting");
    if (messages.length === 0 && workspaceCollapsed) {
      setWorkspaceCollapsed(false);
    }
    addUserMessage(content);
    beginAssistantMessage();

    // Build payload — only include images not yet sent
    const readyControlImage =
      controlImage && !controlImage.uploading && !controlImage.error && controlImage.url
        ? controlImage
        : null;
    const readyAnnotatedImage =
      annotatedImage && !annotatedImage.uploading && !annotatedImage.error && annotatedImage.url
        ? annotatedImage
        : null;
    const readyImages = referenceImages.filter((img) => !img.uploading && !img.error && img.url && !img.sent);
    const payload = {
      content,
      ...(readyControlImage && {
        control_image: {
          file_id: readyControlImage.fileId,
          url: readyControlImage.url,
          note: readyControlImage.note ?? "",
        },
      }),
      ...(readyAnnotatedImage && {
        annotated_image: {
          file_id: readyAnnotatedImage.fileId,
          url: readyAnnotatedImage.url,
          note: readyAnnotatedImage.note ?? "",
        },
      }),
      ...(readyImages.length > 0 && {
        reference_images: readyImages.map((img) => ({
          file_id: img.fileId,
          url: img.url,
          intent: img.intent,
          note: img.note ?? "",
        })),
      }),
      workspace: {
        keywords: promptDraft.keywords,
        llm_description: promptDraft.llm_description,
        custom_description: promptDraft.custom_description,
        negative_prompt: promptDraft.negative_prompt,
        prompt_template: promptDraft.prompt_template,
      },
    };

    try {
      const response = await submitChatMessage(sessionId, payload);
      if (readyControlImage) {
        updateControlImage(sessionId, { sent: true });
      }
      if (readyAnnotatedImage) {
        updateAnnotatedImage(sessionId, { sent: true });
      }
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
      generationPreviews={generationPreviews}
      isResizing={isResizingWorkspace}
      onTabChange={setActiveTab}
      onToggle={toggleWorkspace}
      onResizeStart={handleWorkspaceResizeStart}
    />
  );

  const visibleMessages = loadingSession && currentSessionId !== sessionId ? [] : messages;
  const isWelcome =
    !loadingSession &&
    visibleMessages.length === 0 &&
    streamState === "idle" &&
    !errorMessage;

  return (
    <div
      ref={containerRef}
      className={`fixed inset-0 flex min-h-0 items-stretch overflow-hidden bg-white ${isResizingWorkspace ? "select-none" : ""}`}
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
        messages={visibleMessages}
        activeToolStatus={activeToolStatus}
        generationPreviews={generationPreviews.filter((item) => item.imageUrl)}
        streamState={streamState}
        errorMessage={errorMessage}
        isWelcome={isWelcome}
        onSubmit={handleSubmit}
      />
      {isWelcome ? null : workspacePanel}
    </div>
  );
}
