from __future__ import annotations

import unittest

from core.llm.streaming import get_current_emitter, stream_agent_events


class FakeGraph:
    async def astream_events(self, input_state: dict, config: dict, version: str):
        emitter = get_current_emitter()
        if emitter is not None:
            await emitter.emit(
                "prompt_update",
                {
                    "prompt": "modern villa, clean lines",
                    "negative_prompt": "blurry",
                    "source": "enhance_prompt",
                },
            )
            await emitter.close()
        yield {"event": "on_chain_stream", "name": "agent", "data": {"chunk": {"content": "hello"}}}


class TestStreaming(unittest.IsolatedAsyncioTestCase):
    async def test_stream_agent_events_emits_prompt_update(self):
        graph = FakeGraph()
        chunks = []

        async for chunk in stream_agent_events(graph, config={}, input_state={}):
            chunks.append(chunk)

        self.assertTrue(any("event: prompt_update" in chunk for chunk in chunks), chunks)


if __name__ == "__main__":
    unittest.main()
