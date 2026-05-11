from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP

import config
from core.milvus_client import MilvusImageLibraryClient
from core.pg_client import ImageLibraryPGClient


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


if __name__ == "__main__":
    mcp.run("stdio")
