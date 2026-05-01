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


async def save_upload(file: UploadFile) -> tuple[str, str]:
    validate_image_mime_type(file.content_type)

    if settings.STORAGE == "minio":
        raise NotImplementedError("MinIO storage is not implemented yet")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid4())
    suffix = _suffix_from_content_type(file.content_type or "")
    filename = f"{file_id}{suffix}"
    file_path = upload_dir / filename

    content = await file.read()
    file_path.write_bytes(content)

    return file_id, f"/static/uploads/{filename}"
