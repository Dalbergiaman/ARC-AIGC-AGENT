"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { createSession } from "@/lib/api";
import type { SessionResponse } from "@/lib/types";

type Props = {
  sessionId: string;
};

let pendingSessionCreation: Promise<SessionResponse> | null = null;

export function ChatSessionShell({ sessionId }: Props) {
  const router = useRouter();
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(
    sessionId === "new" ? null : sessionId,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function resolveSession() {
      if (sessionId !== "new") {
        setResolvedSessionId(sessionId);
        setError(null);
        return;
      }

      setResolvedSessionId(null);
      setError(null);

      try {
        if (!pendingSessionCreation) {
          pendingSessionCreation = createSession();
        }
        const session = await pendingSessionCreation;
        if (!active) {
          return;
        }
        setResolvedSessionId(session.id);
        router.replace(`/chat/${session.id}`);
      } catch (nextError) {
        if (!active) {
          return;
        }
        setError(nextError instanceof Error ? nextError.message : "创建会话失败");
      } finally {
        pendingSessionCreation = null;
      }
    }

    resolveSession();
    return () => {
      active = false;
    };
  }, [router, sessionId]);

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!resolvedSessionId) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-sm text-muted-foreground">
        正在创建会话...
      </div>
    );
  }

  return <ChatWorkspace sessionId={resolvedSessionId} />;
}
