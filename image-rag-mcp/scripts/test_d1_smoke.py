"""Manual smoke test for D-1 scaffolding.

Runs the lifespan context manager outside of FastMCP stdio so we can verify:
  - asyncpg pool connects to aigc_image_library and image_library table is created
  - Milvus connects, image_library collection exists with required indexes
  - health_check returns sensible values
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from core.milvus_client import MilvusImageLibraryClient  # noqa: E402
from core.pg_client import ImageLibraryPGClient  # noqa: E402


async def main() -> None:
    pg = ImageLibraryPGClient(config.get_pg_dsn())
    milvus = MilvusImageLibraryClient(
        config.get_milvus_host(),
        config.get_milvus_port(),
    )

    await pg.connect()
    try:
        await milvus.connect()
        pg_ok = await pg.health_check()
        milvus_status = await milvus.health_check()
        print("PG ok:", pg_ok)
        print("Milvus:", milvus_status)

        async with pg.pool.acquire() as conn:
            cols = await conn.fetch(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'image_library'
                ORDER BY ordinal_position
                """
            )
            print("image_library columns:")
            for row in cols:
                print(" ", row["column_name"], row["data_type"])
    finally:
        await milvus.close()
        await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
