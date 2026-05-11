"""search_by_text / search_by_image: query the RAG library.

Both return Milvus-only fields. Callers that need prompt/design_state can look
the image up via get_image_by_id.
"""
from typing import Any

import config
from core.embedding.factory import ImageEmbeddingFactory, TextEmbeddingFactory
from core.milvus_client import MilvusImageLibraryClient
from core.storage import resolve_library_url, to_data_url


async def search_by_text(
    *,
    milvus: MilvusImageLibraryClient,
    query: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    api_key = config.get_embedding_api_key()
    if not api_key:
        raise RuntimeError("embedding.api_key missing in dashboard.yaml")

    client = TextEmbeddingFactory.create("volcengine", api_key)
    vector = await client.embed(query)
    return await milvus.search(
        vector_field="caption_vector",
        query_vector=vector,
        top_k=top_k,
        filters=filters,
    )


async def search_by_image(
    *,
    milvus: MilvusImageLibraryClient,
    image_url: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    api_key = config.get_embedding_api_key()
    if not api_key:
        raise RuntimeError("embedding.api_key missing in dashboard.yaml")

    # If the URL points at our own library copy, read it locally and pass as a
    # data URL — our embedding provider cannot resolve relative /static paths.
    local_path = resolve_library_url(image_url)
    embed_input = to_data_url(local_path) if local_path else image_url

    client = ImageEmbeddingFactory.create("volcengine", api_key)
    vector = await client.embed_image(embed_input)
    return await milvus.search(
        vector_field="image_vector",
        query_vector=vector,
        top_k=top_k,
        filters=filters,
    )
