import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import HumanMessage

from core.llm.client import LLMClient


_MOCK_CONFIG = {
    "llm": {"provider": "bailian", "model": "qwen-vl-max", "api_key": "test-key"},
    "image_provider": {"provider": "bailian", "api_key": ""},
    "langfuse": {"host": "", "public_key": "", "secret_key": ""},
}


class TestLLMClient(unittest.IsolatedAsyncioTestCase):
    def _make_client_with_mock(self):
        llm = LLMClient()
        mock_inner = MagicMock()
        mock_inner.ainvoke = AsyncMock(return_value="text response")
        mock_inner.ainvoke_with_vision = AsyncMock(return_value="vision response")
        return llm, mock_inner

    @patch("core.llm.client.dashboard_service.get_config", return_value=_MOCK_CONFIG)
    @patch("core.llm.client.LLMClientFactory.create")
    async def test_no_images_calls_ainvoke(self, mock_create, _mock_cfg):
        mock_inner = MagicMock()
        mock_inner.ainvoke = AsyncMock(return_value="text response")
        mock_create.return_value = mock_inner

        result = await LLMClient().ainvoke([HumanMessage(content="hello")])

        mock_inner.ainvoke.assert_awaited_once()
        mock_inner.ainvoke_with_vision.assert_not_called()
        self.assertEqual(result, "text response")

    @patch("core.llm.client.dashboard_service.get_config", return_value=_MOCK_CONFIG)
    @patch("core.llm.client.LLMClientFactory.create")
    async def test_with_images_calls_ainvoke_with_vision(self, mock_create, _mock_cfg):
        mock_inner = MagicMock()
        mock_inner.ainvoke_with_vision = AsyncMock(return_value="vision response")
        mock_create.return_value = mock_inner

        result = await LLMClient().ainvoke(
            [HumanMessage(content="describe this")],
            images=["http://example.com/img.jpg"],
        )

        mock_inner.ainvoke_with_vision.assert_awaited_once()
        mock_inner.ainvoke.assert_not_called()
        self.assertEqual(result, "vision response")


if __name__ == "__main__":
    unittest.main()
