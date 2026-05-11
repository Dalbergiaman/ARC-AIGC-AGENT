import json
from typing import Any

import asyncpg


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS image_library (
    id              UUID PRIMARY KEY,
    session_id      UUID,
    image_url       TEXT NOT NULL,
    caption         TEXT,
    prompt          TEXT,
    negative_prompt TEXT,
    design_state    JSONB,
    provider        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


class ImageLibraryPGClient:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
            await self._init_schema()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("PG pool not initialized; call connect() first")
        return self._pool

    async def _init_schema(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)

    async def insert(
        self,
        *,
        image_id: str,
        session_id: str | None,
        image_url: str,
        caption: str | None,
        prompt: str | None,
        negative_prompt: str | None,
        design_state: dict[str, Any] | None,
        provider: str | None,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO image_library (
                    id, session_id, image_url, caption,
                    prompt, negative_prompt, design_state, provider
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                """,
                image_id,
                session_id,
                image_url,
                caption,
                prompt,
                negative_prompt,
                json.dumps(design_state) if design_state is not None else None,
                provider,
            )

    async def get_by_id(self, image_id: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM image_library WHERE id = $1",
                image_id,
            )
        return _row_to_dict(row)

    async def get_by_ids(self, image_ids: list[str]) -> list[dict[str, Any]]:
        if not image_ids:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM image_library WHERE id = ANY($1::uuid[])",
                image_ids,
            )
        return [item for row in rows if (item := _row_to_dict(row)) is not None]

    async def health_check(self) -> bool:
        async with self.pool.acquire() as conn:
            value = await conn.fetchval("SELECT 1")
        return value == 1


def _row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    if isinstance(data.get("id"), object) and data.get("id") is not None:
        data["id"] = str(data["id"])
    if isinstance(data.get("session_id"), object) and data.get("session_id") is not None:
        data["session_id"] = str(data["session_id"])
    raw_design = data.get("design_state")
    if isinstance(raw_design, str):
        try:
            data["design_state"] = json.loads(raw_design)
        except json.JSONDecodeError:
            pass
    return data
