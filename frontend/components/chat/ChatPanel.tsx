"use client";

import type { ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

import { InputBar } from "@/components/chat/InputBar";
import { MessageList } from "@/components/chat/MessageList";

type Props = {
  sessionTitle: string;
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  generationPreviews: GenerationPreview[];
  streamState: "idle" | "submitting" | "streaming" | "error";
  errorMessage: string | null;
  onSubmit: (content: string) => Promise<void>;
};

export function ChatPanel({
  sessionTitle,
  messages,
  activeToolStatus,
  generationPreviews,
  streamState,
  errorMessage,
  onSubmit,
}: Props) {
  return (
    <section className="flex min-h-0 flex-1 flex-col bg-white">
      <header className="flex h-[72px] flex-col justify-center border-b border-black/6 bg-white px-6 py-4">
        <div className="text-sm font-semibold">{sessionTitle}</div>
        <div className="text-xs text-muted-foreground">
          {streamState === "streaming" ? "模型正在回复" : "纯文字对话主链路"}
        </div>
      </header>

      {errorMessage ? (
        <div className="border-b bg-red-50 px-6 py-3 text-sm text-red-700">{errorMessage}</div>
      ) : null}

      <MessageList
        messages={messages}
        activeToolStatus={activeToolStatus}
        generationPreviews={generationPreviews}
      />

      <InputBar disabled={streamState === "submitting" || streamState === "streaming"} onSubmit={onSubmit} />
    </section>
  );
}
