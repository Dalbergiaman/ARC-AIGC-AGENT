"""End-to-end stdio smoke for D-3 MCP tools.

Pipeline:
  1. Boot server.py via stdio_client, list_tools should include the 5 tools.
  2. store_generated_image x 2  -> get two image_ids.
  3. Verify library_images/{image_id}.{ext} was created on disk.
  4. Verify PG/Milvus image_url uses the configured library storage URL.
  5. search_by_text("modern villa") -> at least one of the stored hits.
  6. search_by_image passing the stored short URL -> self-match (top result).
  7. get_image_by_id(stored_id) -> returns the prompt we wrote in step 2.
  8. Cleanup: drop rows from PG + Milvus + library files.

Uses real images from backend/generated/ as data URLs (volcengine cannot fetch
external URLs from outside CN).
"""
import asyncio
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from pymilvus import connections, utility, Collection  # noqa: E402
import asyncpg  # noqa: E402

import config  # noqa: E402
from core.storage import delete_published_library_object  # noqa: E402

_GENERATED_DIR = ROOT.parent / "backend" / "generated"
_LIBRARY_DIR = ROOT / "library_images"


def _is_expected_library_url(url: str) -> bool:
    if config.get_image_library_storage() == "minio":
        prefix = f"{config.get_minio_public_endpoint()}/{config.get_minio_bucket()}/"
        return url.startswith(prefix)
    return url.startswith("/static/library/")


def _to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _parse_tool_result(result) -> object:
    """FastMCP returns dicts via text content + structuredContent; lists only
    via structuredContent wrapped as {"result": [...]}."""
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    for block in result.content:
        if hasattr(block, "text"):
            return json.loads(block.text)
    return None


async def _cleanup(image_ids: list[str]) -> None:
    if not image_ids:
        return
    pool = await asyncpg.create_pool(config.get_pg_dsn(), min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM image_library WHERE id = ANY($1::uuid[])", image_ids
            )
    finally:
        await pool.close()

    connections.connect(alias="cleanup", host=config.get_milvus_host(), port=config.get_milvus_port())
    try:
        if utility.has_collection(config.COLLECTION_NAME, using="cleanup"):
            coll = Collection(config.COLLECTION_NAME, using="cleanup")
            quoted = ", ".join(f'"{i}"' for i in image_ids)
            coll.delete(f"image_id in [{quoted}]")
            coll.flush()
    finally:
        connections.disconnect("cleanup")

    for image_id in image_ids:
        for p in _LIBRARY_DIR.glob(f"{image_id}.*"):
            await delete_published_library_object(image_id, p.suffix.lstrip("."))
            p.unlink(missing_ok=True)


async def main() -> None:
    images = sorted(_GENERATED_DIR.glob("*.png"))[:2]
    if len(images) < 2:
        raise RuntimeError(f"need >=2 images in {_GENERATED_DIR}, got {len(images)}")

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )

    stored_ids: list[str] = []

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                print("tools:", sorted(names))
                assert {"store_generated_image", "search_by_text", "search_by_image", "get_image_by_id"} <= names

                # 1. store two images with different design_state
                samples = [
                    {
                        "path": images[0],
                        "prompt": "modern minimal villa with floor-to-ceiling glass facade",
                        "design_state": {"style": "modern_minimal", "building_type": "villa"},
                        "provider": "grsai",
                    },
                    {
                        "path": images[1],
                        "prompt": "industrial office tower with steel and concrete facade",
                        "design_state": {"style": "industrial", "building_type": "office"},
                        "provider": "grsai",
                    },
                ]
                stored: list[dict] = []
                for s in samples:
                    print(f"[store] {s['path'].name} ...")
                    res = await session.call_tool(
                        "store_generated_image",
                        {
                            "image_url": _to_data_url(s["path"]),
                            "prompt": s["prompt"],
                            "design_state": s["design_state"],
                            "provider": s["provider"],
                        },
                    )
                    payload = _parse_tool_result(res)
                    print("   ->", {k: payload[k] for k in ("image_id", "image_url")})
                    assert payload and payload.get("image_id"), "store returned no image_id"
                    assert _is_expected_library_url(payload["image_url"]), (
                        f"stored URL should match storage mode, got {payload['image_url']!r}"
                    )
                    stored.append({**s, "image_id": payload["image_id"], "caption": payload["caption"], "stored_url": payload["image_url"]})
                    stored_ids.append(payload["image_id"])

                    # 1a. library file must exist on disk
                    local_files = list(_LIBRARY_DIR.glob(f"{payload['image_id']}.*"))
                    assert len(local_files) == 1, f"expected exactly 1 library file, got {local_files}"
                    print(f"   library_file: {local_files[0].name} ({local_files[0].stat().st_size} bytes)")

                # 2. search_by_text
                print("[search_by_text] 'modern villa with glass facade'")
                res = await session.call_tool(
                    "search_by_text",
                    {"query": "modern villa with glass facade", "top_k": 5},
                )
                hits = _parse_tool_result(res)
                print(f"   hits: {len(hits)}, first score={hits[0]['score'] if hits else None}")
                assert hits, "no search hits"
                top_ids = [h["image_id"] for h in hits]
                assert stored[0]["image_id"] in top_ids, "modern villa not retrieved"
                # returned image_url must match configured library storage.
                assert all(_is_expected_library_url(h["image_url"]) for h in hits if h["image_id"] in stored_ids), (
                    "search hits missing expected library URL"
                )

                # 2b. search_by_text + filter
                print("[search_by_text] with filter style=industrial")
                res = await session.call_tool(
                    "search_by_text",
                    {"query": "office tower", "top_k": 5, "filters": {"style": "industrial"}},
                )
                hits = _parse_tool_result(res)
                print(f"   filtered hits: {len(hits)}")
                assert all(h["style"] == "industrial" for h in hits), "filter not applied"
                assert stored[1]["image_id"] in [h["image_id"] for h in hits]

                # 3. search_by_image passing the stored short URL (exercises
                #    local-path resolution on the MCP side)
                print(f"[search_by_image] self-query using {stored[0]['stored_url']}")
                res = await session.call_tool(
                    "search_by_image",
                    {"image_url": stored[0]["stored_url"], "top_k": 3},
                )
                hits = _parse_tool_result(res)
                print(f"   hits: {len(hits)}; top score={hits[0]['score']}, id={hits[0]['image_id']}")
                assert hits[0]["image_id"] == stored[0]["image_id"], "self-search did not return self at top"

                # 4. get_image_by_id
                print("[get_image_by_id]")
                res = await session.call_tool(
                    "get_image_by_id",
                    {"image_id": stored[0]["image_id"]},
                )
                row = _parse_tool_result(res)
                print("   row keys:", sorted(row.keys()))
                assert row["prompt"] == stored[0]["prompt"]
                assert row["design_state"]["style"] == "modern_minimal"
                assert row["caption"] == stored[0]["caption"]
                assert _is_expected_library_url(row["image_url"]), (
                    f"PG image_url should match storage mode, got {row['image_url']!r}"
                )

                print("OK — all D-3 tools verified")
    finally:
        if stored_ids:
            print(f"[cleanup] removing {len(stored_ids)} rows from PG+Milvus+library")
            await _cleanup(stored_ids)


if __name__ == "__main__":
    asyncio.run(main())
