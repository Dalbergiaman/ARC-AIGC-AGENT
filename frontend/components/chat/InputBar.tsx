"use client";

import { FormEvent, KeyboardEvent, useState } from "react";
import { SendHorizontal } from "lucide-react";

type Props = {
  disabled?: boolean;
  welcome?: boolean;
  onSubmit: (content: string) => Promise<void> | void;
};

export function InputBar({ disabled = false, welcome = false, onSubmit }: Props) {
  const [value, setValue] = useState("");

  async function submit() {
    const content = value.trim();
    if (!content || disabled) {
      return;
    }
    setValue("");
    await onSubmit(content);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter") return;
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    if (event.ctrlKey || event.shiftKey || event.metaKey) return;
    event.preventDefault();
    void submit();
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white px-4 py-4">
      <div className="flex items-end gap-3 rounded-3xl border border-black/8 bg-white p-3">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            welcome
              ? "描述你想要的建筑效果，我会陪你逐步细化并出图。（Enter 发送，Ctrl/Shift/Cmd+Enter 换行）"
              : "描述你想生成的建筑效果图（Enter 发送，Ctrl/Shift/Cmd+Enter 换行）"
          }
          className="h-20 flex-1 resize-none overflow-y-auto bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          disabled={disabled}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-2xl bg-black/8 text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="发送消息"
        >
          <SendHorizontal className="size-4" />
        </button>
      </div>
    </form>
  );
}
