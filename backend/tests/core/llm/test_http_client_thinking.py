from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage

from core.llm.bailian_client import BailianLLMClient
from core.llm.volcengine_client import VolcengineLLMClient


class TestHTTPLLMClientThinking(unittest.IsolatedAsyncioTestCase):
    async def test_bailian_vision_can_disable_thinking(self) -> None:
        captured: dict = {}

        async def fake_post(payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        client = BailianLLMClient(model="qwen-vl-max", api_key="test")
        with patch.object(client, "_post", AsyncMock(side_effect=fake_post)):
            result = await client.ainvoke_with_vision(
                [HumanMessage(content="describe")],
                ["data:image/png;base64,abc"],
                enable_thinking=False,
            )

        self.assertEqual(result, "ok")
        self.assertIs(captured["enable_thinking"], False)

    async def test_volcengine_vision_can_disable_thinking(self) -> None:
        captured: dict = {}

        async def fake_post(payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        client = VolcengineLLMClient(model="doubao-vision", api_key="test")
        with patch.object(client, "_post", AsyncMock(side_effect=fake_post)):
            result = await client.ainvoke_with_vision(
                [HumanMessage(content="describe")],
                ["data:image/png;base64,abc"],
                enable_thinking=False,
            )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["thinking"], {"type": "disabled"})

    async def test_vision_default_keeps_provider_defaults(self) -> None:
        captured: dict = {}

        async def fake_post(payload: dict) -> dict:
            captured.update(payload)
            return {"choices": [{"message": {"content": "ok"}}]}

        client = BailianLLMClient(model="qwen-vl-max", api_key="test")
        with patch.object(client, "_post", AsyncMock(side_effect=fake_post)):
            await client.ainvoke_with_vision(
                [HumanMessage(content="describe")],
                ["data:image/png;base64,abc"],
            )

        self.assertNotIn("enable_thinking", captured)


if __name__ == "__main__":
    unittest.main()
