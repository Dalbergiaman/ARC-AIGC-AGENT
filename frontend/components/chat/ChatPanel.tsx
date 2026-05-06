"use client";

import type { ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

import { InputBar } from "@/components/chat/InputBar";
import { MessageList } from "@/components/chat/MessageList";

type Props = {
  sessionId: string;
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  generationPreviews: GenerationPreview[];
  streamState: "idle" | "submitting" | "streaming" | "error";
  errorMessage: string | null;
  onSubmit: (content: string) => Promise<void>;
};

export function ChatPanel({
  sessionId,
  messages,
  activeToolStatus,
  generationPreviews,
  streamState,
  errorMessage,
  onSubmit,
}: Props) {
  return (
    <section className="flex min-h-0 flex-1 flex-col bg-[linear-gradient(180deg,#fcfcfc_0%,#f7f7f7_100%)]">
      <header className="border-b bg-white/80 px-6 py-4 backdrop-blur">
        <div className="text-sm font-semibold">会话 {sessionId}</div>
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
