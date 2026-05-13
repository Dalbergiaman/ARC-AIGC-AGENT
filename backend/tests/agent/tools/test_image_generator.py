from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agent.tools.image_generator import generate_image
from agent.tools.prompt_builder import EnhancedPrompt


class TestImageGeneratorTool(unittest.IsolatedAsyncioTestCase):
    async def test_generate_image_uses_control_image_not_last_reference(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "control_image": {"image_url": "https://example.com/control.png"},
            "reference_images": [
                {"image_url": "https://example.com/ref-1.png"},
                {"image_url": "https://example.com/ref-2.png"},
            ],
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            result = await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(result["image_url"], "https://example.com/out.png")
        self.assertEqual(captured["control_image_url"], "https://example.com/control.png")
        self.assertEqual(captured["ref_image_url"], "https://example.com/control.png")
        self.assertNotIn("reference_image_urls", captured)

    async def test_generate_image_does_not_promote_reference_to_control(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "reference_images": [{"image_url": "https://example.com/ref.png"}],
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertIsNone(captured["control_image_url"])
        self.assertIsNone(captured["ref_image_url"])
        self.assertEqual(captured["input_image_urls"], [])
        self.assertNotIn("reference_image_urls", captured)

    async def test_generate_image_includes_control_and_annotated_images_in_order(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "control_image": {"image_url": "https://example.com/control.png"},
            "annotated_image": {
                "image_url": "https://example.com/annotated.png",
                "note": "加深入口雨棚",
            },
            "reference_images": [{"image_url": "https://example.com/ref.png"}],
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(captured["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("本次编辑的主约束图", captured["prompt"])
        self.assertIn("不要只做轻微风格变化", captured["prompt"])
        self.assertIn("图2为带批注效果图", captured["prompt"])
        self.assertIn("允许重绘相关区域", captured["prompt"])
        self.assertIn("批注说明：加深入口雨棚", captured["prompt"])

    async def test_generate_image_includes_annotated_image_without_control(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "annotated_image": {
                "image_url": "https://example.com/annotated.png",
                "note": "入口增加暖光",
            },
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(captured["input_image_urls"], ["https://example.com/annotated.png"])
        self.assertIsNone(captured["control_image_url"])
        self.assertIn("图1为带批注效果图", captured["prompt"])
        self.assertIn("批注说明：入口增加暖光", captured["prompt"])

    async def test_retry_includes_failed_image_after_non_empty_slots(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "control_image": {"image_url": "https://example.com/control.png"},
            "rag_image": {
                "image_url": "https://example.com/rag.png",
                "ambience_note": "明亮的午后侧光",
            },
            "_current_gen_result": {"image_url": "https://example.com/failed.png"},
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(captured["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/rag.png",
            "https://example.com/failed.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("图2为氛围参考：明亮的午后侧光", captured["prompt"])
        self.assertIn("图3为上一轮低分生成结果", captured["prompt"])
        self.assertNotIn("图4为上一轮低分生成结果", captured["prompt"])

    async def test_retry_with_all_slots_labels_failed_image_as_fourth_input(self) -> None:
        task = SimpleNamespace(id="task-1")
        async_result = SimpleNamespace(
            ready=lambda: True,
            successful=lambda: True,
            get=lambda: {
                "image_url": "https://example.com/out.png",
                "provider": "test",
                "generation_time": 1.0,
                "raw_response": {},
            },
        )
        captured: dict = {}

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.update(request_dict)
            return task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "control_image": {"image_url": "https://example.com/control.png"},
            "annotated_image": {
                "image_url": "https://example.com/annotated.png",
                "note": "保留原窗洞",
            },
            "rag_image": {
                "image_url": "https://example.com/rag.png",
                "ambience_note": "黑白漫画线稿氛围",
            },
            "_current_gen_result": {"image_url": "https://example.com/failed.png"},
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", return_value=async_result),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(captured["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
            "https://example.com/rag.png",
            "https://example.com/failed.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("图2为带批注效果图", captured["prompt"])
        self.assertIn("图3为氛围参考：黑白漫画线稿氛围", captured["prompt"])
        self.assertIn("图4为上一轮低分生成结果", captured["prompt"])
