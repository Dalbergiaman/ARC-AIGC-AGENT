"use client";

import { useRef } from "react";
import { X, Upload, Loader2 } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api";
import { useWorkspaceStore } from "@/store/workspaceStore";
import type { ReferenceIntent } from "@/lib/types";

const INTENT_LABELS: Record<ReferenceIntent, string> = {
  composition: "构图",
  color: "色彩",
  style: "建筑样式",
  material: "材质",
  lighting: "光线",
  surroundings: "环境",
  other: "其他",
};

const INTENT_OPTIONS = Object.entries(INTENT_LABELS) as [ReferenceIntent, string][];

type Props = {
  sessionId: string;
};

export function PromptReferenceTab({ sessionId }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    promptDraft,
    negativePromptDraft,
    getReferenceImages,
    setPromptDraft,
    setNegativePromptDraft,
    addReferenceImage,
    updateReferenceImage,
    removeReferenceImage,
  } = useWorkspaceStore();

  const referenceImages = getReferenceImages(sessionId);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    e.target.value = "";

    for (const file of files) {
      const tempId = `uploading-${crypto.randomUUID()}`;
      addReferenceImage(sessionId, { fileId: tempId, url: "", intent: "composition", uploading: true });

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch(`${getApiBaseUrl()}/api/upload`, {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const msg = await res.text();
          updateReferenceImage(sessionId, tempId, { uploading: false, error: msg || "上传失败" });
          continue;
        }
        const data = (await res.json()) as { file_id: string; url: string };
        updateReferenceImage(sessionId, tempId, {
          fileId: data.file_id,
          url: data.url,
          uploading: false,
        });
      } catch {
        updateReferenceImage(sessionId, tempId, { uploading: false, error: "网络错误" });
      }
    }
  }

  return (
    <div className="flex flex-col gap-5 px-4 py-4">
      {/* Prompt section */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">正向提示词</span>
          {promptDraft && (
            <button
              type="button"
              onClick={() => setPromptDraft("")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              清空
            </button>
          )}
        </div>
        <textarea
          value={promptDraft}
          onChange={(e) => setPromptDraft(e.target.value)}
          placeholder="Agent 生成的提示词会显示在这里，你也可以手动编辑"
          rows={4}
          className="w-full resize-none rounded-xl border border-black/8 bg-white px-3 py-2.5 text-sm leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-black/20"
        />

        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">负向提示词</span>
          {negativePromptDraft && (
            <button
              type="button"
              onClick={() => setNegativePromptDraft("")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              清空
            </button>
          )}
        </div>
        <textarea
          value={negativePromptDraft}
          onChange={(e) => setNegativePromptDraft(e.target.value)}
          placeholder="不希望出现的元素"
          rows={2}
          className="w-full resize-none rounded-xl border border-black/8 bg-white px-3 py-2.5 text-sm leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-black/20"
        />
      </div>

      {/* Reference images section */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">参考图</span>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center gap-1 rounded-lg border border-black/8 bg-white px-2.5 py-1 text-xs text-foreground hover:bg-black/[0.04]"
          >
            <Upload className="size-3" />
            上传
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        {referenceImages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-black/8 px-4 py-6 text-center text-xs text-muted-foreground">
            上传参考图后选择参考意图，随下一条消息发给 Agent
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {referenceImages.map((img) => (
              <div
                key={img.fileId}
                className="flex gap-3 rounded-xl border border-black/8 bg-white p-3"
              >
                {/* Thumbnail */}
                <div className="relative size-16 shrink-0 overflow-hidden rounded-lg bg-black/[0.04]">
                  {img.uploading ? (
                    <div className="flex size-full items-center justify-center">
                      <Loader2 className="size-4 animate-spin text-muted-foreground" />
                    </div>
                  ) : img.error ? (
                    <div className="flex size-full items-center justify-center px-1 text-center text-[10px] text-red-500">
                      {img.error}
                    </div>
                  ) : (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={`${getApiBaseUrl()}${img.url}`}
                      alt="参考图"
                      className="size-full object-cover"
                    />
                  )}
                  {img.sent && (
                    <div className="absolute bottom-0 left-0 right-0 bg-black/50 px-1 py-0.5 text-center text-[9px] text-white">
                      已发送
                    </div>
                  )}
                </div>

                {/* Controls */}
                <div className="flex min-w-0 flex-1 flex-col gap-2">
                  <select
                    value={img.intent}
                    disabled={img.uploading || img.sent}
                    onChange={(e) =>
                      updateReferenceImage(sessionId, img.fileId, { intent: e.target.value as ReferenceIntent })
                    }
                    className="w-full rounded-lg border border-black/8 bg-white px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-black/20 disabled:opacity-50"
                  >
                    {INTENT_OPTIONS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={img.note ?? ""}
                    disabled={img.uploading || img.sent}
                    placeholder="补充说明（可选）"
                    onChange={(e) =>
                      updateReferenceImage(sessionId, img.fileId, { note: e.target.value })
                    }
                    className="w-full rounded-lg border border-black/8 bg-white px-2 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-black/20 disabled:opacity-50"
                  />
                </div>

                {/* Remove */}
                <button
                  type="button"
                  onClick={() => removeReferenceImage(sessionId, img.fileId)}
                  className="self-start rounded-md p-0.5 text-muted-foreground hover:text-foreground"
                  aria-label="删除参考图"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
