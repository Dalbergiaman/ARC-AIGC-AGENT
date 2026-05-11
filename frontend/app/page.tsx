"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { HomeGallery } from "@/components/gallery/HomeGallery";
import { listSessions } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [navigating, setNavigating] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const galleryRef = useRef<HTMLDivElement>(null);
  const lockUntilRef = useRef(0);

  function handleWheel(e: React.WheelEvent) {
    const now = Date.now();
    if (now < lockUntilRef.current) return;

    if (!collapsed && e.deltaY > 0) {
      setCollapsed(true);
      lockUntilRef.current = now + 700;
      return;
    }
    if (
      collapsed &&
      e.deltaY < 0 &&
      (galleryRef.current?.scrollTop ?? 0) <= 0
    ) {
      setCollapsed(false);
      lockUntilRef.current = now + 700;
    }
  }

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
    <div
      onWheel={handleWheel}
      className="fixed inset-0 overflow-hidden bg-background"
    >
      <div
        className="absolute left-1/2 flex flex-col items-center transition-all duration-500 ease-out"
        style={{
          top: collapsed ? "24px" : "50%",
          transform: collapsed ? "translateX(-50%)" : "translate(-50%, -50%)",
          gap: collapsed ? 0 : "1.5rem",
        }}
      >
        <h1
          className="font-semibold tracking-tight transition-all duration-500 ease-out"
          style={{ fontSize: collapsed ? "1.5rem" : "3.5rem" }}
        >
          AIGC Agent
        </h1>
        <div
          className="flex flex-col items-center gap-6 transition-all duration-500 ease-out"
          style={{
            opacity: collapsed ? 0 : 1,
            maxHeight: collapsed ? 0 : "200px",
            overflow: "hidden",
            pointerEvents: collapsed ? "none" : "auto",
          }}
        >
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
      </div>

      <div
        ref={galleryRef}
        className="absolute inset-x-0 bottom-0 overflow-y-auto transition-[top] duration-500 ease-out"
        style={{ top: collapsed ? "140px" : "100vh" }}
      >
        <HomeGallery />
      </div>

      <button
        type="button"
        onClick={() => setCollapsed(true)}
        aria-label="查看历史作品"
        className="text-muted-foreground hover:text-foreground absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce rounded-full p-2 transition-opacity duration-500"
        style={{
          opacity: collapsed ? 0 : 1,
          pointerEvents: collapsed ? "none" : "auto",
        }}
      >
        <ChevronDown className="h-8 w-8" />
      </button>
    </div>
  );
}
