"use client";

import { useMemo } from "react";
import Link from "next/link";
import { BookOpen, ChevronLeft, ChevronRight, Home, MessageSquare, Settings2 } from "lucide-react";

import type { SessionResponse } from "@/lib/types";

type Props = {
  collapsed: boolean;
  sessionId: string;
  sessions: SessionResponse[];
  onToggle: () => void;
};

export function AppSidebar({ collapsed, sessionId, sessions, onToggle }: Props) {
  const historyItems = useMemo(
    () => sessions.slice(0, 8).map((session) => ({
      id: session.id,
      label: `会话 ${session.id.slice(0, 8)}`,
      createdAt: session.created_at,
    })),
    [sessions],
  );

  return (
    <aside
      className={`flex h-full flex-col border-r bg-[linear-gradient(180deg,#ffffff_0%,#fafafa_100%)] transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-72"
      }`}
    >
      <div className="flex items-center justify-between border-b px-3 py-3">
        <div className={`min-w-0 ${collapsed ? "hidden" : "block"}`}>
          <div className="text-sm font-semibold">AIGC Agent</div>
          <div className="truncate text-xs text-muted-foreground">建筑效果图工作台</div>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md border p-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-6 px-3 py-4">
        <div className="space-y-2">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent"
          >
            <Home className="size-4 shrink-0" />
            {!collapsed ? <span>首页</span> : null}
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent"
          >
            <Settings2 className="size-4 shrink-0" />
            {!collapsed ? <span>Dashboard</span> : null}
          </Link>
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <BookOpen className="size-4 shrink-0" />
            {!collapsed ? <span>知识库</span> : null}
          </button>
        </div>

        <div className="space-y-2">
          {!collapsed ? (
            <div className="px-3 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
              历史对话
            </div>
          ) : null}
          <div className="space-y-2">
            {historyItems.map((item) => {
              const active = item.id === sessionId;
              return (
                <Link
                  key={item.id}
                  href={`/chat/${item.id}`}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-3 text-sm transition-colors ${
                    active ? "border-primary/30 bg-primary/5" : "bg-background/80 hover:bg-accent"
                  }`}
                >
                  <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                  {!collapsed ? (
                    <div className="min-w-0">
                      <div className="truncate font-medium">{item.label}</div>
                      <div className="truncate text-xs text-muted-foreground">
                        {item.createdAt
                          ? new Date(item.createdAt).toLocaleString("zh-CN", {
                              month: "2-digit",
                              day: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : item.id}
                      </div>
                    </div>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>
    </aside>
  );
}
