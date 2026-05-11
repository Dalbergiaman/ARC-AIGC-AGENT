"""Local file storage for the RAG image library.

image-rag-mcp owns a copy of every image stored via store_generated_image so
the library is not coupled to upstream lifecycle (generated/ uploads/ MinIO).
Files live under ``library_images/{image_id}.{ext}`` and are referenced by the
short URL ``/static/library/{image_id}.{ext}`` — the backend FastAPI mounts
this path as a static directory so the frontend can display it directly.
"""
import base64
import mimetypes
import re
from pathlib import Path

import httpx

import config

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<b64>.+)$", re.DOTALL)
_LIBRARY_URL_PREFIX = "/static/library/"
_DOWNLOAD_TIMEOUT = 60.0


def get_library_dir() -> Path:
    path = config.get_library_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def library_url_for(image_id: str, ext: str) -> str:
    return f"{_LIBRARY_URL_PREFIX}{image_id}.{ext.lstrip('.')}"


def resolve_library_url(url: str) -> Path | None:
    """If ``url`` is one of our short library URLs, return the local file."""
    if not isinstance(url, str):
        return None
    # Accept both absolute (http://host/static/library/..) and relative forms.
    marker = _LIBRARY_URL_PREFIX
    idx = url.find(marker)
    if idx < 0:
        return None
    name = url[idx + len(marker):]
    if "/" in name or ".." in name or not name:
        return None
    path = get_library_dir() / name
    return path if path.exists() else None


async def save_source_url(source_url: str, image_id: str) -> tuple[Path, str]:
    """Persist the bytes referenced by ``source_url`` into the library.

    Returns ``(local_path, ext)`` — caller uses ``library_url_for`` to build the
    short URL stored in PG/Milvus.
    """
    data, ext = await _fetch_bytes(source_url)
    target = get_library_dir() / f"{image_id}.{ext}"
    target.write_bytes(data)
    return target, ext


async def _fetch_bytes(url: str) -> tuple[bytes, str]:
    data_match = _DATA_URL_RE.match(url)
    if data_match:
        mime = data_match.group("mime")
        raw = base64.b64decode(data_match.group("b64"), validate=False)
        return raw, _ext_for_mime(mime)

    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    ext = _ext_from_url(url)
    if not ext:
        mime = (resp.headers.get("Content-Type") or "").split(";")[0].strip()
        ext = _ext_for_mime(mime)
    return resp.content, ext


def _ext_from_url(url: str) -> str | None:
    path = url.split("?", 1)[0].split("#", 1)[0]
    suffix = Path(path).suffix.lstrip(".").lower()
    if suffix in ("png", "jpg", "jpeg", "webp", "gif"):
        return "jpg" if suffix == "jpeg" else suffix
    return None


def _ext_for_mime(mime: str) -> str:
    mime = (mime or "").lower()
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    if mime in mapping:
        return mapping[mime]
    guessed = mimetypes.guess_extension(mime) if mime else None
    return (guessed or ".png").lstrip(".")


def to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"
