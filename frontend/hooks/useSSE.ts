"use client";

import { useEffect, useRef } from "react";

import { getApiBaseUrl } from "@/lib/api";
import type { SSEEventType } from "@/lib/types";

type Handlers = {
  onTextDelta?: (content: string) => void;
  onToolStart?: (tool: string, summary: string) => void;
  onToolEnd?: (tool: string, summary: string) => void;
  onGenerationStart?: (taskId: string, runId?: string) => void;
  onGenerationDone?: (taskId: string, imageUrl: string, runId?: string) => void;
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
  onError,
  onDone,
}: Options) {
  const handlersRef = useRef<Handlers>({
    onTextDelta,
    onToolStart,
    onToolEnd,
    onGenerationStart,
    onGenerationDone,
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
      onError,
      onDone,
    };
  }, [onDone, onError, onGenerationDone, onGenerationStart, onTextDelta, onToolEnd, onToolStart]);

  useEffect(() => {
    if (!enabled || !sessionId || !streamId) {
      return;
    }

    const eventSource = new EventSource(
      `${getApiBaseUrl()}/api/chat/sessions/${sessionId}/stream?stream_id=${streamId}`,
    );

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
        handlers.onGenerationDone?.(
          data.task_id,
          data.image_url,
          typeof data.run_id === "string" ? data.run_id : undefined,
        );
      }
      if (eventType === "error" && typeof data.code === "string" && typeof data.message === "string") {
        handlers.onError?.(data.code, data.message);
      }
      if (eventType === "done" && typeof data.finish_reason === "string") {
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
    const errorListener = (event: MessageEvent<string>) => handleEvent("error", event);
    const doneListener = (event: MessageEvent<string>) => handleEvent("done", event);

    eventSource.addEventListener("text_delta", textDeltaListener);
    eventSource.addEventListener("tool_start", toolStartListener);
    eventSource.addEventListener("tool_end", toolEndListener);
    eventSource.addEventListener("generation_start", generationStartListener);
    eventSource.addEventListener("generation_done", generationDoneListener);
    eventSource.addEventListener("error", errorListener);
    eventSource.addEventListener("done", doneListener);
    eventSource.onerror = () => {
      handlersRef.current.onError?.("SSE_CONNECTION_ERROR", "流式连接已中断");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [enabled, sessionId, streamId]);
}
