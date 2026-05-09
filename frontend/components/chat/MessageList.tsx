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
        <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-black/8 text-sm text-muted-foreground">
          发送第一条消息开始对话
        </div>
      ) : null}

      {messages.map((message, index) => {
        const isAssistant = message.role === "assistant";
        const isLast = index === messages.length - 1;

        if (isAssistant) {
          return (
            <div key={message.id} className="flex justify-start">
              <div className="max-w-[78%]">
                {message.content ? (
                  <div className="text-sm leading-6 whitespace-pre-wrap text-foreground">
                    {message.content}
                  </div>
                ) : (
                  <div className="flex items-center gap-1 py-1">
                    <span className="size-1.5 rounded-full bg-black/30 animate-bounce [animation-delay:-0.3s]" />
                    <span className="size-1.5 rounded-full bg-black/30 animate-bounce [animation-delay:-0.15s]" />
                    <span className="size-1.5 rounded-full bg-black/30 animate-bounce" />
                  </div>
                )}
                {isLast && activeToolStatus ? (
                  <div className="mt-2 rounded-xl bg-black/[0.04] px-3 py-2 text-xs text-muted-foreground">
                    {activeToolStatus.summary}
                  </div>
                ) : null}
              </div>
            </div>
          );
        }

        return (
          <div key={message.id} className="flex justify-end">
            <div className="max-w-[78%] rounded-2xl border border-black/6 bg-black/[0.04] px-4 py-3 text-sm text-foreground">
              <div className="whitespace-pre-wrap leading-6">{message.content}</div>
            </div>
          </div>
        );
      })}

      {generationPreviews.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {generationPreviews.map((preview) => (
            <div key={preview.taskId} className="overflow-hidden rounded-2xl border border-black/8 bg-white">
              {/* Generated images may come from arbitrary remote providers; keep raw img in E-1. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.imageUrl}
                alt="生成结果缩略图"
                className="h-40 w-full object-cover"
              />
              <div className="border-t border-black/6 px-3 py-2 text-xs text-muted-foreground">
                task: {preview.taskId}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
