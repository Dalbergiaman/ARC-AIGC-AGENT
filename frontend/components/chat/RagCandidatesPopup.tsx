"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getApiBaseUrl } from "@/lib/api";

type RagCandidate = {
  image_id: string;
  image_url: string;
  caption?: string;
  score?: number;
};

type Props = {
  candidates: RagCandidate[];
  timeout: number;
  sessionId: string;
  runId: string;
  onClose: () => void;
};

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

export function RagCandidatesPopup({ candidates, timeout, sessionId, runId, onClose }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(timeout);
  const [picking, setPicking] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(timerRef.current!);
          onClose();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [onClose]);

  const sendPick = useCallback(
    async (imageId: string | null) => {
      if (picking) return;
      setPicking(true);
      if (timerRef.current) clearInterval(timerRef.current);
      try {
        await fetch(`${getApiBaseUrl()}/api/library/pick`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, run_id: runId, image_id: imageId }),
        });
      } catch {
        // best-effort; rag_gate will timeout and continue
      } finally {
        onClose();
      }
    },
    [picking, sessionId, runId, onClose],
  );

  return (
    <div className="absolute inset-x-0 bottom-24 z-50 mx-4 rounded-xl border border-gray-200 bg-white shadow-lg">
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <div>
          <p className="text-sm font-medium text-gray-900">选择氛围参考图</p>
          <p className="text-xs text-gray-500">选中一张作为第三槽位氛围参考，或跳过</p>
        </div>
        <span className="text-xs tabular-nums text-gray-400">{secondsLeft}s</span>
      </div>

      <div className="flex gap-3 overflow-x-auto p-4">
        {candidates.map((c) => (
          <button
            key={c.image_id}
            onClick={() => sendPick(c.image_id)}
            disabled={picking}
            className="group relative flex-shrink-0 overflow-hidden rounded-lg border-2 border-transparent transition hover:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
          >
            <img
              src={resolveImageUrl(c.image_url)}
              alt={c.caption ?? "候选图"}
              className="h-32 w-32 object-cover"
            />
            {c.score !== undefined && (
              <span className="absolute bottom-1 right-1 rounded bg-black/60 px-1 py-0.5 text-[10px] text-white">
                {(c.score * 100).toFixed(0)}%
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex justify-end border-t border-gray-100 px-4 py-3">
        <button
          onClick={() => sendPick(null)}
          disabled={picking}
          className="rounded-md px-4 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
        >
          跳过
        </button>
      </div>
    </div>
  );
}
