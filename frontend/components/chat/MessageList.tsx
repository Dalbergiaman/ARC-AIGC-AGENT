"use client";

import { getApiBaseUrl } from "@/lib/api";
import type { ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

type Props = {
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  generationPreviews: GenerationPreview[];
};

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

function PreviewGrid({ previews }: { previews: GenerationPreview[] }) {
  const visible = previews.filter((p) => p.imageUrl);
  if (!visible.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {visible.map((preview) => (
        <div key={preview.taskId} className="overflow-hidden rounded-lg border border-black/8 bg-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resolveImageUrl(preview.imageUrl!)}
            alt="生成结果缩略图"
            className="h-32 w-auto object-contain"
          />
        </div>
      ))}
    </div>
  );
}

export function MessageList({ messages, activeToolStatus, generationPreviews }: Props) {
  const unanchored = generationPreviews.filter((p) => !p.assistantMessageId && p.imageUrl);

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
        const linked = generationPreviews.filter((p) => p.assistantMessageId === message.id);

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
                <PreviewGrid previews={linked} />
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

      {unanchored.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {unanchored.map((preview) => (
            <div key={preview.taskId} className="overflow-hidden rounded-lg border border-black/8 bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveImageUrl(preview.imageUrl!)}
                alt="生成结果缩略图"
                className="h-32 w-auto object-contain"
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
