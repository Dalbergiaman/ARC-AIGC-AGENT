"""Chat API routes.

POST /api/chat/sessions/{session_id}/messages
    Submit a user message. Returns {"stream_id": "<uuid>"}.
    stream_id == run_id — used for SSE isolation and cancel flag.

GET /api/chat/sessions/{session_id}/stream?stream_id=<uuid>
    Consume the SSE stream for the submitted message.
    Supports Last-Event-ID header for reconnection (replays buffered events).
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.llm.streaming import _parse_sse_chunk, stream_agent_events
from core.observability import (
    message_preview,
    set_current_trace_io,
    start_observation,
    update_current_span,
)
from models.database import get_session
from models.schemas import GenerationTask
from services.message_service import add_message, get_messages
from services.session_service import get_session as get_db_session
from services.session_service import create_generation_task, update_workspace_state, upsert_reference_images
from services.session_title_service import maybe_generate_session_title

router = APIRouter(prefix="/api/chat")

# Redis TTL for buffered SSE events (seconds)
_EVENT_BUFFER_TTL = 60
# Redis TTL for pending messages and active run markers (seconds)
_RUN_TTL = 300
# Redis key prefix for event buffers
_BUFFER_KEY = "sse_buffer:{session_id}:{stream_id}"
_ACTIVE_RUN_KEY = "active_run:{session_id}"
_CANCEL_KEY = "cancel:{session_id}:{stream_id}"


# ---------------------------------------------------------------------------
# Redis helper
# ---------------------------------------------------------------------------

def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _buffer_event(redis: aioredis.Redis, key: str, event_str: str) -> None:
    """Append a raw SSE string to the Redis list and refresh TTL."""
    await redis.rpush(key, event_str)
    await redis.expire(key, _EVENT_BUFFER_TTL)


async def _replay_events(
    redis: aioredis.Redis, key: str, last_event_id: int
) -> list[str]:
    """Return buffered events with id > last_event_id."""
    raw: list[str] = await redis.lrange(key, 0, -1)
    result = []
    for chunk in raw:
        # Extract id from the SSE chunk: "id: <n>\n"
        for line in chunk.splitlines():
            if line.startswith("id: "):
                try:
                    eid = int(line[4:].strip())
                except ValueError:
                    eid = 0
                if eid > last_event_id:
                    result.append(chunk)
                break
    return result


# ---------------------------------------------------------------------------
# POST — submit message
# ---------------------------------------------------------------------------

class ReferenceImagePayload(BaseModel):
    file_id: str
    url: str
    intent: str
    note: str = ""


class WorkspacePayload(BaseModel):
    keywords: dict[str, str] = Field(default_factory=dict)
    llm_description: str = ""
    custom_description: str = ""
    negative_prompt: str = ""
    prompt_template: dict | None = None


class MessageRequest(BaseModel):
    content: str
    reference_images: list[ReferenceImagePayload] = []
    workspace: WorkspacePayload | None = None


@router.post("/sessions/{session_id}/messages")
async def submit_message(
    session_id: uuid.UUID,
    body: MessageRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    session = await get_db_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    stream_id = str(uuid.uuid4())

    # Persist user message. The stream endpoint reads conversation history from
    # PostgreSQL, so the pending Redis key is only a stream_id handshake.
    message = await add_message(db, session_id, "user", body.content)

    # Store pending message in Redis so the SSE endpoint can pick it up
    r = _redis()
    try:
        active_key = _ACTIVE_RUN_KEY.format(session_id=session_id)
        previous_run = await r.get(active_key)
        if previous_run and previous_run != stream_id:
            cancel_key = _CANCEL_KEY.format(session_id=session_id, stream_id=previous_run)
            await r.set(cancel_key, "1", ex=_RUN_TTL)
        await r.set(active_key, stream_id, ex=_RUN_TTL)

        pending_key = f"pending:{session_id}:{stream_id}"
        await r.set(pending_key, str(message.id), ex=_RUN_TTL)

        # Store reference images and workspace draft for the SSE endpoint
        if body.reference_images:
            ref_key = f"ref_images:{session_id}:{stream_id}"
            await r.set(ref_key, json.dumps([img.model_dump() for img in body.reference_images]), ex=_RUN_TTL)
        if body.workspace and any(
            [
                body.workspace.keywords,
                body.workspace.llm_description,
                body.workspace.custom_description,
                body.workspace.negative_prompt,
                body.workspace.prompt_template,
            ]
        ):
            ws_key = f"workspace:{session_id}:{stream_id}"
            await r.set(ws_key, json.dumps(body.workspace.model_dump()), ex=_RUN_TTL)
            await update_workspace_state(db, session_id, body.workspace.model_dump())

        if body.reference_images:
            await upsert_reference_images(
                db,
                session_id,
                [
                    {
                        "file_id": img.file_id,
                        "url": img.url,
                        "analysis": {
                            "intent": img.intent,
                            "note": img.note,
                            "sent": True,
                        },
                    }
                    for img in body.reference_images
                ],
            )
    finally:
        await r.aclose()

    return {"stream_id": stream_id}


# ---------------------------------------------------------------------------
# GET — SSE stream
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: uuid.UUID,
    stream_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    session = await get_db_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Reconnection: parse Last-Event-ID header
    last_event_id_header = request.headers.get("last-event-id", "0")
    try:
        last_event_id = int(last_event_id_header)
    except ValueError:
        last_event_id = 0

    pending_message_id: str | None = None
    if last_event_id == 0:
        # Validate the pending stream_id. Conversation history is loaded from DB.
        r = _redis()
        try:
            pending_key = f"pending:{session_id}:{stream_id}"
            pending_message_id = await r.get(pending_key)
            await r.delete(pending_key)
        finally:
            await r.aclose()

    if pending_message_id is None and last_event_id == 0:
        raise HTTPException(status_code=404, detail="stream_id not found or already consumed")

    buffer_key = _BUFFER_KEY.format(session_id=session_id, stream_id=stream_id)

    return StreamingResponse(
        _generate_sse(
            session_id=session_id,
            stream_id=stream_id,
            should_run_agent=last_event_id == 0,
            last_event_id=last_event_id,
            buffer_key=buffer_key,
            db=db,
            request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_sse(
    session_id: uuid.UUID,
    stream_id: str,
    should_run_agent: bool,
    last_event_id: int,
    buffer_key: str,
    db: AsyncSession,
    request: Request,
) -> AsyncIterator[str]:
    r = _redis()
    assistant_text_parts: list[str] = []
    should_persist_assistant = should_run_agent
    try:
        # --- Reconnection: replay buffered events first ---
        if last_event_id > 0:
            replayed = await _replay_events(r, buffer_key, last_event_id)
            for chunk in replayed:
                yield chunk
            return

        # --- Fresh stream: run the graph ---
        graph = request.app.state.graph

        # Load conversation history and build input state
        history = await get_messages(db, session_id, limit=20)
        lc_messages = [
            HumanMessage(content=m.content) if m.role == "user"
            else _ai_message(m.content)
            for m in history
        ]

        # Read reference images and workspace draft stored by submit_message
        ref_images_raw = await r.get(f"ref_images:{session_id}:{stream_id}")
        workspace_raw = await r.get(f"workspace:{session_id}:{stream_id}")

        # Pre-fill reference_images in input_state (url + intent/note; description filled by agent_node)
        pending_ref_images: list[dict] = []
        if ref_images_raw:
            base = str(request.base_url).rstrip("/")
            for img in json.loads(ref_images_raw):
                url = img["url"]
                # Convert relative paths to absolute so VLM can fetch the image
                if url.startswith("/"):
                    url = f"{base}{url}"
                pending_ref_images.append({
                    "file_id": img.get("file_id", ""),
                    "image_url": url,
                    "reference_intent": img.get("intent", ""),
                    "intent_note": img.get("note", ""),
                })

        # Append workspace prompt draft to the last HumanMessage so Agent can see it
        if workspace_raw and lc_messages:
            ws = json.loads(workspace_raw)
            last = lc_messages[-1]
            if isinstance(last, HumanMessage):
                lc_messages[-1] = HumanMessage(
                    content=f"{last.content}\n[用户草稿 workspace: {json.dumps(ws, ensure_ascii=False)}]"
                )

        input_state: dict = {
            "messages": lc_messages,
            "turn_id": str(session_id),
            "run_id": stream_id,
        }
        if pending_ref_images:
            input_state["reference_images"] = pending_ref_images
        if workspace_raw:
            input_state["workspace"] = json.loads(workspace_raw)

        config = {
            "configurable": {"thread_id": str(session_id)},
            "recursion_limit": 25,
        }

        latest_user = next(
            (message_preview(m.content) for m in reversed(lc_messages) if isinstance(m, HumanMessage)),
            "",
        )
        turn_metadata = {
            "session_id": str(session_id),
            "run_id": stream_id,
            "history_count": len(lc_messages),
            "reference_image_count": len(pending_ref_images),
            "has_workspace_prompt": bool(workspace_raw),
        }

        with start_observation(
            name="agent:turn",
            as_type="agent",
            input=latest_user,
            metadata=turn_metadata,
        ):
            set_current_trace_io(input=latest_user)
            update_current_span(metadata=turn_metadata)

        async for chunk in stream_agent_events(graph, config, input_state):
            event_type, data = _parse_sse_chunk(chunk)
            if should_persist_assistant and event_type == "text_delta":
                content = data.get("content")
                if isinstance(content, str):
                    assistant_text_parts.append(content)

            if event_type == "prompt_update" and isinstance(data, dict):
                await update_workspace_state(db, session_id, {
                    "keywords": data.get("keywords", {}),
                    "llm_description": data.get("llm_description", ""),
                    "custom_description": data.get("custom_description", ""),
                    "negative_prompt": data.get("negative_prompt", ""),
                    "prompt_template": data.get("prompt_template"),
                })

            if event_type == "reference_image_update" and isinstance(data.get("image_url"), str):
                analysis = dict(data)
                await upsert_reference_images(
                    db,
                    session_id,
                    [
                        {
                            "file_id": str(data.get("file_id") or data.get("image_url")),
                            "url": str(data.get("image_url")),
                            "analysis": {
                                **analysis,
                                "intent": data.get("reference_intent", ""),
                                "note": data.get("intent_note", ""),
                                "sent": True,
                            },
                        }
                    ],
                )
                continue

            if event_type == "generation_start" and isinstance(data.get("task_id"), str):
                workspace_payload = json.loads(workspace_raw) if workspace_raw else {}
                await create_generation_task(
                    db,
                    session_id,
                    task_id=str(data.get("task_id")),
                    prompt=str(workspace_payload.get("llm_description") or workspace_payload.get("custom_description") or ""),
                    negative_prompt=str(workspace_payload.get("negative_prompt") or "") or None,
                    provider=None,
                    status="running",
                )

            if event_type == "generation_done" and isinstance(data.get("task_id"), str):
                result = await db.execute(
                    select(GenerationTask)
                    .where(GenerationTask.session_id == session_id)
                    .where(GenerationTask.task_id == str(data.get("task_id")))
                    .order_by(GenerationTask.created_at.desc())
                    .limit(1)
                )
                task_row = result.scalar_one_or_none()
                if task_row is not None:
                    task_row.image_url = str(data.get("image_url") or task_row.image_url)
                    task_row.status = "done"
                    await db.commit()

            if event_type == "generation_done" and isinstance(data.get("prompt"), str):
                result = await db.execute(
                    select(GenerationTask)
                    .where(GenerationTask.session_id == session_id)
                    .where(GenerationTask.task_id == str(data.get("task_id")))
                    .order_by(GenerationTask.created_at.desc())
                    .limit(1)
                )
                task_row = result.scalar_one_or_none()
                if task_row is None:
                    await create_generation_task(
                        db,
                        session_id,
                        task_id=str(data.get("task_id")),
                        prompt=str(data.get("prompt") or ""),
                        negative_prompt=str(data.get("negative_prompt") or "") or None,
                        provider=str(data.get("provider") or "") or None,
                        image_url=str(data.get("image_url") or "") or None,
                        status=str(data.get("status") or "done"),
                        score=data.get("score") if isinstance(data.get("score"), (int, float)) else None,
                        raw_response=data.get("raw_response") if isinstance(data.get("raw_response"), dict) else None,
                    )
                else:
                    task_row.prompt = str(data.get("prompt") or task_row.prompt)
                    task_row.negative_prompt = str(data.get("negative_prompt") or "") or task_row.negative_prompt
                    task_row.provider = str(data.get("provider") or "") or task_row.provider
                    task_row.image_url = str(data.get("image_url") or "") or task_row.image_url
                    task_row.status = str(data.get("status") or task_row.status)
                    task_row.score = data.get("score") if isinstance(data.get("score"), (int, float)) else task_row.score
                    task_row.raw_response = data.get("raw_response") if isinstance(data.get("raw_response"), dict) else task_row.raw_response
                    await db.commit()

            # Buffer for reconnection
            await _buffer_event(r, buffer_key, chunk)
            yield chunk

            if should_persist_assistant and event_type == "done":
                assistant_text = "".join(assistant_text_parts).strip()
                if assistant_text:
                    reply_text = _extract_reply(assistant_text) or assistant_text
                    set_current_trace_io(output=message_preview(reply_text))
                    update_current_span(
                        output=message_preview(reply_text),
                        metadata={"finish_reason": data.get("finish_reason", "stop")},
                    )
                    await add_message(db, session_id, "assistant", reply_text)
                    try:
                        await maybe_generate_session_title(db, session_id)
                    except Exception:
                        pass
                await _clear_active_run(r, session_id, stream_id)
                should_persist_assistant = False

            # Honour client disconnect
            if await request.is_disconnected():
                update_current_span(level="WARNING", status_message="client disconnected")
                break

    finally:
        await r.aclose()


def _ai_message(content: str):
    from langchain_core.messages import AIMessage
    return AIMessage(content=content)


async def _clear_active_run(
    redis: aioredis.Redis,
    session_id: uuid.UUID,
    stream_id: str,
) -> None:
    """Clear active_run only if it still points to this stream."""
    active_key = _ACTIVE_RUN_KEY.format(session_id=session_id)
    active_run = await redis.get(active_key)
    if active_run == stream_id:
        await redis.delete(active_key)


def _extract_reply(raw: str) -> str | None:
    """Extract the 'reply' field from agent JSON output.

    The agent streams raw JSON (including design_state_updates, phase, etc.).
    Only the 'reply' field should be persisted and shown to the user.
    Falls back to None if parsing fails, so callers can keep the raw text.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        import json as _json
        data = _json.loads(text)
        reply = data.get("reply", "")
        if isinstance(reply, str) and reply.strip():
            return reply.strip()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Self-test (requires running Redis and no DB)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def _test_buffer_replay() -> None:
        print("=== Redis buffer / replay test ===")
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        key = "sse_buffer:test:selftest"

        # Clean up
        await r.delete(key)

        events = [
            "event: text_delta\ndata: {\"content\": \"A\"}\nid: 1\n\n",
            "event: text_delta\ndata: {\"content\": \"B\"}\nid: 2\n\n",
            "event: done\ndata: {\"finish_reason\": \"stop\"}\nid: 3\n\n",
        ]
        for e in events:
            await _buffer_event(r, key, e)

        # Replay from id=1 → should get id 2 and 3
        replayed = await _replay_events(r, key, last_event_id=1)
        print(f"  replayed from id=1: {len(replayed)} events")
        assert len(replayed) == 2, f"expected 2, got {len(replayed)}"

        # Replay from id=0 → all 3
        replayed_all = await _replay_events(r, key, last_event_id=0)
        print(f"  replayed from id=0: {len(replayed_all)} events")
        assert len(replayed_all) == 3

        await r.delete(key)
        await r.aclose()
        print("  buffer/replay OK\n")

    async def _test_pending_roundtrip() -> None:
        print("=== Pending message roundtrip test ===")
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        sid = "test-session"
        stid = "test-stream"
        key = f"pending:{sid}:{stid}"

        await r.set(key, "用户消息内容", ex=300)
        val = await r.get(key)
        print(f"  stored and retrieved: {val!r}")
        assert val == "用户消息内容"

        await r.delete(key)
        await r.aclose()
        print("  pending roundtrip OK\n")

    async def main() -> None:
        await _test_buffer_replay()
        await _test_pending_roundtrip()
        print("All chat.py tests passed.")

    asyncio.run(main())
