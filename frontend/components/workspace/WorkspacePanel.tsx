"use client";

import { PanelRightClose, PanelRightOpen } from "lucide-react";

import { PromptReferenceTab } from "@/components/workspace/PromptReferenceTab";
import type { GenerationPreview, WorkspaceTab } from "@/lib/types";

type Props = {
  sessionId: string;
  activeTab: WorkspaceTab;
  collapsed: boolean;
  widthRatio: number;
  generationPreviews: GenerationPreview[];
  isResizing: boolean;
  onTabChange: (tab: WorkspaceTab) => void;
  onToggle: () => void;
  onResizeStart: () => void;
};

export function WorkspacePanel({
  sessionId,
  activeTab,
  collapsed,
  widthRatio,
  generationPreviews,
  isResizing,
  onTabChange,
  onToggle,
  onResizeStart,
}: Props) {
  if (collapsed) {
    return (
      <aside className="hidden w-14 shrink-0 border-l border-black/6 bg-white xl:flex xl:flex-col">
        <div className="flex flex-1 flex-col items-center gap-3 px-2 py-4">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex size-9 items-center justify-center rounded-md border border-black/8 bg-white text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
            aria-label="展开工作区"
          >
            <PanelRightOpen className="size-4" />
          </button>
          <div className="writing-mode-vertical text-xs text-muted-foreground [writing-mode:vertical-rl] [text-orientation:mixed]">
            工作区
          </div>
        </div>
      </aside>
    );
  }

  return (
    <>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="调整工作区宽度"
        onPointerDown={onResizeStart}
        className={`hidden w-1 shrink-0 cursor-col-resize bg-transparent transition-colors xl:block ${
          isResizing ? "bg-black/8" : "hover:bg-black/[0.05]"
        }`}
      />
      <aside
        className="hidden shrink-0 border-l border-black/6 bg-white xl:flex xl:flex-col"
        style={{ width: `${widthRatio * 100}%` }}
      >
        {/* Header */}
        <div className="flex h-[72px] items-center justify-between gap-3 border-b border-black/6 px-4">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onTabChange("prompt")}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeTab === "prompt" ? "bg-black text-white" : "border border-black/8 bg-white"
              }`}
            >
              提示词
            </button>
            <button
              type="button"
              onClick={() => onTabChange("images")}
              className={`rounded-md px-3 py-1.5 text-sm ${
                activeTab === "images" ? "bg-black text-white" : "border border-black/8 bg-white"
              }`}
            >
              生成图片
            </button>
          </div>
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex size-8 items-center justify-center rounded-md border border-black/8 bg-white text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
            aria-label="折叠工作区"
          >
            <PanelRightClose className="size-4" />
          </button>
        </div>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          {activeTab === "prompt" ? (
            <PromptReferenceTab sessionId={sessionId} />
          ) : (
            <div className="px-4 py-4">
              {generationPreviews.length === 0 ? (
                <div className="rounded-xl border border-dashed border-black/8 p-4 text-sm text-muted-foreground">
                  生成结果会在这里出现
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {generationPreviews.map((item) => (
                    <div
                      key={item.taskId}
                      className="overflow-hidden rounded-xl border border-black/8 bg-white"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={item.imageUrl}
                        alt="生成结果"
                        className="h-44 w-full object-cover"
                      />
                      <div className="border-t border-black/6 px-3 py-2 text-xs text-muted-foreground">
                        {item.taskId}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
