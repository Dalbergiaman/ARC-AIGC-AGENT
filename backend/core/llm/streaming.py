"""SSE streaming layer: bridges LangGraph astream_events to the 7-event SSE protocol.

Event types (per DEV_SPEC):
  text_delta        — LLM token output
  tool_start        — agent begins a tool call
  tool_end          — tool call completed
  generation_start  — image generation task submitted (from generate_image emitter)
  generation_done   — image generation completed   (from generate_image emitter)
  error             — any error during the turn
  done              — turn finished (finish_reason: stop | max_retries | interrupted)

ContextVar usage:
  Before calling graph.astream_events(), store a QueueEmitter in _EMITTER_VAR.
  generate_image_node reads it via get_current_emitter().
  streaming.py drains both astream_events and the queue concurrently.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
from typing import AsyncIterator

from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

# ---------------------------------------------------------------------------
# ContextVar — carries the per-request QueueEmitter into generate_image_node
# ---------------------------------------------------------------------------

_EMITTER_VAR: contextvars.ContextVar["QueueEmitter | None"] = contextvars.ContextVar(
    "_EMITTER_VAR", default=None
)


def get_current_emitter() -> "QueueEmitter | None":
    return _EMITTER_VAR.get()


# ---------------------------------------------------------------------------
# QueueEmitter — real SSEEmitter backed by asyncio.Queue
# ---------------------------------------------------------------------------

class QueueEmitter:
    """Receives generation_start / generation_done events from generate_image_node
    and puts them into a queue that streaming.py drains."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(self, event_type: str, data: dict) -> None:
        await self._queue.put({"type": event_type, "data": data})

    async def close(self) -> None:
        """Signal that no more events will be emitted."""
        await self._queue.put(None)

    async def drain(self) -> AsyncIterator[dict]:
        """Yield queued events until close() is called."""
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item


# ---------------------------------------------------------------------------
# Tool output summarizer
# ---------------------------------------------------------------------------

_TOOL_SUMMARIES: dict[str, str] = {
    "analyze_reference_image": "正在分析参考图...",
    "lookup_style_keywords": "正在查询风格关键词...",
    "search_similar_cases": "正在检索相似案例...",
    "enhance_prompt": "正在构建生成提示词...",
    "refine_prompt": "正在优化提示词...",
    "evaluate_generated_image": "正在评估生成结果...",
    "generate_image": "正在生成图像...",
}

_TOOL_DONE_SUMMARIES: dict[str, str] = {
    "analyze_reference_image": "参考图分析完成",
    "lookup_style_keywords": "风格关键词已加载",
    "search_similar_cases": "相似案例检索完成",
    "enhance_prompt": "提示词构建完成",
    "refine_prompt": "提示词优化完成",
    "evaluate_generated_image": "图像评估完成",
    "generate_image": "图像生成完成",
}


def summarize_tool_output(tool_name: str, output: object) -> str:
    """Return a user-friendly one-line summary for a tool_end event."""
    base = _TOOL_DONE_SUMMARIES.get(tool_name, f"{tool_name} 完成")

    if tool_name == "evaluate_generated_image" and isinstance(output, dict):
        score = output.get("score")
        if score is not None:
            return f"{base}（评分 {score:.2f}）"

    if tool_name == "search_similar_cases" and isinstance(output, list):
        return f"{base}（找到 {len(output)} 个案例）"

    return base


# ---------------------------------------------------------------------------
# SSE formatting helpers
# ---------------------------------------------------------------------------

_event_counter: int = 0


def _sse(event_type: str, data: dict, event_id: int) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\nid: {event_id}\n\n"


def _parse_sse_chunk(chunk: str) -> tuple[str | None, dict]:
    event_type: str | None = None
    data: dict = {}
    for line in chunk.splitlines():
        if line.startswith("event: "):
            event_type = line[len("event: "):].strip()
        elif line.startswith("data: "):
            try:
                parsed = json.loads(line[len("data: "):].strip())
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                data = parsed
    return event_type, data


# ---------------------------------------------------------------------------
# Main streaming function
# ---------------------------------------------------------------------------

