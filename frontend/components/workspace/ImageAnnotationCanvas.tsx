"use client";

import { useEffect, useRef, useState } from "react";
import { RotateCcw, Save, Trash2, X } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api";

type Props = {
  imageUrl: string;
  onClose: () => void;
  onExport: (image: { fileId: string; url: string }) => void;
};

type Point = { x: number; y: number };

export function ImageAnnotationCanvas({ imageUrl, onClose, onExport }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [strokes, setStrokes] = useState<Point[][]>([]);
  const [currentStroke, setCurrentStroke] = useState<Point[]>([]);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => setImage(img);
    img.onerror = () => setError("图片加载失败，无法批注");
    img.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = Math.max(8, Math.round(canvas.width * 0.006));
    ctx.strokeStyle = "#ef4444";

    [...strokes, currentStroke].forEach((stroke) => {
      if (stroke.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(stroke[0].x, stroke[0].y);
      stroke.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.stroke();
    });
  }, [currentStroke, image, strokes]);

  function getPoint(event: React.PointerEvent<HTMLCanvasElement>): Point {
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    };
  }

  function handlePointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    setCurrentStroke([getPoint(event)]);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    if (currentStroke.length === 0) return;
    const point = getPoint(event);
    setCurrentStroke((stroke) => [...stroke, point]);
  }

  function finishStroke() {
    setCurrentStroke((stroke) => {
      if (stroke.length > 1) {
        setStrokes((items) => [...items, stroke]);
      }
      return [];
    });
  }

  async function handleExport() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    setExporting(true);
    setError(null);

    try {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) {
        throw new Error("批注导出失败");
      }
      const form = new FormData();
      form.append("file", blob, `annotation-${Date.now()}.png`);
      const res = await fetch(`${getApiBaseUrl()}/api/upload`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        throw new Error(await res.text() || "上传批注图失败");
      }
      const data = (await res.json()) as { file_id: string; url: string };
      onExport({ fileId: data.file_id, url: data.url });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "批注图上传失败");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-6 py-6">
      <div className="flex max-h-full w-full max-w-5xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-black/8 px-4">
          <div className="text-sm font-medium">批注生成图</div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-black/[0.04] hover:text-foreground"
            aria-label="关闭批注"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-black/[0.03] p-4">
          {error && <div className="mb-3 text-sm text-red-500">{error}</div>}
          <canvas
            ref={canvasRef}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={finishStroke}
            onPointerCancel={finishStroke}
            className="mx-auto block max-h-[70vh] max-w-full touch-none rounded-md bg-white object-contain shadow-sm"
          />
        </div>
        <div className="flex h-14 shrink-0 items-center justify-between gap-3 border-t border-black/8 px-4">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setStrokes((items) => items.slice(0, -1))}
              disabled={strokes.length === 0}
              className="inline-flex items-center gap-1.5 rounded-md border border-black/8 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              <RotateCcw className="size-4" />
              撤销
            </button>
            <button
              type="button"
              onClick={() => setStrokes([])}
              disabled={strokes.length === 0}
              className="inline-flex items-center gap-1.5 rounded-md border border-black/8 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              <Trash2 className="size-4" />
              清空
            </button>
          </div>
          <button
            type="button"
            onClick={handleExport}
            disabled={!image || exporting}
            className="inline-flex items-center gap-1.5 rounded-md bg-black px-3 py-1.5 text-sm text-white disabled:opacity-40"
          >
            <Save className="size-4" />
            {exporting ? "导出中" : "导出批注图"}
          </button>
        </div>
      </div>
    </div>
  );
}
