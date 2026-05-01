import unittest

from core.llm.factory import LLMClientFactory
from core.llm.bailian_client import BailianLLMClient
from core.llm.volcengine_client import VolcengineLLMClient


class TestLLMClientFactory(unittest.TestCase):
    def test_bailian_instantiates(self):
        client = LLMClientFactory.create("bailian", model="qwen-vl-max", api_key="test-key")
        self.assertIsInstance(client, BailianLLMClient)

    def test_volcengine_instantiates(self):
        client = LLMClientFactory.create("volcengine", model="doubao-1.5-vision-pro-32k", api_key="test-key")
        self.assertIsInstance(client, VolcengineLLMClient)

    def test_unknown_provider_raises_key_error(self):
        with self.assertRaises(KeyError):
            LLMClientFactory.create("unknown", model="x", api_key="x")


if __name__ == "__main__":
    unittest.main()
