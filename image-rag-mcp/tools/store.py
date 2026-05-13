"""store_generated_image: persist an image into the RAG library.

Pipeline:
  1. Download the source image into ``library_images/{image_id}.{ext}`` so the
     library owns its own copy (decoupled from backend/generated lifecycle).
  2. Generate VLM caption for the local file (data URL).
  3. Embed caption -> caption_vector (2048-d).
  4. Embed image   -> image_vector   (2048-d).
  5. Insert PG row + Milvus entity, storing the configured library URL. In
     local mode this is ``/static/library/...``; in MinIO mode it is a public
     MinIO HTTP URL that can be opened from Attu/Milvus.

Scalar fields (style / building_type) are extracted from design_state so the
caller does not have to pass them separately.
"""
import uuid
from typing import Any

import config
from core.embedding.factory import ImageEmbeddingFactory, TextEmbeddingFactory
from core.milvus_client import MilvusImageLibraryClient
from core.pg_client import ImageLibraryPGClient
from core.storage import (
    delete_published_library_object,
    publish_library_object,
    save_source_url,
    to_data_url,
)
from core.vlm_caption import generate_caption


async def store_generated_image(
    *,
    pg: ImageLibraryPGClient,
    milvus: MilvusImageLibraryClient,
    image_url: str,
    session_id: str | None,
    prompt: str,
    negative_prompt: str | None = None,
    design_state: dict[str, Any] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    api_key = config.get_embedding_api_key()
    if not api_key:
        raise RuntimeError("embedding.api_key missing in dashboard.yaml")

    image_id = str(uuid.uuid4())

    local_path, ext = await save_source_url(image_url, image_id)
    stored_url = ""
    try:
        local_data_url = to_data_url(local_path)
        stored_url = await publish_library_object(local_path, image_id, ext)

        caption = await generate_caption(local_data_url)

        text_client = TextEmbeddingFactory.create("volcengine", api_key)
        image_client = ImageEmbeddingFactory.create("volcengine", api_key)
        caption_vec = await text_client.embed(caption)
        image_vec = await image_client.embed_image(local_data_url)

        style = str((design_state or {}).get("style") or "")
        building_type = str((design_state or {}).get("building_type") or "")

        await pg.insert(
            image_id=image_id,
            session_id=session_id,
            image_url=stored_url,
            caption=caption,
            prompt=prompt,
            negative_prompt=negative_prompt,
            design_state=design_state,
            provider=provider,
        )
        await milvus.insert(
            image_id=image_id,
            caption=caption,
            caption_vector=caption_vec,
            image_vector=image_vec,
            style=style,
            building_type=building_type,
            image_url=stored_url,
        )
    except Exception:
        # Library copy is orphaned if PG/Milvus insert fails — clean it up so
        # the filesystem stays consistent with the index.
        await delete_published_library_object(image_id, ext)
        local_path.unlink(missing_ok=True)
        raise

    return {"image_id": image_id, "caption": caption, "image_url": stored_url}
