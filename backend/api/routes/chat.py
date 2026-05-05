"""Chat API routes.

POST /api/chat/sessions/{session_id}/messages
    Submit a user message. Returns {"stream_id": "<uuid>"}.
    stream_id == run_id — used for SSE isolation and cancel flag.

GET /api/chat/sessions/{session_id}/stream?stream_id=<uuid>
    Consume the SSE stream for the submitted message.
    Supports Last-Event-ID header for reconnection (replays buffered events).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent.state import default_agent_state
from config import settings
from core.llm.streaming import QueueEmitter, _EMITTER_VAR, stream_agent_events
from models.database import get_session
from services.message_service import add_message, get_messages
from services.session_service import get_session as get_db_session

router = APIRouter(prefix="/api/chat")

# Redis TTL for buffered SSE events (seconds)
_EVENT_BUFFER_TTL = 60
# Redis key prefix for event buffers
_BUFFER_KEY = "sse_buffer:{session_id}:{stream_id}"


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

class MessageRequest(BaseModel):
    content: str


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

    # Persist user message
    await add_message(db, session_id, "user", body.content)

    # Store pending message in Redis so the SSE endpoint can pick it up
    r = _redis()
    try:
        pending_key = f"pending:{session_id}:{stream_id}"
        await r.set(pending_key, body.content, ex=300)
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

    # Retrieve the pending message content
    r = _redis()
    try:
        pending_key = f"pending:{session_id}:{stream_id}"
        message_content = await r.get(pending_key)
        await r.delete(pending_key)
    finally:
        await r.aclose()

    if message_content is None and last_event_id == 0:
        raise HTTPException(status_code=404, detail="stream_id not found or already consumed")

    buffer_key = _BUFFER_KEY.format(session_id=session_id, stream_id=stream_id)

    return StreamingResponse(
        _generate_sse(
            session_id=session_id,
            stream_id=stream_id,
            message_content=message_content,
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
    message_content: str | None,
    last_event_id: int,
    buffer_key: str,
    db: AsyncSession,
    request: Request,
) -> AsyncIterator[str]:
    r = _redis()
    try:
        # --- Reconnection: replay buffered events first ---
        if last_event_id > 0:
            replayed = await _replay_events(r, buffer_key, last_event_id)
            for chunk in replayed:
                yield chunk
            # If no new message to process, we're done
            if message_content is None:
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
        # The latest user message is already persisted; add it to messages
        if message_content:
            lc_messages.append(HumanMessage(content=message_content))

        input_state = {
            "messages": lc_messages,
            "turn_id": str(session_id),
            "run_id": stream_id,
        }

        config = {
            "configurable": {"thread_id": str(session_id)},
            "recursion_limit": 25,
        }

        async for chunk in stream_agent_events(graph, config, input_state):
            # Buffer for reconnection
            await _buffer_event(r, buffer_key, chunk)
            yield chunk

            # Honour client disconnect
            if await request.is_disconnected():
                break

    finally:
        await r.aclose()


def _ai_message(content: str):
    from langchain_core.messages import AIMessage
    return AIMessage(content=content)


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
