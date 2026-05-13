from __future__ import annotations

import unittest

from core.llm.streaming import extract_reply, get_current_emitter, stream_agent_events


class FakeGraph:
    async def astream_events(self, input_state: dict, config: dict, version: str):
        emitter = get_current_emitter()
        if emitter is not None:
            await emitter.emit(
                "prompt_update",
                {
                    "keywords": {"style": "modern"},
                    "llm_description": "modern villa with clean lines",
                    "custom_description": "",
                    "negative_prompt": "blurry",
                    "prompt_template": {
                        "style": "现代主义",
                        "positive": ["modernist architecture"],
                        "negative": ["traditional ornament"],
                        "mood": "理性、开放、通透",
                        "description": "现代主义建筑说明",
                    },
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

    def test_extract_reply_from_agent_json(self):
        raw = '```json\n{"reply":"可以，现在开始生成。","phase":"generating"}\n```'

        self.assertEqual(extract_reply(raw), "可以，现在开始生成。")


if __name__ == "__main__":
    unittest.main()
