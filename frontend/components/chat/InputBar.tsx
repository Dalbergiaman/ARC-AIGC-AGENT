"use client";

import { FormEvent, useState } from "react";
import { SendHorizontal } from "lucide-react";

type Props = {
  disabled?: boolean;
  onSubmit: (content: string) => Promise<void> | void;
};

export function InputBar({ disabled = false, onSubmit }: Props) {
  const [value, setValue] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = value.trim();
    if (!content || disabled) {
      return;
    }

    setValue("");
    await onSubmit(content);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white px-4 py-4">
      <div className="flex items-end gap-3 rounded-3xl border border-black/8 bg-white p-3">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="描述你想生成的建筑效果图"
          className="min-h-20 flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground"
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
