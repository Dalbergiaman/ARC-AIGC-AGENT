"""Manual integration check for C-6.1 Chat/SSE hardening.

Run with Docker Postgres/Redis up:

    cd backend
    .venv/bin/python scripts/test_chat_sse_flow.py

This script uses real PostgreSQL and Redis, but a fake graph. It does not call
the real LLM or image generation APIs.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import redis.asyncio as aioredis
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import chat as chat_route  # noqa: E402
from core.llm.streaming import _parse_sse_chunk  # noqa: E402
from models.database import async_session, engine  # noqa: E402
from models.schemas import Base, Message, Session  # noqa: E402
from services.message_service import add_message, get_messages  # noqa: E402
from services.session_service import create_session  # noqa: E402


FAKE_REPLY = "这是 C-6.1 SSE 测试回复。"


class FakeGraph:
    def __init__(self) -> None:
        self.call_count = 0
        self.input_states: list[dict] = []

    async def astream_events(self, input_state: dict, config: dict, version: str):
        self.call_count += 1
        self.input_states.append(input_state)
        yield {
            "event": "on_chain_stream",
            "name": "agent",
            "data": {"chunk": {"messages": [AIMessage(content=FAKE_REPLY)]}},
        }


class FakeRequest:
    def __init__(self, graph: FakeGraph) -> None:
        self.app = SimpleNamespace(state=SimpleNamespace(graph=graph))

    async def is_disconnected(self) -> bool:
        return False


def parse_sse_events(chunks: list[str]) -> list[tuple[str | None, dict, int | None]]:
    events = []
    for chunk in chunks:
        event_type, data = _parse_sse_chunk(chunk)
        event_id: int | None = None
        for line in chunk.splitlines():
            if line.startswith("id: "):
                event_id = int(line[len("id: "):].strip())
                break
        events.append((event_type, data, event_id))
    return events


async def consume_sse(
    session_id: uuid.UUID,
    stream_id: str,
    last_event_id: int,
    graph: FakeGraph,
) -> list[str]:
    buffer_key = chat_route._BUFFER_KEY.format(
        session_id=session_id,
        stream_id=stream_id,
    )
    chunks: list[str] = []
    async with async_session() as db:
        async for chunk in chat_route._generate_sse(
            session_id=session_id,
            stream_id=stream_id,
            should_run_agent=last_event_id == 0,
            last_event_id=last_event_id,
            buffer_key=buffer_key,
            db=db,
            request=FakeRequest(graph),
        ):
            chunks.append(chunk)
    return chunks


async def assert_messages(session_id: uuid.UUID, expected_user: str) -> None:
    async with async_session() as db:
        messages = await get_messages(db, session_id, limit=20)

    user_messages = [m for m in messages if m.role == "user"]
    assistant_messages = [m for m in messages if m.role == "assistant"]

    assert len(user_messages) == 1, f"expected 1 user message, got {len(user_messages)}"
    assert user_messages[0].content == expected_user
    assert len(assistant_messages) == 1, (
        f"expected 1 assistant message, got {len(assistant_messages)}"
    )
    assert assistant_messages[0].content == FAKE_REPLY


async def assert_graph_input_not_duplicated(graph: FakeGraph, expected_user: str) -> None:
    assert graph.call_count == 1, f"expected graph to run once, got {graph.call_count}"
    messages = graph.input_states[0]["messages"]
    user_contents = [
        message.content
        for message in messages
        if isinstance(message, HumanMessage)
    ]
    assert user_contents == [expected_user], f"unexpected graph user messages: {user_contents}"


async def assert_replay_buffer(
    redis: aioredis.Redis,
    session_id: uuid.UUID,
    stream_id: str,
) -> None:
    buffer_key = chat_route._BUFFER_KEY.format(
        session_id=session_id,
        stream_id=stream_id,
    )
    raw_events = await redis.lrange(buffer_key, 0, -1)
    event_types = [event_type for event_type, _, _ in parse_sse_events(raw_events)]
    assert "text_delta" in event_types, f"missing text_delta in {event_types}"
    assert "done" in event_types, f"missing done in {event_types}"


async def assert_reconnect_replays_without_rerun(
    session_id: uuid.UUID,
    stream_id: str,
    graph: FakeGraph,
) -> None:
    chunks = await consume_sse(
        session_id=session_id,
        stream_id=stream_id,
        last_event_id=1,
        graph=graph,
    )
    events = parse_sse_events(chunks)
    assert graph.call_count == 1, "reconnect unexpectedly reran graph"
    assert [event_type for event_type, _, _ in events] == ["done"], events

    async with async_session() as db:
        result = await db.execute(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "assistant",
            )
        )
        assistant_messages = result.scalars().all()
    assert len(assistant_messages) == 1, "reconnect duplicated assistant message"


async def assert_active_run_cancel(redis: aioredis.Redis, session_id: uuid.UUID) -> None:
    old_run = "old-run"
    new_run = str(uuid.uuid4())
    active_key = chat_route._ACTIVE_RUN_KEY.format(session_id=session_id)
    cancel_key = chat_route._CANCEL_KEY.format(
        session_id=session_id,
        stream_id=old_run,
    )

    await redis.set(active_key, old_run, ex=chat_route._RUN_TTL)

    previous_run = await redis.get(active_key)
    if previous_run and previous_run != new_run:
        await redis.set(cancel_key, "1", ex=chat_route._RUN_TTL)
    await redis.set(active_key, new_run, ex=chat_route._RUN_TTL)

    assert await redis.get(cancel_key) == "1", "cancel flag was not written"
    assert await redis.get(active_key) == new_run, "active run was not updated"


async def cleanup(redis: aioredis.Redis, session_id: uuid.UUID, stream_id: str) -> None:
    keys = [
        chat_route._BUFFER_KEY.format(session_id=session_id, stream_id=stream_id),
        chat_route._ACTIVE_RUN_KEY.format(session_id=session_id),
        chat_route._CANCEL_KEY.format(session_id=session_id, stream_id="old-run"),
        f"pending:{session_id}:{stream_id}",
    ]
    await redis.delete(*keys)

    async with async_session() as db:
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Session).where(Session.id == session_id))
        await db.commit()


async def main() -> None:
    stream_id = str(uuid.uuid4())
    user_message = "请帮我设计一栋现代风格别墅"
    graph = FakeGraph()
    redis = aioredis.from_url(chat_route.settings.REDIS_URL, decode_responses=True)
    session_id: uuid.UUID | None = None

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await redis.ping()

        async with async_session() as db:
            session = await create_session(db)
            session_id = session.id
            await add_message(db, session_id, "user", user_message)

        await redis.set(f"pending:{session_id}:{stream_id}", "message-id", ex=chat_route._RUN_TTL)
        await redis.set(
            chat_route._ACTIVE_RUN_KEY.format(session_id=session_id),
            stream_id,
            ex=chat_route._RUN_TTL,
        )

        chunks = await consume_sse(
            session_id=session_id,
            stream_id=stream_id,
            last_event_id=0,
            graph=graph,
        )
        events = parse_sse_events(chunks)
        event_types = [event_type for event_type, _, _ in events]
        assert event_types == ["text_delta", "done"], event_types

        await assert_graph_input_not_duplicated(graph, user_message)
        await assert_messages(session_id, user_message)
        await assert_replay_buffer(redis, session_id, stream_id)
        await assert_reconnect_replays_without_rerun(session_id, stream_id, graph)
        await assert_active_run_cancel(redis, session_id)

        print("C-6.1 chat/SSE integration checks passed.")

    except Exception:
        if session_id is not None:
            print(f"Test data may remain: session_id={session_id}, stream_id={stream_id}")
        raise
    finally:
        if session_id is not None:
            await cleanup(redis, session_id, stream_id)
        await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