async def stream_agent_events(
    graph: CompiledStateGraph,
    config: dict,
    input_state: dict,
) -> AsyncIterator[str]:
    """Run the graph and yield SSE-formatted strings.

    Concurrently consumes:
    - graph.astream_events() for text_delta / tool_start / tool_end
    - QueueEmitter for generation_start / generation_done
    """
    emitter = QueueEmitter()
    token = _EMITTER_VAR.set(emitter)

    event_id = 0
    finish_reason = "stop"
    saw_chat_model_stream = False
    emitted_state_texts: set[str] = set()

    async def _graph_task() -> None:
        nonlocal finish_reason
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                await _graph_event_queue.put(event)
        except asyncio.CancelledError:
            finish_reason = "interrupted"
        except Exception as exc:
            await _graph_event_queue.put({"_error": str(exc)})
        finally:
            await emitter.close()
            await _graph_event_queue.put(None)  # sentinel

    _graph_event_queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_graph_task())

    try:
        graph_done = False
        emitter_done = False

        pending_graph: asyncio.Queue = _graph_event_queue
        pending_emitter = emitter._queue

        while not (graph_done and emitter_done):
            # Wait for whichever queue has something
            get_graph = asyncio.ensure_future(pending_graph.get()) if not graph_done else None
            get_emit = asyncio.ensure_future(pending_emitter.get()) if not emitter_done else None

            futs = [f for f in (get_graph, get_emit) if f is not None]
            if not futs:
                break

            done, _ = await asyncio.wait(futs, return_when=asyncio.FIRST_COMPLETED)

            # Cancel the futures that didn't fire
            for f in futs:
                if f not in done:
                    f.cancel()

            for fut in done:
                item = fut.result()

                # --- Graph event ---
                if fut is get_graph:
                    if item is None:
                        graph_done = True
                        continue
                    if isinstance(item, dict) and "_error" in item:
                        event_id += 1
                        yield _sse("error", {"code": "AGENT_ERROR", "message": item["_error"]}, event_id)
                        graph_done = True
                        finish_reason = "stop"
                        continue

                    sse_chunk = _map_langgraph_event(
                        item,
                        event_id,
                        suppress_state_text_delta=saw_chat_model_stream,
                    )
                    if sse_chunk:
                        if item.get("event") == "on_chat_model_stream":
                            saw_chat_model_stream = True
                        elif item.get("event") == "on_chain_stream":
                            _, data = _parse_sse_chunk(sse_chunk)
                            content = data.get("content")
                            if isinstance(content, str):
                                if content in emitted_state_texts:
                                    continue
                                emitted_state_texts.add(content)
                        event_id += 1
                        yield sse_chunk

                # --- Emitter event (generation_start / generation_done) ---
                elif fut is get_emit:
                    if item is None:
                        emitter_done = True
                        continue
                    event_id += 1
                    yield _sse(item["type"], item["data"], event_id)

    finally:
        task.cancel()
        _EMITTER_VAR.reset(token)

    # Final done event
    event_id += 1
    yield _sse("done", {"finish_reason": finish_reason}, event_id)


def _map_langgraph_event(
    event: dict,
    current_id: int,
    suppress_state_text_delta: bool = False,
) -> str | None:
    """Map a single LangGraph astream_events v2 event to an SSE string, or None to skip."""
    kind = event.get("event", "")
    name = event.get("name", "")

    if kind == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        if chunk is None:
            return None
        content = ""
        if hasattr(chunk, "content"):
            content = chunk.content
        elif isinstance(chunk, dict):
            content = chunk.get("content", "")
        if not content:
            return None
        return _sse("text_delta", {"content": content}, current_id + 1)

    if kind == "on_chain_stream" and not suppress_state_text_delta:
        content = _extract_ai_message_content(event.get("data", {}).get("chunk"))
        if content:
            return _sse("text_delta", {"content": content}, current_id + 1)

    if kind == "on_tool_start":
        tool_name = name or event.get("data", {}).get("name", "")
        tool_input = event.get("data", {}).get("input", {})
        return _sse("tool_start", {
            "tool": tool_name,
            "input": tool_input,
            "summary": _TOOL_SUMMARIES.get(tool_name, f"正在调用 {tool_name}..."),
        }, current_id + 1)

    if kind == "on_tool_end":
        tool_name = name or event.get("data", {}).get("name", "")
        output = event.get("data", {}).get("output")
        return _sse("tool_end", {
            "tool": tool_name,
            "summary": summarize_tool_output(tool_name, output),
        }, current_id + 1)

    return None


