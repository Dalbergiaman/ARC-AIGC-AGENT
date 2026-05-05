from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from config import settings

_PG_URL = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def get_conn_string() -> str:
    return _PG_URL


async def init_checkpointer(saver: AsyncPostgresSaver) -> None:
    """Create LangGraph checkpoint tables. Call once at startup after entering the context."""
    await saver.setup()
