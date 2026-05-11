"""Gallery API routes: expose locally generated images for the home page."""
from __future__ import annotations

import os

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api/gallery")

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@router.get("/images")
def list_gallery_images() -> list[dict]:
    directory = settings.GENERATED_DIR
    if not os.path.isdir(directory):
        return []

    entries: list[tuple[str, float]] = []
    for name in os.listdir(directory):
        ext = os.path.splitext(name)[1].lower()
        if ext not in _ALLOWED_EXTS:
            continue
        path = os.path.join(directory, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        entries.append((name, mtime))

    entries.sort(key=lambda item: item[1], reverse=True)
    return [
        {"url": f"/static/generated/{name}", "mtime": mtime}
        for name, mtime in entries
    ]
