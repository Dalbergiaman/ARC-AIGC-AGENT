"use client";

import type { AgentStatus, ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

import { InputBar } from "@/components/chat/InputBar";
import { MessageList } from "@/components/chat/MessageList";

type Props = {
  sessionTitle: string;
  messages: ChatMessage[];
  activeToolStatus: ToolStatus | null;
  agentStatusesByMessage: Record<string, AgentStatus[]>;
  generationPreviews: GenerationPreview[];
  streamState: "idle" | "submitting" | "streaming" | "error";
  errorMessage: string | null;
  isWelcome: boolean;
  onSubmit: (content: string) => Promise<void>;
};

export function ChatPanel({
  sessionTitle,
  messages,
  activeToolStatus,
  agentStatusesByMessage,
  generationPreviews,
  streamState,
  errorMessage,
  isWelcome,
  onSubmit,
}: Props) {
  const inputDisabled = streamState === "submitting" || streamState === "streaming";

  if (isWelcome) {
    return (
      <section className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-white transition-all duration-300">
        <header className="flex h-[72px] shrink-0 flex-col justify-center bg-white px-6 py-4">
          <div className="text-sm font-semibold">{sessionTitle}</div>
          <div className="text-xs text-muted-foreground">开启新的建筑效果图对话</div>
        </header>
        {/* 黄金分割：内容块顶部距可用区域顶部约 38.2% */}
        <div className="flex min-h-0 flex-1 flex-col items-center overflow-hidden px-6 pt-[18%]">
          <div className="flex w-[50%] flex-col items-center gap-5">
            {/* eslint-disable-next-line react/no-unescaped-entities */}
            <h1 className="text-2xl font-semibold tracking-tight">(●'◡'●) 有什么想生成的？</h1>
            <div className="w-full">
              <InputBar disabled={inputDisabled} onSubmit={onSubmit} welcome />
            </div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="grid h-full min-h-0 flex-1 grid-rows-[72px_minmax(0,1fr)_auto] overflow-hidden bg-white transition-all duration-300">
      <header className="flex min-h-0 flex-col justify-center bg-white px-6 py-4">
        <div className="text-sm font-semibold">{sessionTitle}</div>
        <div className="text-xs text-muted-foreground">
          {streamState === "streaming" ? "模型正在回复" : "纯文字对话主链路"}
        </div>
      </header>

      <div className="flex min-h-0 flex-col overflow-hidden">
        {errorMessage ? (
          <div className="shrink-0 border-b bg-red-50 px-6 py-3 text-sm text-red-700">{errorMessage}</div>
        ) : null}
        <MessageList
          messages={messages}
          activeToolStatus={activeToolStatus}
          agentStatusesByMessage={agentStatusesByMessage}
          generationPreviews={generationPreviews}
        />
      </div>

      <div className="min-h-0">
        <InputBar disabled={inputDisabled} onSubmit={onSubmit} />
      </div>
    </section>
  );
}
