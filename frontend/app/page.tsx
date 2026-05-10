"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { listSessions } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [navigating, setNavigating] = useState(false);

  async function handleStartChat() {
    if (navigating) return;
    setNavigating(true);
    try {
      const sessions = await listSessions();
      const latestId = sessions[0]?.id;
      router.push(latestId ? `/chat/${latestId}` : "/chat/new");
    } catch {
      router.push("/chat/new");
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">AIGC Agent</h1>
      <p className="text-muted-foreground text-sm">建筑效果图生成系统</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleStartChat}
          disabled={navigating}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
        >
          {navigating ? "正在打开..." : "开始对话"}
        </button>
        <Link
          href="/dashboard"
          className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
