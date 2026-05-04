from base64 import b64decode
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from config import settings

_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


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


def save_generated_image_base64(base64_data: str, content_type: str = "image/png") -> str:
    validate_image_mime_type(content_type)

    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    raw = b64decode(base64_data)
    _, url = _save_bytes(raw, _suffix_from_content_type(content_type))
    return url
