"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  Activity,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Home,
  MessageSquare,
  Plus,
  Settings2,
  Trash2,
} from "lucide-react";

import type { SessionResponse } from "@/lib/types";

type Props = {
  collapsed: boolean;
  sessionId: string;
  sessions: SessionResponse[];
  onToggle: () => void;
  onDeleteSession: (sessionId: string) => void | Promise<void>;
};

export function AppSidebar({
  collapsed,
  sessionId,
  sessions,
  onToggle,
  onDeleteSession,
}: Props) {
  const historyItems = useMemo(
    () => sessions.map((session) => ({
      id: session.id,
      label: session.title?.trim() || "Unnamed Chat",
      createdAt: session.created_at,
    })),
    [sessions],
  );

  return (
    <aside
      className={`flex self-stretch flex-col border-r border-black/6 bg-white transition-[width] duration-200 ${
        collapsed ? "w-16" : "w-72"
      }`}
    >
      <div className="flex h-[72px] items-center justify-between border-b border-black/6 px-3 py-4">
        <div className={`min-w-0 ${collapsed ? "hidden" : "block"}`}>
          <div className="text-sm font-semibold">AIGC Agent</div>
          <div className="truncate text-xs text-muted-foreground">建筑效果图工作台</div>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md border border-black/8 p-2 text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
          aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-6 px-3 py-4">
        <div className="space-y-2">
          <Link
            href="/"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-black/[0.04]"
          >
            <Home className="size-4 shrink-0" />
            {!collapsed ? <span>首页</span> : null}
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-black/[0.04]"
          >
            <Settings2 className="size-4 shrink-0" />
            {!collapsed ? <span>Dashboard</span> : null}
          </Link>
          <a
            href="http://localhost:8080"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-black/[0.04]"
          >
            <BookOpen className="size-4 shrink-0" />
            {!collapsed ? <span>知识库</span> : null}
          </a>
          <a
            href="http://localhost:3000"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-black/[0.04]"
          >
            <Activity className="size-4 shrink-0" />
            {!collapsed ? <span>推理追踪</span> : null}
          </a>
          <Link
            href="/chat/new"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-black/[0.04]"
          >
            <Plus className="size-4 shrink-0" />
            {!collapsed ? <span>新建对话</span> : null}
          </Link>
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
                <div
                  key={item.id}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors ${
                    active
                      ? "border-black/10 bg-black/[0.035]"
                      : "border-transparent bg-transparent hover:bg-black/[0.035]"
                  }`}
                >
                  <Link
                    href={`/chat/${item.id}`}
                    className="flex min-w-0 flex-1 items-center gap-3"
                  >
                    <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                    {!collapsed ? (
                      <div className="min-w-0">
                        <div className="truncate font-medium">{item.label}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {item.createdAt
                            ? new Date(item.createdAt).toLocaleString("zh-CN", {
                                timeZone: "Asia/Shanghai",
                                hour12: false,
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
                  {!collapsed ? (
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        void onDeleteSession(item.id);
                      }}
                      className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-black/[0.05] hover:text-destructive"
                      aria-label={`删除会话 ${item.label}`}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </nav>
    </aside>
  );
}
