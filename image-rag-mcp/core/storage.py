"""Storage for the RAG image library.

image-rag-mcp owns a copy of every image stored via store_generated_image so
the library is not coupled to upstream lifecycle. Files always live under
``library_images/{image_id}.{ext}`` for local embedding/search, and can also be
published to MinIO so Milvus/Attu stores a browser-openable URL.
"""
import base64
import datetime as dt
import hashlib
import hmac
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

import httpx

import config

_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<b64>.+)$", re.DOTALL)
_LIBRARY_URL_PREFIX = "/static/library/"
_DOWNLOAD_TIMEOUT = 60.0
_S3_REGION = "us-east-1"
_S3_SERVICE = "s3"


def get_library_dir() -> Path:
    path = config.get_library_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def library_url_for(image_id: str, ext: str) -> str:
    if config.get_image_library_storage() == "minio":
        key = _object_key(image_id, ext)
        return f"{config.get_minio_public_endpoint()}/{config.get_minio_bucket()}/{quote(key)}"
    return f"{_LIBRARY_URL_PREFIX}{image_id}.{ext.lstrip('.')}"


def resolve_library_url(url: str) -> Path | None:
    """If ``url`` points at our library copy, return the local file."""
    if not isinstance(url, str):
        return None

    minio_prefix = f"{config.get_minio_public_endpoint()}/{config.get_minio_bucket()}/"
    if url.startswith(minio_prefix):
        name = url[len(minio_prefix):]
        if "/" in name or ".." in name or not name:
            return None
        path = get_library_dir() / name
        return path if path.exists() else None

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


async def publish_library_object(local_path: Path, image_id: str, ext: str) -> str:
    """Publish a library copy and return the URL stored in PG/Milvus."""
    stored_url = library_url_for(image_id, ext)
    if config.get_image_library_storage() != "minio":
        return stored_url

    await _ensure_minio_bucket()
    key = _object_key(image_id, ext)
    mime, _ = mimetypes.guess_type(str(local_path))
    await _s3_request(
        "PUT",
        f"/{config.get_minio_bucket()}/{key}",
        content=local_path.read_bytes(),
        headers={"content-type": mime or "application/octet-stream"},
    )
    return stored_url


async def delete_published_library_object(image_id: str, ext: str) -> None:
    if config.get_image_library_storage() != "minio":
        return
    try:
        await _s3_request("DELETE", f"/{config.get_minio_bucket()}/{_object_key(image_id, ext)}")
    except Exception:
        return


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


def _object_key(image_id: str, ext: str) -> str:
    return f"{image_id}.{ext.lstrip('.')}"


async def _ensure_minio_bucket() -> None:
    bucket = config.get_minio_bucket()
    try:
        await _s3_request("HEAD", f"/{bucket}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        await _s3_request("PUT", f"/{bucket}")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            }
        ],
    }
    await _s3_request(
        "PUT",
        f"/{bucket}",
        query="policy=",
        content=json.dumps(policy, separators=(",", ":")).encode(),
        headers={"content-type": "application/json"},
    )


async def _s3_request(
    method: str,
    path: str,
    *,
    query: str = "",
    content: bytes = b"",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    endpoint = config.get_minio_endpoint()
    parsed_host = endpoint.split("://", 1)[-1]
    request_headers = {k.lower(): v for k, v in (headers or {}).items()}
    request_headers.setdefault("host", parsed_host)
    request_headers.setdefault("x-amz-content-sha256", hashlib.sha256(content).hexdigest())
    now = dt.datetime.now(dt.timezone.utc)
    request_headers["x-amz-date"] = now.strftime("%Y%m%dT%H%M%SZ")

    authorization = _authorization_header(method, path, query, request_headers, now)
    request_headers["authorization"] = authorization

    url = f"{endpoint}{path}"
    if query:
        url = f"{url}?{query}"
    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as client:
        resp = await client.request(method, url, content=content, headers=request_headers)
        resp.raise_for_status()
        return resp


def _authorization_header(
    method: str,
    path: str,
    query: str,
    headers: dict[str, str],
    now: dt.datetime,
) -> str:
    signed_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name].strip()}\n" for name in signed_names)
    signed_headers = ";".join(signed_names)
    payload_hash = headers["x-amz-content-sha256"]
    canonical_request = "\n".join([
        method,
        quote(path, safe="/"),
        query,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    date = now.strftime("%Y%m%d")
    scope = f"{date}/{_S3_REGION}/{_S3_SERVICE}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        headers["x-amz-date"],
        scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])
    signing_key = _signing_key(config.get_minio_secret_key(), date)
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return (
        f"AWS4-HMAC-SHA256 Credential={config.get_minio_access_key()}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


def _signing_key(secret: str, date: str) -> bytes:
    key = hmac.new(f"AWS4{secret}".encode(), date.encode(), hashlib.sha256).digest()
    key = hmac.new(key, _S3_REGION.encode(), hashlib.sha256).digest()
    key = hmac.new(key, _S3_SERVICE.encode(), hashlib.sha256).digest()
    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"
