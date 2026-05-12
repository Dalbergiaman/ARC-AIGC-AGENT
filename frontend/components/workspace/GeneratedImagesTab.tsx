"use client";

import { useState } from "react";
import { BookMarked, Download, ImageIcon, Loader2, Pencil, Save, X } from "lucide-react";

import { ImageAnnotationCanvas } from "@/components/workspace/ImageAnnotationCanvas";
import { deleteUpload, getApiBaseUrl, storeImageToLibrary } from "@/lib/api";
import type { GenerationPreview } from "@/lib/types";
import { useChatStore } from "@/store/chatStore";
import { useWorkspaceStore } from "@/store/workspaceStore";

type Props = {
  sessionId: string;
  generationPreviews: GenerationPreview[];
};

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

function getBestTaskId(previews: GenerationPreview[]): string | null {
  const scored = previews.filter((p) => typeof p.score === "number" && p.imageUrl);
  if (scored.length === 0) return null;
  return scored.reduce((best, p) => (p.score! > best.score! ? p : best)).taskId;
}

export function GeneratedImagesTab({ sessionId, generationPreviews }: Props) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [annotatingUrl, setAnnotatingUrl] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [storingTaskId, setStoringTaskId] = useState<string | null>(null);
  const [storeError, setStoreError] = useState<string | null>(null);
  const bestTaskId = getBestTaskId(generationPreviews);
  const { upsertGenerationPreview } = useChatStore();
  const {
    getAnnotatedImage,
    setAnnotatedImage,
    updateAnnotatedImage,
    removeAnnotatedImage,
  } = useWorkspaceStore();
  const annotatedImage = getAnnotatedImage(sessionId);

  async function handleDownload(item: GenerationPreview) {
    if (!item.imageUrl) return;
    setDownloadError(null);
    try {
      const url = resolveImageUrl(item.imageUrl);
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error("图片下载失败");
      }
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = `${item.taskId || "generated-image"}.png`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "跨域限制导致下载失败");
    }
  }

  async function handleStore(item: GenerationPreview) {
    if (!item.imageUrl || storingTaskId || item.storedInLibrary) return;
    setStoreError(null);
    setStoringTaskId(item.taskId);
    try {
      await storeImageToLibrary({
        image_url: resolveImageUrl(item.imageUrl),
        prompt: item.prompt ?? "",
        session_id: sessionId,
        task_id: item.taskId,
        negative_prompt: item.negativePrompt ?? undefined,
        provider: item.provider ?? undefined,
      });
      upsertGenerationPreview({ ...item, storedInLibrary: true });
    } catch (error) {
      setStoreError(error instanceof Error ? error.message : "存入图库失败");
    } finally {
      setStoringTaskId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      {annotatedImage && (
        <div className="flex gap-3 rounded-lg border border-black/8 bg-white p-3">
          <div className="size-16 shrink-0 overflow-hidden rounded-md bg-black/[0.04]">
            {annotatedImage.error ? (
              <div className="flex size-full items-center justify-center px-1 text-center text-[10px] text-red-500">
                {annotatedImage.error}
              </div>
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={resolveImageUrl(annotatedImage.url)}
                alt="批注图"
                className="size-full object-cover"
              />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-2 text-xs font-medium">当前批注图</div>
            <textarea
              value={annotatedImage.note ?? ""}
              placeholder="批注说明（可选）"
              onChange={(event) => updateAnnotatedImage(sessionId, { note: event.target.value })}
              rows={2}
              className="w-full resize-none rounded-md border border-black/8 px-2 py-1.5 text-xs leading-5 focus:outline-none focus:ring-1 focus:ring-black/20"
            />
          </div>
          <button
            type="button"
            onClick={() => {
                deleteUpload(annotatedImage.fileId);
                removeAnnotatedImage(sessionId);
              }}
            className="self-start rounded-md p-0.5 text-muted-foreground hover:text-foreground"
            aria-label="清空批注图"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {downloadError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
          {downloadError}
        </div>
      )}

      {storeError && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
          {storeError}
        </div>
      )}

      {generationPreviews.length === 0 ? (
        <div className="rounded-lg border border-dashed border-black/8 p-4 text-sm text-muted-foreground">
          生成结果会在这里出现
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {generationPreviews.map((item) => {
            const imageUrl = item.imageUrl ? resolveImageUrl(item.imageUrl) : null;
            const status = item.status ?? (imageUrl ? "done" : "running");
            const failed = status === "failed" || status === "error";
            return (
              <div key={item.taskId} className="overflow-hidden rounded-lg border border-black/8 bg-white">
                <button
                  type="button"
                  disabled={!imageUrl}
                  onClick={() => imageUrl && setPreviewUrl(imageUrl)}
                  className="block w-full bg-black/[0.04] text-left disabled:cursor-default"
                >
                  {imageUrl ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img src={imageUrl} alt="生成结果" className="w-full h-auto" />
                  ) : failed ? (
                    <div className="flex h-32 items-center justify-center px-4 text-center text-sm text-red-500">
                      生成失败
                    </div>
                  ) : (
                    <div className="flex h-32 items-center justify-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" />
                      生成中
                    </div>
                  )}
                </button>
                <div className="flex flex-col gap-2 border-t border-black/6 px-3 py-2">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate text-muted-foreground">{item.taskId}</span>
                    <div className="flex shrink-0 items-center gap-1">
                      {typeof item.score === "number" && (
                        <span
                          className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${
                            item.taskId === bestTaskId
                              ? "bg-green-100 text-green-700"
                              : "bg-black/[0.04] text-muted-foreground"
                          }`}
                        >
                          {item.taskId === bestTaskId ? "最优 " : ""}
                          {(item.score * 100).toFixed(0)}分
                        </span>
                      )}
                      <span className="rounded bg-black/[0.04] px-1.5 py-0.5 text-[11px] text-muted-foreground">
                        {status}
                      </span>
                      {item.storedInLibrary && (
                        <span className="flex items-center gap-0.5 rounded bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-600">
                          <BookMarked className="size-3" />
                          已入库
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {item.provider && <span>{item.provider}</span>}
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    <button
                      type="button"
                      disabled={!imageUrl}
                      onClick={() => imageUrl && setAnnotatingUrl(imageUrl)}
                      className="inline-flex items-center justify-center rounded-md border border-black/8 py-1.5 text-muted-foreground hover:bg-black/[0.04] disabled:opacity-40"
                      title="批注"
                    >
                      <Pencil className="size-4" />
                    </button>
                    <button
                      type="button"
                      disabled={!imageUrl}
                      onClick={() => handleDownload(item)}
                      className="inline-flex items-center justify-center rounded-md border border-black/8 py-1.5 text-muted-foreground hover:bg-black/[0.04] disabled:opacity-40"
                      title="下载"
                    >
                      <Download className="size-4" />
                    </button>
                    <button
                      type="button"
                      disabled={!imageUrl || storingTaskId === item.taskId || item.storedInLibrary}
                      onClick={() => handleStore(item)}
                      className="inline-flex items-center justify-center rounded-md border border-black/8 py-1.5 text-muted-foreground hover:bg-black/[0.04] disabled:opacity-40"
                      title={item.storedInLibrary ? "已存入图库" : "存入图库"}
                    >
                      {storingTaskId === item.taskId ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Save className="size-4" />
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={!imageUrl}
                      onClick={() => imageUrl && setPreviewUrl(imageUrl)}
                      className="inline-flex items-center justify-center rounded-md border border-black/8 py-1.5 text-muted-foreground hover:bg-black/[0.04] disabled:opacity-40"
                      title="预览"
                    >
                      <ImageIcon className="size-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {previewUrl && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-6 py-6"
          onClick={() => setPreviewUrl(null)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt="生成结果大图"
            className="max-h-full max-w-full rounded-md bg-white object-contain"
          />
        </div>
      )}

      {annotatingUrl && (
        <ImageAnnotationCanvas
          imageUrl={annotatingUrl}
          onClose={() => setAnnotatingUrl(null)}
          onExport={(image) =>
            setAnnotatedImage(sessionId, {
              fileId: image.fileId,
              url: image.url,
              note: annotatedImage?.note ?? "",
              sent: false,
            })
          }
        />
      )}
    </div>
  );
}
