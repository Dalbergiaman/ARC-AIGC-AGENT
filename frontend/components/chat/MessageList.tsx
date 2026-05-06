"use client";

import type { ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

type Props = {
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  generationPreviews: GenerationPreview[];
};

export function MessageList({ messages, activeToolStatus, generationPreviews }: Props) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-6">
      {messages.length === 0 ? (
        <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed text-sm text-muted-foreground">
          发送第一条消息开始对话
        </div>
      ) : null}

      {messages.map((message) => {
        const isAssistant = message.role === "assistant";

        return (
          <div
            key={message.id}
            className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                isAssistant
                  ? "border bg-white text-foreground"
                  : "bg-primary text-primary-foreground"
              }`}
            >
              <div className="whitespace-pre-wrap leading-6">{message.content || " "}</div>
              {isAssistant && activeToolStatus ? (
                <div className="mt-3 rounded-xl bg-muted px-3 py-2 text-xs text-muted-foreground">
                  {activeToolStatus.summary}
                </div>
              ) : null}
            </div>
          </div>
        );
      })}

      {generationPreviews.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {generationPreviews.map((preview) => (
            <div key={preview.taskId} className="overflow-hidden rounded-2xl border bg-white shadow-sm">
              {/* Generated images may come from arbitrary remote providers; keep raw img in E-1. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.imageUrl}
                alt="生成结果缩略图"
                className="h-40 w-full object-cover"
              />
              <div className="border-t px-3 py-2 text-xs text-muted-foreground">
                task: {preview.taskId}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
