from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from agent.tools.image_generator import generate_image
from agent.tools.prompt_builder import EnhancedPrompt
from config import settings


class TestImageGeneratorTool(unittest.IsolatedAsyncioTestCase):
    async def test_generate_image_uses_control_image_and_reference_inputs(self) -> None:
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
                {"image_url": "https://example.com/ref-1.png", "reference_intent": "material"},
                {"image_url": "https://example.com/ref-2.png", "reference_intent": "color"},
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
        self.assertEqual(captured["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/ref-1.png",
            "https://example.com/ref-2.png",
        ])
        self.assertEqual(captured["width"], 2048)
        self.assertEqual(captured["height"], 1152)
        self.assertEqual(captured["aspectRatio"], "16:9")
        self.assertIn("图2为参考图：只参考材质肌理", captured["prompt"])
        self.assertIn("图3为参考图：只参考色彩关系", captured["prompt"])

    async def test_generate_image_references_do_not_promote_to_control(self) -> None:
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
            "reference_images": [{"image_url": "https://example.com/ref.png", "reference_intent": "lighting"}],
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
        self.assertEqual(captured["input_image_urls"], ["https://example.com/ref.png"])
        self.assertEqual(captured["width"], 2048)
        self.assertEqual(captured["height"], 1152)
        self.assertEqual(captured["aspectRatio"], "16:9")
        self.assertIn("图1为参考图：只参考光线时段", captured["prompt"])

    async def test_generate_image_uses_control_image_ratio_for_canvas(self) -> None:
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

        with tempfile.TemporaryDirectory() as temp_dir:
            original_upload_dir = settings.UPLOAD_DIR
            settings.UPLOAD_DIR = temp_dir
            try:
                Image.new("RGB", (300, 200), color="white").save(
                    Path(temp_dir) / "control.png",
                    format="PNG",
                )
                state = {
                    "turn_id": "session-1",
                    "run_id": "run-1",
                    "control_image": {"image_url": "/static/uploads/control.png"},
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
            finally:
                settings.UPLOAD_DIR = original_upload_dir

        self.assertEqual(captured["width"], 2048)
        self.assertEqual(captured["height"], 1344)
        self.assertEqual(captured["aspectRatio"], "3:2")

    async def test_generate_image_uses_annotated_image_ratio_without_control(self) -> None:
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

        with tempfile.TemporaryDirectory() as temp_dir:
            original_upload_dir = settings.UPLOAD_DIR
            settings.UPLOAD_DIR = temp_dir
            try:
                Image.new("RGB", (100, 200), color="white").save(
                    Path(temp_dir) / "annotated.png",
                    format="PNG",
                )
                state = {
                    "turn_id": "session-1",
                    "run_id": "run-1",
                    "annotated_image": {"image_url": "/static/uploads/annotated.png"},
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
            finally:
                settings.UPLOAD_DIR = original_upload_dir

        self.assertEqual(captured["width"], 1024)
        self.assertEqual(captured["height"], 2048)
        self.assertEqual(captured["aspectRatio"], "1:2")

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
            "reference_images": [{"image_url": "https://example.com/ref.png", "reference_intent": "style"}],
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
            "https://example.com/ref.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("本次编辑的主约束图", captured["prompt"])
        self.assertIn("不要只做轻微风格变化", captured["prompt"])
        self.assertIn("图2为带批注效果图", captured["prompt"])
        self.assertIn("允许重绘相关区域", captured["prompt"])
        self.assertIn("批注说明：加深入口雨棚", captured["prompt"])
        self.assertIn("图3为参考图：只参考建筑表达语言", captured["prompt"])

    async def test_generate_image_limits_reference_inputs_to_three(self) -> None:
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
            "reference_images": [
                {"image_url": f"https://example.com/ref-{index}.png", "reference_intent": "color"}
                for index in range(1, 5)
            ],
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
            "https://example.com/ref-1.png",
            "https://example.com/ref-2.png",
            "https://example.com/ref-3.png",
        ])
        self.assertIn("图3为参考图", captured["prompt"])
        self.assertNotIn("ref-4", captured["prompt"])

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

    async def test_retry_does_not_include_previous_generation_after_non_empty_slots(self) -> None:
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
                {"image_url": "https://example.com/ref.png", "reference_intent": "material"}
            ],
            "rag_image": {
                "image_url": "https://example.com/rag.png",
                "ambience_note": "明亮的午后侧光",
            },
            "_current_gen_result": {"image_url": "https://example.com/previous.png"},
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
            "https://example.com/ref.png",
            "https://example.com/rag.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("图2为参考图", captured["prompt"])
        self.assertIn("图3为氛围参考：明亮的午后侧光", captured["prompt"])
        self.assertNotIn("https://example.com/previous.png", captured["input_image_urls"])
        self.assertNotIn("上一轮低分生成结果", captured["prompt"])

    async def test_retry_with_all_slots_does_not_label_previous_generation(self) -> None:
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
            "reference_images": [
                {"image_url": "https://example.com/ref.png", "reference_intent": "composition"}
            ],
            "rag_image": {
                "image_url": "https://example.com/rag.png",
                "ambience_note": "黑白漫画线稿氛围",
            },
            "_current_gen_result": {"image_url": "https://example.com/previous.png"},
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
            "https://example.com/ref.png",
            "https://example.com/rag.png",
        ])
        self.assertIn("图1为图生图底图", captured["prompt"])
        self.assertIn("图2为带批注效果图", captured["prompt"])
        self.assertIn("图3为参考图：只参考构图", captured["prompt"])
        self.assertIn("图4为氛围参考：黑白漫画线稿氛围", captured["prompt"])
        self.assertNotIn("https://example.com/previous.png", captured["input_image_urls"])
        self.assertNotIn("上一轮低分生成结果", captured["prompt"])

    async def test_reference_input_failure_falls_back_to_strong_anchors(self) -> None:
        first_task = SimpleNamespace(id="task-1")
        second_task = SimpleNamespace(id="task-2")
        results = {
            "task-1": SimpleNamespace(
                ready=lambda: True,
                successful=lambda: False,
                result="provider rejected too many input images",
            ),
            "task-2": SimpleNamespace(
                ready=lambda: True,
                successful=lambda: True,
                get=lambda: {
                    "image_url": "https://example.com/out.png",
                    "provider": "test",
                    "generation_time": 1.0,
                    "raw_response": {},
                },
            ),
        }
        captured: list[dict] = []

        def fake_delay(request_dict: dict) -> SimpleNamespace:
            captured.append(request_dict)
            return first_task if len(captured) == 1 else second_task

        class FakeRedis:
            async def exists(self, _key: str) -> int:
                return 0

            async def aclose(self) -> None:
                return None

        state = {
            "turn_id": "session-1",
            "run_id": "run-1",
            "control_image": {"image_url": "https://example.com/control.png"},
            "annotated_image": {"image_url": "https://example.com/annotated.png"},
            "reference_images": [
                {"image_url": "https://example.com/ref.png", "reference_intent": "color"}
            ],
        }

        with (
            patch("agent.tools.image_generator.asyncio.sleep", AsyncMock()),
            patch("tasks.image_task.generate_image_task.delay", side_effect=fake_delay),
            patch("agent.tools.image_generator.AsyncResult", side_effect=lambda task_id, app=None: results[task_id]),
            patch("redis.asyncio.Redis.from_url", return_value=FakeRedis()),
        ):
            result = await generate_image(
                state=state,
                enhanced_prompt=EnhancedPrompt(prompt="modern villa", negative_prompt="blurry"),
            )

        self.assertEqual(result["image_url"], "https://example.com/out.png")
        self.assertEqual(captured[0]["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
            "https://example.com/ref.png",
        ])
        self.assertEqual(captured[1]["input_image_urls"], [
            "https://example.com/control.png",
            "https://example.com/annotated.png",
        ])
