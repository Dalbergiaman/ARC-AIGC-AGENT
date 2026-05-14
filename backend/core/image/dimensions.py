from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

from config import settings


DEFAULT_WIDTH = 2048
DEFAULT_HEIGHT = 1152
TARGET_LONG_EDGE = 2048
SIZE_MULTIPLE = 64


@dataclass(frozen=True)
class ImageCanvas:
    width: int
    height: int
    aspect_ratio: str
    source_width: int | None = None
    source_height: int | None = None
    source_url: str | None = None
    used_default: bool = False


def default_canvas() -> ImageCanvas:
    return ImageCanvas(
        width=DEFAULT_WIDTH,
        height=DEFAULT_HEIGHT,
        aspect_ratio="16:9",
        used_default=True,
    )


def canvas_from_image_url(image_url: str | None) -> ImageCanvas:
    path = local_path_from_image_url(image_url)
    if path is None:
        return default_canvas()

    try:
        source_width, source_height = read_image_size(path)
    except (OSError, UnidentifiedImageError, ValueError):
        return default_canvas()

    width, height = normalize_canvas_size(source_width, source_height)
    return ImageCanvas(
        width=width,
        height=height,
        aspect_ratio=aspect_ratio_string(source_width, source_height),
        source_width=source_width,
        source_height=source_height,
        source_url=image_url,
    )


def read_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image size: {width}x{height}")
    return width, height


def normalize_canvas_size(
    source_width: int,
    source_height: int,
    *,
    long_edge: int = TARGET_LONG_EDGE,
    multiple: int = SIZE_MULTIPLE,
) -> tuple[int, int]:
    if source_width <= 0 or source_height <= 0:
        raise ValueError(f"invalid image size: {source_width}x{source_height}")
    if long_edge <= 0 or multiple <= 0:
        raise ValueError("long_edge and multiple must be positive")

    if source_width >= source_height:
        width = long_edge
        height = round(source_height * long_edge / source_width)
    else:
        height = long_edge
        width = round(source_width * long_edge / source_height)

    return (
        max(multiple, _round_to_multiple(width, multiple)),
        max(multiple, _round_to_multiple(height, multiple)),
    )


def aspect_ratio_string(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid image size: {width}x{height}")
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def local_path_from_image_url(image_url: str | None) -> Path | None:
    if not image_url:
        return None

    path_part = image_url
    parsed = urlparse(image_url)
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            return None
        path_part = parsed.path

    local_dirs = {
        "/static/uploads/": Path(settings.UPLOAD_DIR),
        "/static/generated/": Path(settings.GENERATED_DIR),
    }
    for url_prefix, disk_dir in local_dirs.items():
        if path_part.startswith(url_prefix):
            filename = path_part[len(url_prefix):]
            path = disk_dir / filename
            if path.exists():
                return path
            return None
    return None


def _round_to_multiple(value: int, multiple: int) -> int:
    return max(multiple, int(round(value / multiple)) * multiple)
