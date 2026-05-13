from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.image.bailian_client import BailianClient
from core.image.base import GenerationRequest
from core.image.grsai_client import GrsaiClient
from core.image.volcengine_client import VolcengineClient


class TestProviderPayloads(unittest.IsolatedAsyncioTestCase):
    async def test_volcengine_payload_includes_control_image_only(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    is_success=True,
                    raise_for_status=lambda: None,
                    json=lambda: {"data": [{"url": "https://example.com/out.png"}]},
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await VolcengineClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    control_image_url="https://example.com/control.png",
                )
            )

        self.assertEqual(captured["image"], "https://example.com/control.png")
        self.assertIs(captured["watermark"], False)

    async def test_volcengine_payload_includes_ordered_input_images(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    is_success=True,
                    raise_for_status=lambda: None,
                    json=lambda: {"data": [{"url": "https://example.com/out.png"}]},
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await VolcengineClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    input_image_urls=[
                        "https://example.com/control.png",
                        "https://example.com/annotated.png",
                    ],
                )
            )

        self.assertEqual(captured["image"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
        ])
        self.assertIs(captured["watermark"], False)

    async def test_volcengine_payload_folds_negative_prompt_into_prompt(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    is_success=True,
                    raise_for_status=lambda: None,
                    json=lambda: {"data": [{"url": "https://example.com/out.png"}]},
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await VolcengineClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    negative_prompt="blurry, watermark",
                )
        )

        self.assertIn("modern villa", captured["prompt"])
        self.assertIn("避免出现以下问题：blurry, watermark", captured["prompt"])
        self.assertNotIn("negative_prompt", captured)

    async def test_grsai_payload_includes_control_image_only(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, json: dict, headers: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    text='data: {"results":[{"url":"https://example.com/out.png"}]}',
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await GrsaiClient(api_key="key", model="nano-banana-pro").generate(
                GenerationRequest(
                    prompt="modern villa",
                    control_image_url="https://example.com/control.png",
                )
            )

        self.assertEqual(captured["urls"], ["https://example.com/control.png"])

    async def test_grsai_payload_includes_ordered_input_images(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, json: dict, headers: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    text='data: {"results":[{"url":"https://example.com/out.png"}]}',
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await GrsaiClient(api_key="key", model="nano-banana-pro").generate(
                GenerationRequest(
                    prompt="modern villa",
                    input_image_urls=[
                        "https://example.com/control.png",
                        "https://example.com/annotated.png",
                    ],
                )
            )

        self.assertEqual(captured["urls"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
        ])

    async def test_grsai_payload_folds_negative_prompt_into_prompt(self) -> None:
        captured: dict = {}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, json: dict, headers: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    text='data: {"results":[{"url":"https://example.com/out.png"}]}',
                )

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await GrsaiClient(api_key="key", model="nano-banana-pro").generate(
                GenerationRequest(
                    prompt="modern villa",
                    negative_prompt="blurry, watermark",
                )
            )

        self.assertIn("modern villa", captured["prompt"])
        self.assertIn("避免出现以下问题：blurry, watermark", captured["prompt"])
        self.assertNotIn("negative_prompt", captured)

    async def test_bailian_payload_includes_control_image_content_before_text(self) -> None:
        captured: dict = {}
        poll_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "output": {
                    "task_status": "SUCCEEDED",
                    "choices": [
                        {"message": {"content": [{"image": "https://example.com/out.png"}]}}
                    ],
                }
            },
        )

        class FakeClient:
            def __init__(self):
                self._first = True

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"output": {"task_id": "task-1"}},
                )

            async def get(self, _endpoint: str, *, headers: dict):
                return poll_response

        with (
            patch("httpx.AsyncClient", return_value=FakeClient()),
        ):
            await BailianClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    control_image_url="https://example.com/control.png",
                )
            )

        content = captured["input"]["messages"][0]["content"]
        self.assertEqual(content, [
            {"image": "https://example.com/control.png"},
            {"text": "modern villa"},
        ])

    async def test_bailian_payload_includes_ordered_input_images_before_text(self) -> None:
        captured: dict = {}
        poll_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "output": {
                    "task_status": "SUCCEEDED",
                    "choices": [
                        {"message": {"content": [{"image": "https://example.com/out.png"}]}}
                    ],
                }
            },
        )

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"output": {"task_id": "task-1"}},
                )

            async def get(self, _endpoint: str, *, headers: dict):
                return poll_response

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await BailianClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    input_image_urls=[
                        "https://example.com/control.png",
                        "https://example.com/annotated.png",
                    ],
                )
            )

        content = captured["input"]["messages"][0]["content"]
        self.assertEqual(content, [
            {"image": "https://example.com/control.png"},
            {"image": "https://example.com/annotated.png"},
            {"text": "modern villa"},
        ])

    async def test_bailian_payload_folds_negative_prompt_into_prompt(self) -> None:
        captured: dict = {}
        poll_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "output": {
                    "task_status": "SUCCEEDED",
                    "choices": [
                        {"message": {"content": [{"image": "https://example.com/out.png"}]}}
                    ],
                }
            },
        )

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, _endpoint: str, *, headers: dict, json: dict):
                captured.update(json)
                return SimpleNamespace(
                    raise_for_status=lambda: None,
                    json=lambda: {"output": {"task_id": "task-1"}},
                )

            async def get(self, _endpoint: str, *, headers: dict):
                return poll_response

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            await BailianClient(api_key="key", model="model").generate(
                GenerationRequest(
                    prompt="modern villa",
                    negative_prompt="blurry, watermark",
                )
            )

        content = captured["input"]["messages"][0]["content"]
        self.assertEqual(content, [
            {"text": "modern villa\n\n避免出现以下问题：blurry, watermark"},
        ])
        self.assertNotIn("negative_prompt", captured["input"])
        self.assertNotIn("negative_prompt", captured["parameters"])
