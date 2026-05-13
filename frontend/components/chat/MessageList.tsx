"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api";
import type { AgentStatus, ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

type Props = {
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  agentStatusesByMessage: Record<string, AgentStatus[]>;
  generationPreviews: GenerationPreview[];
};

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

function PreviewGrid({
  previews,
  onOpen,
}: {
  previews: GenerationPreview[];
  onOpen: (url: string) => void;
}) {
  const visible = previews.filter((p) => p.imageUrl);
  if (!visible.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {visible.map((preview) => (
        <button
          key={preview.taskId}
          type="button"
          onClick={() => onOpen(resolveImageUrl(preview.imageUrl!))}
          className="overflow-hidden rounded-lg border border-black/8 bg-white transition hover:border-black/20 focus:outline-none focus:ring-2 focus:ring-black/20"
          aria-label="放大查看生成结果"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resolveImageUrl(preview.imageUrl!)}
            alt="生成结果缩略图"
            className="h-32 w-auto object-contain"
          />
        </button>
      ))}
    </div>
  );
}

function StatusList({ statuses }: { statuses: AgentStatus[] }) {
  if (!statuses.length) return null;
  return (
    <div className="mt-3 space-y-1.5 rounded-md border border-black/6 bg-black/[0.025] px-3 py-2">
      {statuses.map((item) => (
        <div key={item.id} className="flex items-center gap-2 text-xs text-muted-foreground">
          {item.status === "running" ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : item.status === "done" ? (
            <Check className="size-3.5" />
          ) : (
            <X className="size-3.5" />
          )}
          <span>{item.summary}</span>
        </div>
      ))}
    </div>
  );
}

export function MessageList({ messages, activeToolStatus, agentStatusesByMessage, generationPreviews }: Props) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const unanchored = generationPreviews.filter((p) => !p.assistantMessageId && p.imageUrl);

  useEffect(() => {
    if (!previewUrl) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPreviewUrl(null);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [previewUrl]);

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
        const statuses = agentStatusesByMessage[message.id] ?? [];

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
                <StatusList statuses={statuses} />
                <PreviewGrid previews={linked} onOpen={setPreviewUrl} />
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
            <button
              key={preview.taskId}
              type="button"
              onClick={() => setPreviewUrl(resolveImageUrl(preview.imageUrl!))}
              className="overflow-hidden rounded-lg border border-black/8 bg-white transition hover:border-black/20 focus:outline-none focus:ring-2 focus:ring-black/20"
              aria-label="放大查看生成结果"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveImageUrl(preview.imageUrl!)}
                alt="生成结果缩略图"
                className="h-32 w-auto object-contain"
              />
            </button>
          ))}
        </div>
      ) : null}

      {previewUrl ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-4"
          onClick={() => setPreviewUrl(null)}
        >
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setPreviewUrl(null);
            }}
            aria-label="关闭预览"
            className="absolute right-5 top-5 rounded-md bg-white/90 p-2 text-black shadow hover:bg-white focus:outline-none focus:ring-2 focus:ring-white/80"
          >
            <X className="size-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt="生成结果大图"
            onClick={(event) => event.stopPropagation()}
            className="max-h-[92vh] max-w-[92vw] rounded-md bg-white object-contain shadow-2xl"
          />
        </div>
      ) : null}
    </div>
  );
}
