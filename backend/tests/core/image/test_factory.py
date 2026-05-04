import unittest

from core.image.bailian_client import BailianClient
from core.image.factory import ImageGeneratorFactory
# from core.image.openrouter_client import OpenRouterClient
from core.image.volcengine_client import VolcengineClient
from core.image.grsai_client import GrsaiClient


class TestImageGeneratorFactory(unittest.TestCase):
    def test_bailian_instantiates(self):
        client = ImageGeneratorFactory.create("bailian", api_key="test", model="wan2.7-image-pro")
        self.assertIsInstance(client, BailianClient)

    def test_volcengine_instantiates(self):
        client = ImageGeneratorFactory.create(
            "volcengine", api_key="test", model="doubao-seedream-3-0-t2i-250415"
        )
        self.assertIsInstance(client, VolcengineClient)

    def test_grsai_instantiates(self):
        client = ImageGeneratorFactory.create(
            "grsai", api_key="test", model="gpt-image"
        )
        self.assertIsInstance(client, GrsaiClient)

    def test_unknown_provider_raises_key_error(self):
        with self.assertRaises(KeyError):
            ImageGeneratorFactory.create("unknown", api_key="test", model="x")


if __name__ == "__main__":
    unittest.main()
