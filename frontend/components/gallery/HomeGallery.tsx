"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

import { getApiBaseUrl, listGalleryImages, type GalleryImage } from "@/lib/api";

function resolveImageUrl(url: string): string {
  return url.startsWith("/") ? `${getApiBaseUrl()}${url}` : url;
}

type Preview = {
  url: string;
  from: { top: number; left: number; width: number; height: number };
};

export function HomeGallery() {
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    listGalleryImages()
      .then(setImages)
      .catch(() => setImages([]));
  }, []);

  useEffect(() => {
    if (!preview) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closePreview();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [preview]);

  function openPreview(e: React.MouseEvent<HTMLButtonElement>, url: string) {
    const rect = e.currentTarget.getBoundingClientRect();
    setPreview({
      url,
      from: {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      },
    });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setOpen(true));
    });
  }

  function closePreview() {
    setOpen(false);
    setTimeout(() => setPreview(null), 300);
  }

  async function handleDownload(url: string) {
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = url.split("/").pop() ?? "image.png";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
    } catch {
      window.open(url, "_blank");
    }
  }

  if (images.length === 0) return null;

  return (
    <>
      <div className="mx-auto w-full max-w-6xl columns-2 gap-3 px-8 md:columns-3 md:px-16 lg:columns-4 lg:px-24">
        {images.map((img) => {
          const full = resolveImageUrl(img.url);
          return (
            <button
              key={img.url}
              type="button"
              onClick={(e) => openPreview(e, full)}
              className="mb-3 block w-full break-inside-avoid overflow-hidden rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={full}
                alt=""
                loading="lazy"
                className="block h-auto w-full transition-transform hover:scale-[1.02]"
              />
            </button>
          );
        })}
      </div>

      {preview && (
        <div
          className="fixed inset-0 z-50"
          onClick={closePreview}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview.url}
            alt=""
            onClick={(e) => e.stopPropagation()}
            className="fixed rounded-md object-contain transition-all duration-300 ease-out"
            style={
              open
                ? {
                    top: "5vh",
                    left: "5vw",
                    width: "90vw",
                    height: "90vh",
                  }
                : {
                    top: `${preview.from.top}px`,
                    left: `${preview.from.left}px`,
                    width: `${preview.from.width}px`,
                    height: `${preview.from.height}px`,
                  }
            }
          />
          <div
            className="fixed right-6 top-6 flex gap-2 transition-opacity duration-300"
            style={{ opacity: open ? 1 : 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => handleDownload(preview.url)}
              aria-label="下载"
              className="rounded-md bg-white/90 p-2 shadow hover:bg-white"
            >
              <Download className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={closePreview}
              aria-label="关闭"
              className="rounded-md bg-white/90 p-2 shadow hover:bg-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
