from base64 import b64decode
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
from fastapi import UploadFile

from config import settings

_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_BACKEND_ORIGIN = "http://localhost:8000"


def validate_image_mime_type(content_type: str | None) -> None:
    if content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError("Unsupported file type. Only JPEG, PNG and WEBP are allowed.")


def _suffix_from_content_type(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    return ".webp"


def _ensure_local_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _ensure_generated_dir() -> Path:
    generated_dir = Path(settings.GENERATED_DIR)
    generated_dir.mkdir(parents=True, exist_ok=True)
    return generated_dir


def _save_bytes(content: bytes, suffix: str) -> tuple[str, str]:
    upload_dir = _ensure_local_upload_dir()
    file_id = str(uuid4())
    filename = f"{file_id}{suffix}"
    file_path = upload_dir / filename
    file_path.write_bytes(content)
    return file_id, f"/static/uploads/{filename}"


async def save_upload(file: UploadFile) -> tuple[str, str]:
    validate_image_mime_type(file.content_type)

    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    content = await file.read()
    suffix = _suffix_from_content_type(file.content_type or "")
    return _save_bytes(content, suffix)


def _resolve_library_short_url(url: str) -> tuple[str, Path | None]:
    """Resolve a /static/library/... short URL to both a fetchable URL and
    an on-disk path (if the short URL can be mapped locally).

    Returns (fetch_url, local_path_or_none). For absolute HTTP URLs the local
    path is None and the caller falls back to HTTP download.
    """
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        return url, None
    if url.startswith("/static/library/"):
        filename = url[len("/static/library/"):]
        local_path = Path(settings.IMAGE_LIBRARY_DIR) / filename
        return urljoin(_BACKEND_ORIGIN, url), local_path
    return url, None


async def download_and_save_generated_image(url: str) -> str:
    """Download a cloud-provider image URL and persist it locally under /static/generated/."""
    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        content_type = "image/jpeg"

    generated_dir = _ensure_generated_dir()
    filename = f"{uuid4()}{_suffix_from_content_type(content_type)}"
    (generated_dir / filename).write_bytes(resp.content)
    return f"/static/generated/{filename}"


async def download_and_save_library_image(url: str) -> tuple[str, str]:
    """Copy an image from the RAG library into backend/uploads/.

    Accepts either an absolute HTTP URL or a short ``/static/library/{id}.{ext}``
    URL — short URLs are resolved directly from the library directory on disk,
    falling back to HTTP if the file is missing. Returns ``(file_id, /static/uploads/...)``.
    """
    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    fetch_url, local_path = _resolve_library_short_url(url)

    if local_path is not None and local_path.exists():
        suffix = local_path.suffix or ".jpg"
        return _save_bytes(local_path.read_bytes(), suffix)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(fetch_url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        content_type = "image/jpeg"
    return _save_bytes(resp.content, _suffix_from_content_type(content_type))


def delete_upload(file_id: str) -> bool:
    """Delete an uploaded file by its file_id (UUID). Returns True if deleted."""
    upload_dir = Path(settings.UPLOAD_DIR)
    for path in upload_dir.glob(f"{file_id}.*"):
        path.unlink(missing_ok=True)
        return True
    return False


def save_generated_image_base64(base64_data: str, content_type: str = "image/png") -> str:
    validate_image_mime_type(content_type)

    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    generated_dir = _ensure_generated_dir()
    filename = f"{uuid4()}{_suffix_from_content_type(content_type)}"
    (generated_dir / filename).write_bytes(b64decode(base64_data))
    return f"/static/generated/{filename}"
