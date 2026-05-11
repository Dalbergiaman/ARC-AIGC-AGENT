from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP

import config
from core.milvus_client import MilvusImageLibraryClient
from core.pg_client import ImageLibraryPGClient
from tools.retrieve import get_image_by_id as _get_image_by_id
from tools.search import search_by_image as _search_by_image
from tools.search import search_by_text as _search_by_text
from tools.store import store_generated_image as _store_generated_image


@dataclass
class AppContext:
    pg: ImageLibraryPGClient
    milvus: MilvusImageLibraryClient


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    pg = ImageLibraryPGClient(config.get_pg_dsn())
    milvus = MilvusImageLibraryClient(config.get_milvus_host(), config.get_milvus_port())

    await pg.connect()
    try:
        await milvus.connect()
    except Exception:
        await pg.close()
        raise

    try:
        yield AppContext(pg=pg, milvus=milvus)
    finally:
        await milvus.close()
        await pg.close()


mcp = FastMCP("image-rag", lifespan=lifespan)


@mcp.tool()
async def health_check(ctx: Context) -> dict[str, Any]:
    """Verify PG pool and Milvus collection are reachable."""
    app: AppContext = ctx.request_context.lifespan_context
    pg_ok = await app.pg.health_check()
    milvus_status = await app.milvus.health_check()
    return {
        "pg": {"ok": pg_ok},
        "milvus": milvus_status,
    }


@mcp.tool()
async def store_generated_image(
    ctx: Context,
    image_url: str,
    prompt: str,
    session_id: str | None = None,
    negative_prompt: str | None = None,
    design_state: dict[str, Any] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Persist an image into the RAG library (VLM caption + dual embeddings)."""
    app: AppContext = ctx.request_context.lifespan_context
    return await _store_generated_image(
        pg=app.pg,
        milvus=app.milvus,
        image_url=image_url,
        session_id=session_id,
        prompt=prompt,
        negative_prompt=negative_prompt,
        design_state=design_state,
        provider=provider,
    )


@mcp.tool()
async def search_by_text(
    ctx: Context,
    query: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve similar images by text query against caption_vector."""
    app: AppContext = ctx.request_context.lifespan_context
    return await _search_by_text(
        milvus=app.milvus,
        query=query,
        top_k=top_k,
        filters=filters,
    )


@mcp.tool()
async def search_by_image(
    ctx: Context,
    image_url: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve similar images by image-to-image search against image_vector."""
    app: AppContext = ctx.request_context.lifespan_context
    return await _search_by_image(
        milvus=app.milvus,
        image_url=image_url,
        top_k=top_k,
        filters=filters,
    )


@mcp.tool()
async def get_image_by_id(
    ctx: Context,
    image_id: str,
) -> dict[str, Any] | None:
    """Fetch full PG row (prompt / design_state / provider) for an image_id."""
    app: AppContext = ctx.request_context.lifespan_context
    return await _get_image_by_id(pg=app.pg, image_id=image_id)


if __name__ == "__main__":
    mcp.run("stdio")
