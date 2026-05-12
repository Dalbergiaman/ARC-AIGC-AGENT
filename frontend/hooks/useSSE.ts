"use client";

import { useEffect, useRef } from "react";

import { getApiBaseUrl } from "@/lib/api";
import type { RagImageState, SSEEventType, StyleTemplate } from "@/lib/types";

type RagCandidate = {
  image_id: string;
  image_url: string;
  caption?: string;
  score?: number;
};

type Handlers = {
  onTextDelta?: (content: string) => void;
  onToolStart?: (tool: string, summary: string) => void;
  onToolEnd?: (tool: string, summary: string) => void;
  onGenerationStart?: (taskId: string, runId?: string) => void;
  onGenerationDone?: (payload: {
    taskId: string;
    imageUrl: string;
    runId?: string;
    provider?: string | null;
    score?: number | null;
    status?: string;
    prompt?: string;
    negativePrompt?: string | null;
    rawResponse?: Record<string, unknown> | null;
  }) => void;
  onPromptUpdate?: (
    keywords: Record<string, string>,
    llmDescription: string,
    customDescription: string,
    negativePrompt: string,
    promptTemplate: StyleTemplate | null,
    source: "agent_node" | "enhance_prompt" | "refine_prompt",
  ) => void;
  onRagCandidates?: (candidates: RagCandidate[], timeout: number) => void;
  onRagImageUpdate?: (ragImage: RagImageState) => void;
  onError?: (code: string, message: string) => void;
  onDone?: (finishReason: "stop" | "max_retries" | "interrupted") => void;
};

type Options = {
  sessionId: string | null;
  streamId: string | null;
  enabled?: boolean;
} & Handlers;

