"use client";

import { useRef, useState } from "react";
import { CheckCircle2, ImagePlus, Loader2, Upload, XCircle } from "lucide-react";

import { getApiBaseUrl, storeImageToLibrary, uploadImage } from "@/lib/api";

type Props = {
  sessionId: string;
};

type UploadStatus = "idle" | "uploading" | "storing" | "done" | "error";

type UploadResult = {
  fileName: string;
  previewUrl: string;
  imageId?: string;
  libraryUrl?: string;
  error?: string;
};

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

export function ManualLibraryUploadTab({ sessionId }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [result, setResult] = useState<UploadResult | null>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const localPreviewUrl = URL.createObjectURL(file);
    setResult({ fileName: file.name, previewUrl: localPreviewUrl });
    setStatus("uploading");

    try {
      const uploaded = await uploadImage(file);
      const uploadedUrl = resolveImageUrl(uploaded.url);
      URL.revokeObjectURL(localPreviewUrl);
      setResult({ fileName: file.name, previewUrl: uploadedUrl });
      setStatus("storing");

      const stored = await storeImageToLibrary({
        image_url: uploadedUrl,
        prompt: "手动上传图库图片",
        session_id: sessionId,
        provider: "manual_upload",
      });

      setResult({
        fileName: file.name,
        previewUrl: uploadedUrl,
        imageId: stored.image_id,
        libraryUrl: stored.image_url,
      });
      setStatus("done");
    } catch (error) {
      setResult({
        fileName: file.name,
        previewUrl: localPreviewUrl,
        error: error instanceof Error ? error.message : "上传图库失败",
      });
      setStatus("error");
    }
  }

  const busy = status === "uploading" || status === "storing";

  return (
    <div className="flex flex-col gap-4 px-4 py-4">
      <div className="rounded-lg border border-dashed border-black/10 bg-white px-4 py-5">
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-black/[0.04] text-muted-foreground">
            <ImagePlus className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-foreground">上传本地图片到图库</div>
            <div className="mt-1 text-xs leading-5 text-muted-foreground">
              支持 JPEG、PNG、WEBP，入库后用于 RAG 检索。
            </div>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-black/8 bg-white px-3 py-1.5 text-sm text-foreground hover:bg-black/[0.04] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
            上传
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      </div>

      {result ? (
        <div className="overflow-hidden rounded-lg border border-black/8 bg-white">
          <div className="bg-black/[0.04]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={result.previewUrl} alt="上传图库预览" className="h-auto w-full" />
          </div>
          <div className="flex flex-col gap-2 border-t border-black/6 px-3 py-3">
            <div className="truncate text-xs text-muted-foreground">{result.fileName}</div>
            {status === "uploading" && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                上传图片
              </div>
            )}
            {status === "storing" && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                写入 RAG 图库
              </div>
            )}
            {status === "done" && (
              <div className="flex flex-col gap-1 text-xs">
                <div className="flex items-center gap-1.5 font-medium text-green-700">
                  <CheckCircle2 className="size-3.5" />
                  已上传图库
                </div>
                {result.imageId && (
                  <div className="break-all text-muted-foreground">image_id: {result.imageId}</div>
                )}
                {result.libraryUrl && (
                  <div className="break-all text-muted-foreground">image_url: {result.libraryUrl}</div>
                )}
              </div>
            )}
            {status === "error" && (
              <div className="flex items-start gap-1.5 text-xs text-red-600">
                <XCircle className="mt-0.5 size-3.5 shrink-0" />
                <span className="break-words">{result.error ?? "上传图库失败"}</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-black/8 bg-white px-4 py-4 text-sm text-muted-foreground">
          选择图片后会自动上传并写入图库。
        </div>
      )}
    </div>
  );
}
