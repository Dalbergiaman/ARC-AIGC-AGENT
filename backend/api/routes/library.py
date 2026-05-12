from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from services import library_service
from services.storage_service import download_and_save_library_image

router = APIRouter(prefix="/api/library", tags=["library"])


# rag_gate uses this key to detect a user pick; TTL slightly above the blocking
# timeout so the key cannot outlive a single rag_gate cycle.
RAG_PICK_KEY = "rag_pick:{session_id}:{run_id}"
RAG_PICK_SKIP_VALUE = ""
_RAG_PICK_TTL_PADDING = 60


class StoreRequest(BaseModel):
    image_url: str
    prompt: str
    session_id: str | None = None
    negative_prompt: str | None = None
    design_state: dict[str, Any] | None = None
    provider: str | None = None


class SelectRequest(BaseModel):
    image_id: str


class SelectResponse(BaseModel):
    file_id: str
    url: str


class PickRequest(BaseModel):
    session_id: str
    run_id: str
    image_id: str | None = None  # None means user clicked "skip"


@router.post("/store")
async def store_image(request: Request, body: StoreRequest) -> dict[str, Any]:
    client = getattr(request.app.state, "mcp_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="image-rag MCP client is not ready")
    try:
        return await library_service.store_image(
            client,
            image_url=body.image_url,
            prompt=body.prompt,
            session_id=body.session_id,
            negative_prompt=body.negative_prompt,
            design_state=body.design_state,
            provider=body.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP store failed: {exc}") from exc


@router.post("/select", response_model=SelectResponse)
async def select_image(request: Request, body: SelectRequest) -> SelectResponse:
    client = getattr(request.app.state, "mcp_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="image-rag MCP client is not ready")

    record = await library_service.get_image_by_id(client, image_id=body.image_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"image_id {body.image_id} not found")

    source_url = record.get("image_url")
    if not source_url:
        raise HTTPException(status_code=500, detail="library record has no image_url")

    try:
        file_id, url = await download_and_save_library_image(source_url)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return SelectResponse(file_id=file_id, url=url)


@router.post("/pick")
async def pick_candidate(body: PickRequest) -> dict[str, Any]:
    """Record the user's choice from the rag_candidates popup.

    rag_gate_node polls this key while blocking the run. Value is either the
    chosen image_id or an empty string sentinel for skip.
    """
    key = RAG_PICK_KEY.format(session_id=body.session_id, run_id=body.run_id)
    value = body.image_id if body.image_id else RAG_PICK_SKIP_VALUE
    ttl = settings.RAG_BLOCKING_TIMEOUT + _RAG_PICK_TTL_PADDING
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await r.set(key, value, ex=ttl)
    finally:
        await r.aclose()
    return {"ok": True, "picked": body.image_id or None}
