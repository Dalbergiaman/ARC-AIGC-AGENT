"""get_image_by_id: fetch full PG row for an image_id."""
from typing import Any

from core.pg_client import ImageLibraryPGClient


async def get_image_by_id(
    *,
    pg: ImageLibraryPGClient,
    image_id: str,
) -> dict[str, Any] | None:
    return await pg.get_by_id(image_id)