export function useSSE({
  sessionId,
  streamId,
  enabled = true,
  onTextDelta,
  onToolStart,
  onToolEnd,
  onGenerationStart,
  onGenerationDone,
  onPromptUpdate,
  onRagCandidates,
  onRagImageUpdate,
  onError,
  onDone,
}: Options) {
  const handlersRef = useRef<Handlers>({
    onTextDelta,
    onToolStart,
    onToolEnd,
    onGenerationStart,
    onGenerationDone,
    onPromptUpdate,
    onRagCandidates,
    onRagImageUpdate,
    onError,
    onDone,
  });

  useEffect(() => {
    handlersRef.current = {
      onTextDelta,
      onToolStart,
      onToolEnd,
      onGenerationStart,
      onGenerationDone,
      onPromptUpdate,
      onRagCandidates,
      onRagImageUpdate,
      onError,
      onDone,
    };
  }, [
    onDone,
    onError,
    onGenerationDone,
    onGenerationStart,
    onPromptUpdate,
    onRagCandidates,
    onRagImageUpdate,
    onTextDelta,
    onToolEnd,
    onToolStart,
  ]);

  useEffect(() => {
    if (!enabled || !sessionId || !streamId) {
      return;
    }

    const eventSource = new EventSource(
      `${getApiBaseUrl()}/api/chat/sessions/${sessionId}/stream?stream_id=${streamId}`,
    );

    let doneReceived = false;

    const handleEvent = (eventType: SSEEventType, event: MessageEvent<string>) => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(event.data) as Record<string, unknown>;
      } catch {
        data = {};
      }

      const handlers = handlersRef.current;
      if (eventType === "text_delta" && typeof data.content === "string") {
        handlers.onTextDelta?.(data.content);
      }
      if (eventType === "tool_start" && typeof data.tool === "string") {
        handlers.onToolStart?.(data.tool, typeof data.summary === "string" ? data.summary : data.tool);
      }
      if (eventType === "tool_end" && typeof data.tool === "string" && typeof data.summary === "string") {
        handlers.onToolEnd?.(data.tool, data.summary);
      }
      if (eventType === "generation_start" && typeof data.task_id === "string") {
        handlers.onGenerationStart?.(
          data.task_id,
          typeof data.run_id === "string" ? data.run_id : undefined,
        );
      }
      if (
        eventType === "generation_done" &&
        typeof data.task_id === "string" &&
        typeof data.image_url === "string"
      ) {
        handlers.onGenerationDone?.({
          taskId: data.task_id,
          imageUrl: data.image_url,
          runId: typeof data.run_id === "string" ? data.run_id : undefined,
          provider: typeof data.provider === "string" ? data.provider : null,
          score: typeof data.score === "number" ? data.score : null,
          status: typeof data.status === "string" ? data.status : "done",
          prompt: typeof data.prompt === "string" ? data.prompt : undefined,
          negativePrompt: typeof data.negative_prompt === "string" ? data.negative_prompt : null,
          rawResponse: data.raw_response && typeof data.raw_response === "object"
            ? data.raw_response as Record<string, unknown>
            : null,
        });
      }
      if (
        eventType === "prompt_update" &&
        data.keywords &&
        typeof data.llm_description === "string" &&
        typeof data.custom_description === "string" &&
        typeof data.negative_prompt === "string" &&
        (data.source === "agent_node" || data.source === "enhance_prompt" || data.source === "refine_prompt")
      ) {
        handlers.onPromptUpdate?.(
          data.keywords as Record<string, string>,
          data.llm_description,
          data.custom_description,
          data.negative_prompt,
          data.prompt_template && typeof data.prompt_template === "object"
            ? data.prompt_template as StyleTemplate
            : null,
          data.source,
        );
      }
      if (eventType === "error" && typeof data.code === "string" && typeof data.message === "string") {
        handlers.onError?.(data.code, data.message);
      }
      if (eventType === "rag_candidates" && Array.isArray(data.candidates)) {
        handlers.onRagCandidates?.(
          data.candidates as RagCandidate[],
          typeof data.timeout === "number" ? data.timeout : 600,
        );
      }
      if (eventType === "rag_image_update" && typeof data.file_id === "string") {
        handlers.onRagImageUpdate?.(data as unknown as RagImageState);
      }
      if (eventType === "done" && typeof data.finish_reason === "string") {
        doneReceived = true;
        handlers.onDone?.(data.finish_reason as "stop" | "max_retries" | "interrupted");
        eventSource.close();
      }
    };

    const textDeltaListener = (event: MessageEvent<string>) => handleEvent("text_delta", event);
    const toolStartListener = (event: MessageEvent<string>) => handleEvent("tool_start", event);
    const toolEndListener = (event: MessageEvent<string>) => handleEvent("tool_end", event);
    const generationStartListener = (event: MessageEvent<string>) =>
      handleEvent("generation_start", event);
    const generationDoneListener = (event: MessageEvent<string>) =>
      handleEvent("generation_done", event);
    const promptUpdateListener = (event: MessageEvent<string>) =>
      handleEvent("prompt_update", event);
    const ragCandidatesListener = (event: MessageEvent<string>) =>
      handleEvent("rag_candidates", event);
    const ragImageUpdateListener = (event: MessageEvent<string>) =>
      handleEvent("rag_image_update", event);
    const errorListener = (event: MessageEvent<string>) => handleEvent("error", event);
    const doneListener = (event: MessageEvent<string>) => handleEvent("done", event);

    eventSource.addEventListener("text_delta", textDeltaListener);
    eventSource.addEventListener("tool_start", toolStartListener);
    eventSource.addEventListener("tool_end", toolEndListener);
    eventSource.addEventListener("generation_start", generationStartListener);
    eventSource.addEventListener("generation_done", generationDoneListener);
    eventSource.addEventListener("prompt_update", promptUpdateListener);
    eventSource.addEventListener("rag_candidates", ragCandidatesListener);
    eventSource.addEventListener("rag_image_update", ragImageUpdateListener);
    eventSource.addEventListener("error", errorListener);
    eventSource.addEventListener("done", doneListener);
    eventSource.onerror = () => {
      if (doneReceived) return;
      handlersRef.current.onError?.("SSE_CONNECTION_ERROR", "流式连接已中断");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [enabled, sessionId, streamId]);
}