def _extract_ai_message_content(value: object) -> str:
    """Extract visible assistant text from LangGraph state deltas.

    This is a fallback for nodes that call the project LLM wrapper via ainvoke()
    instead of a LangChain streaming chat model. Restrict callers to
    on_chain_stream deltas so full historical state is not replayed as text.
    """
    if isinstance(value, AIMessage):
        return str(value.content or "")

    if isinstance(value, dict):
        role = value.get("role") or value.get("type")
        content = value.get("content")
        if role in {"assistant", "ai"} and isinstance(content, str):
            return content

        messages = value.get("messages")
        if isinstance(messages, list):
            for item in reversed(messages):
                content = _extract_ai_message_content(item)
                if content:
                    return content

        for item in value.values():
            content = _extract_ai_message_content(item)
            if content:
                return content

    if isinstance(value, list):
        for item in reversed(value):
            content = _extract_ai_message_content(item)
            if content:
                return content

    return ""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    async def _test_queue_emitter() -> None:
        print("=== QueueEmitter test ===")
        emitter = QueueEmitter()

        async def _producer() -> None:
            await emitter.emit("generation_start", {"task_id": "abc", "provider": "bailian"})
            await emitter.emit("generation_done", {"task_id": "abc", "image_url": "http://example.com/img.jpg"})
            await emitter.close()

        asyncio.create_task(_producer())

        async for event in emitter.drain():
            print(f"  received: {event}")
        print("  QueueEmitter OK\n")

    async def _test_sse_format() -> None:
        print("=== SSE format test ===")
        chunk = _sse("text_delta", {"content": "你好"}, 1)
        print(repr(chunk))
        assert chunk.startswith("event: text_delta\n")
        assert '"content": "你好"' in chunk
        assert chunk.endswith("\n\n")
        print("  SSE format OK\n")

    async def _test_summarize() -> None:
        print("=== summarize_tool_output test ===")
        s = summarize_tool_output("evaluate_generated_image", {"score": 0.87})
        print(f"  eval summary: {s}")
        assert "0.87" in s

        s2 = summarize_tool_output("search_similar_cases", [1, 2, 3])
        print(f"  search summary: {s2}")
        assert "3" in s2

        s3 = summarize_tool_output("unknown_tool", None)
        print(f"  unknown summary: {s3}")
        print("  summarize OK\n")

    async def _test_map_event() -> None:
        print("=== _map_langgraph_event test ===")

        class FakeChunk:
            content = "Hello"

        e1 = {
            "event": "on_chat_model_stream",
            "name": "ChatModel",
            "data": {"chunk": FakeChunk()},
        }
        result = _map_langgraph_event(e1, 0)
        print(f"  text_delta: {repr(result)}")
        assert result and "text_delta" in result

        e2 = {
            "event": "on_tool_start",
            "name": "analyze_reference_image",
            "data": {"input": {"image_url": "http://x.com/a.jpg"}},
        }
        result2 = _map_langgraph_event(e2, 1)
        print(f"  tool_start: {repr(result2)}")
        assert result2 and "tool_start" in result2

        e3 = {
            "event": "on_tool_end",
            "name": "search_similar_cases",
            "data": {"output": [{"id": "1"}, {"id": "2"}]},
        }
        result3 = _map_langgraph_event(e3, 2)
        print(f"  tool_end: {repr(result3)}")
        assert result3 and "tool_end" in result3
        print("  _map_langgraph_event OK\n")

    async def main() -> None:
        await _test_queue_emitter()
        await _test_sse_format()
        await _test_summarize()
        await _test_map_event()
        print("All streaming.py tests passed.")

    asyncio.run(main())
