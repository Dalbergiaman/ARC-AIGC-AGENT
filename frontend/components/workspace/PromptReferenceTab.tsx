"use client";

import { useMemo, useRef } from "react";
import { Loader2, Upload, X } from "lucide-react";

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
    getReferenceImages,
    setPromptDraftField,
    setPromptDraft,
    addReferenceImage,
    updateReferenceImage,
    removeReferenceImage,
  } = useWorkspaceStore();

  const referenceImages = getReferenceImages(sessionId);
  const prettyDraft = useMemo(
    () => JSON.stringify(promptDraft, null, 2),
    [promptDraft],
  );

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
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">Prompt 草稿 JSON</span>
          <button
            type="button"
            onClick={() => setPromptDraft({
              keywords: {},
              llm_description: "",
              custom_description: "",
              negative_prompt: "",
            })}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            重置
          </button>
        </div>
        <pre className="max-h-72 overflow-auto rounded-xl border border-black/8 bg-white px-3 py-2.5 text-xs leading-5 text-foreground whitespace-pre-wrap break-words">
          {prettyDraft}
        </pre>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">custom_description</span>
          <span className="text-[11px] text-muted-foreground">用户可直接编辑的自由描述</span>
        </div>
        <textarea
          value={promptDraft.custom_description}
          onChange={(e) => setPromptDraftField("custom_description", e.target.value)}
          placeholder="在这里补充你希望模型严格遵守的画面描述"
          rows={5}
          className="w-full resize-none rounded-xl border border-black/8 bg-white px-3 py-2.5 text-sm leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-black/20"
        />
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">llm_description</span>
          <span className="text-[11px] text-muted-foreground">由 Agent 多轮对话整理</span>
        </div>
        <textarea
          value={promptDraft.llm_description}
          readOnly
          rows={4}
          className="w-full resize-none rounded-xl border border-black/8 bg-black/[0.02] px-3 py-2.5 text-sm leading-5 text-foreground focus:outline-none"
        />
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-foreground">负向提示词</span>
        </div>
        <textarea
          value={promptDraft.negative_prompt}
          onChange={(e) => setPromptDraftField("negative_prompt", e.target.value)}
          placeholder="不希望出现的元素"
          rows={2}
          className="w-full resize-none rounded-xl border border-black/8 bg-white px-3 py-2.5 text-sm leading-5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-black/20"
        />
      </div>

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
