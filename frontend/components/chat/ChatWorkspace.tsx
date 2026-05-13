"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { deleteSession, getSession, listSessions, submitChatMessage } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import { useChatStore } from "@/store/chatStore";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { AppSidebar } from "@/components/chat/AppSidebar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { RagCandidatesPopup } from "@/components/chat/RagCandidatesPopup";
import { WorkspacePanel } from "@/components/workspace/WorkspacePanel";
import type { ReferenceIntent, SessionResponse, SubmitMessagePayload } from "@/lib/types";

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

const INTENT_LABELS: Record<ReferenceIntent, string> = {
  composition: "构图",
  color: "色彩",
  style: "建筑样式",
  material: "材质",
  lighting: "光线",
  surroundings: "环境",
  other: "其他",
};

export function ChatWorkspace({ sessionId }: Props) {
  const router = useRouter();
  const [streamId, setStreamId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loadingSession, setLoadingSession] = useState(true);
  const [isResizingWorkspace, setIsResizingWorkspace] = useState(false);
  const [workspaceHydrated, setWorkspaceHydrated] = useState(false);
  const [ragPopup, setRagPopup] = useState<{
    candidates: { image_id: string; image_url: string; caption?: string; score?: number }[];
    timeout: number;
    runId: string;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const {
    sessionId: currentSessionId,
    messages,
    streamState,
    activeToolStatus,
    agentStatusesByMessage,
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
    appendAgentStatus,
    finishRunningAgentStatuses,
    upsertGenerationPreview,
    setGenerationPreviews,
    failRunningPreviews,
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
    setControlImage,
    setAnnotatedImage,
    getReferenceImages,
    getPromptDraft,
    promptDraft,
    setSessionPromptDraft,
    setSessionReferenceImages,
    updateControlImage,
    updateReferenceImage,
    setRagImage,
  } = useWorkspaceStore();

  const controlImage = getControlImage(sessionId);
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
          const ws = sessionDetail.workspace_state;
          // Support both new layered format {prompt_draft, ...} and legacy flat PromptDraft
          const promptDraft = ws.prompt_draft ?? (ws as unknown as import("@/lib/types").PromptDraft);
          setSessionPromptDraft(sessionId, {
            keywords: promptDraft?.keywords ?? {},
            llm_description: promptDraft?.llm_description ?? "",
            custom_description: promptDraft?.custom_description ?? "",
            negative_prompt: promptDraft?.negative_prompt ?? "",
            prompt_template: promptDraft?.prompt_template ?? null,
          });
          if (ws.rag_image) {
            setRagImage(sessionId, ws.rag_image);
          }
          if (ws.control_image) {
            setControlImage(sessionId, {
              fileId: ws.control_image.file_id,
              url: ws.control_image.url,
              note: ws.control_image.note ?? "",
            });
          }
          if (ws.annotated_image) {
            setAnnotatedImage(sessionId, {
              fileId: ws.annotated_image.file_id,
              url: ws.annotated_image.url,
              note: ws.annotated_image.note ?? "",
            });
          }
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
              // Treat any persisted "running" without an image as failed — the task
              // never completed and will never resume after a page reload.
              status: (!item.image_url && item.status === "running") ? "failed" : item.status,
              prompt: item.prompt,
              negativePrompt: item.negative_prompt ?? null,
              rawResponse: item.raw_response ?? null,
              storedInLibrary: item.stored_in_library ?? false,
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
    setControlImage,
    setAnnotatedImage,
    setSessionPromptDraft,
    setSessionReferenceImages,
    setGenerationPreviews,
    setRagImage,
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
    onAgentReply: (content) => {
      replaceAssistantText(content);
    },
    onAgentStatus: (stage, status, summary) => {
      appendAgentStatus({ stage, status, summary });
      setToolStatus({ tool: stage, summary });
    },
    onToolStart: (_tool, summary) => {
      setToolStatus({ tool: _tool, summary });
      appendAgentStatus({ stage: _tool, status: "running", summary });
    },
    onToolEnd: (_tool, summary) => {
      setToolStatus({ tool: _tool, summary });
      appendAgentStatus({ stage: _tool, status: "done", summary });
    },
    onGenerationStart: (taskId, runId) => {
      appendAgentStatus({ stage: "generate_image", status: "running", summary: "图像生成任务已提交，正在等待结果..." });
      upsertGenerationPreview({ taskId, imageUrl: "", runId, status: "running" });
    },
    onGenerationDone: (payload) => {
      appendAgentStatus({ stage: "generate_image", status: "done", summary: "图像生成完成，正在展示结果" });
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
    onGenerationError: (taskId) => {
      appendAgentStatus({ stage: "generate_image", status: "error", summary: "图像生成失败" });
      upsertGenerationPreview({ taskId, status: "failed" });
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
    onRagCandidates: (candidates, timeout) => {
      if (streamId) {
        setRagPopup({ candidates, timeout, runId: streamId });
      }
    },
    onRagImageUpdate: (ragImage) => {
      setRagImage(sessionId, ragImage);
      setRagPopup(null);
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
      finishRunningAgentStatuses();
      failRunningPreviews();
      setStreamState("idle");
      finalizeAssistantMessage();
      setStreamId(null);
      // Title generation runs in the background on the server; refresh after a delay.
      setTimeout(() => {
        refreshSessions().then(setSessions).catch(() => undefined);
      }, 3000);
    },
  });

  async function submitPayload(content: string, payload: SubmitMessagePayload, afterSubmitted?: () => void) {
    setErrorMessage(null);
    setToolStatus(null);
    setStreamState("submitting");
    if (messages.length === 0 && workspaceCollapsed) {
      setWorkspaceCollapsed(false);
    }
    addUserMessage(content);
    beginAssistantMessage();

    try {
      const response = await submitChatMessage(sessionId, payload);
      afterSubmitted?.();
      setStreamId(response.stream_id);
      setStreamState("streaming");
    } catch (error) {
      setStreamState("error");
      finalizeAssistantMessage();
      setErrorMessage(error instanceof Error ? error.message : "发送消息失败");
    }
  }

  function workspacePayload(): NonNullable<SubmitMessagePayload["workspace"]> {
    return {
      keywords: promptDraft.keywords,
      llm_description: promptDraft.llm_description,
      custom_description: promptDraft.custom_description,
      negative_prompt: promptDraft.negative_prompt,
      prompt_template: promptDraft.prompt_template,
    };
  }

  async function handleSubmit(content: string) {
    await submitPayload(content, {
      content,
      workspace: workspacePayload(),
    });
  }

  async function handleSendControlImage() {
    if (!controlImage || controlImage.uploading || controlImage.error || !controlImage.url || controlImage.sent) {
      return;
    }
    const content = controlImage.note?.trim()
      ? `我发送了一张图生图结构底图。底图说明：${controlImage.note.trim()}。请分析这张底图后续可以怎样优化。`
      : "我发送了一张图生图结构底图，请分析这张底图后续可以怎样优化。";
    await submitPayload(
      content,
      {
        content,
        control_image: {
          file_id: controlImage.fileId,
          url: controlImage.url,
          note: controlImage.note ?? "",
        },
        workspace: workspacePayload(),
      },
      () => updateControlImage(sessionId, { sent: true }),
    );
  }

  async function handleSendReferenceImage(fileId: string) {
    const image = referenceImages.find((img) => img.fileId === fileId);
    if (!image || image.uploading || image.error || !image.url || image.sent) {
      return;
    }
    const intentLabel = INTENT_LABELS[image.intent];
    const note = image.note?.trim();
    const content = note
      ? `我发送了一张参考图，主要参考方向是：${intentLabel}。补充说明：${note}。请分析如何用于后续效果图。`
      : `我发送了一张参考图，主要参考方向是：${intentLabel}。请分析如何用于后续效果图。`;
    await submitPayload(
      content,
      {
        content,
        reference_images: [{
          file_id: image.fileId,
          url: image.url,
          intent: image.intent,
          note: image.note ?? "",
        }],
        workspace: workspacePayload(),
      },
      () => updateReferenceImage(sessionId, image.fileId, { sent: true }),
    );
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
      streamBusy={streamState === "submitting" || streamState === "streaming"}
      onTabChange={setActiveTab}
      onToggle={toggleWorkspace}
      onResizeStart={handleWorkspaceResizeStart}
      onSendControlImage={handleSendControlImage}
      onSendReferenceImage={handleSendReferenceImage}
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
      <div className="relative flex min-w-0 flex-1 flex-col">
        <ChatPanel
          sessionTitle={sessionTitle}
          messages={visibleMessages}
          activeToolStatus={activeToolStatus}
          agentStatusesByMessage={agentStatusesByMessage}
          generationPreviews={generationPreviews.filter((item) => item.imageUrl)}
          streamState={streamState}
          errorMessage={errorMessage}
          isWelcome={isWelcome}
          onSubmit={handleSubmit}
        />
        {ragPopup && (
          <RagCandidatesPopup
            candidates={ragPopup.candidates}
            timeout={ragPopup.timeout}
            sessionId={sessionId}
            runId={ragPopup.runId}
            onClose={() => setRagPopup(null)}
          />
        )}
      </div>
      {isWelcome ? null : workspacePanel}
    </div>
  );
}
