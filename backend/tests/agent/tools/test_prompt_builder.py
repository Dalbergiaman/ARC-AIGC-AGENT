from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.prompt_builder import EnhancedPrompt, enhance_prompt, refine_prompt, resolve_prompt_language


def test_resolve_prompt_language_defaults_to_chinese_except_nano_banana() -> None:
    assert resolve_prompt_language("wanx2.1-t2i-turbo") == "zh"
    assert resolve_prompt_language("doubao-seedream-3-0-t2i-250415") == "zh"
    assert resolve_prompt_language("gpt-image-1") == "zh"
    assert resolve_prompt_language("nano-banana") == "en"


@pytest.mark.anyio
async def test_refine_prompt_passes_failed_image_to_llm() -> None:
    captured: dict = {}

    async def fake_ainvoke(messages, images=None):
        captured["messages"] = messages
        captured["images"] = images
        return '{"prompt":"fixed prompt","negative_prompt":"bad anatomy"}'

    with (
        patch("agent.tools.prompt_builder._to_data_url", return_value="data:image/png;base64,abc") as to_data_url,
        patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=fake_ainvoke)),
    ):
        result = await refine_prompt(
            original_prompt=EnhancedPrompt(prompt="old prompt", negative_prompt="blurry"),
            evaluation={
                "score": 0.6,
                "overall_quality_score": 0.4,
                "color_lighting_score": 0.8,
                "architectural_detail_score": 0.4,
                "requirement_score": 0.7,
                "style_score": 0.7,
                "material_score": 0.4,
                "lighting_score": 0.8,
                "composition_score": 0.8,
                "quality_score": 0.8,
                "reference_score": None,
                "fatal_issues": ["透视明显错误"],
                "improvement_focus": "先修正建筑透视",
                "feedback": "材质没有按要求替换",
            },
            failed_image_url="/static/generated/failed.png",
        )

    assert result.prompt == "fixed prompt"
    to_data_url.assert_called_once_with("/static/generated/failed.png")
    assert captured["images"] == ["data:image/png;base64,abc"]
    assert "失败图像" in captured["messages"][0].content
    assert "修正后的中文正向提示词" in captured["messages"][0].content


@pytest.mark.anyio
async def test_enhance_prompt_disables_thinking() -> None:
    captured: dict = {}

    async def fake_ainvoke(messages, images=None, enable_thinking=True):
        captured["enable_thinking"] = enable_thinking
        return '{"prompt":"modern villa","negative_prompt":"blurry"}'

    with patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=fake_ainvoke)):
        result = await enhance_prompt(
            design_state={"building_type": "villa", "style": "modern"},
            reference_analysis=[],
        )

    assert result.prompt == "modern villa"
    assert captured["enable_thinking"] is False


@pytest.mark.anyio
async def test_enhance_prompt_keeps_img2img_edit_context() -> None:
    captured: dict = {}

    async def fake_ainvoke(messages, images=None, enable_thinking=True):
        captured["system"] = messages[0].content
        return '{"prompt":"redesign the entrance canopy","negative_prompt":"blurry"}'

    with patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=fake_ainvoke)):
        result = await enhance_prompt(
            design_state={"building_type": "hotel lobby", "style": "modern"},
            reference_analysis=[
                {
                    "description": "暖色木饰面大堂",
                    "reference_intent": "material",
                    "intent_note": "只参考木材质",
                }
            ],
            latest_user_request="把入口雨棚加深，右侧增加三扇竖向窄窗，不要改变主楼体量",
            control_image={"image_url": "https://example.com/control.png", "note": "保留透视和窗洞节奏"},
            annotated_image={"image_url": "https://example.com/anno.png", "note": "红圈区域换成石材"},
        )

    assert result.prompt == "redesign the entrance canopy"
    assert "用户最新原始要求：把入口雨棚加深，右侧增加三扇竖向窄窗，不要改变主楼体量" in captured["system"]
    assert "图生图底图" in captured["system"]
    assert "保留透视和窗洞节奏" in captured["system"]
    assert "带批注效果图" in captured["system"]
    assert "红圈区域换成石材" in captured["system"]
    assert "只参考木材质" in captured["system"]
    assert "中文正向提示词" in captured["system"]
    assert "prompt 必须是中文" in captured["system"]


@pytest.mark.anyio
async def test_enhance_prompt_can_switch_to_english_for_nano_banana() -> None:
    captured: dict = {}

    async def fake_ainvoke(messages, images=None, enable_thinking=True):
        captured["system"] = messages[0].content
        return '{"prompt":"modern villa","negative_prompt":"blurry"}'

    with patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=fake_ainvoke)):
        await enhance_prompt(
            design_state={"building_type": "villa", "style": "modern"},
            prompt_language="en",
        )

    assert "英文正向提示词" in captured["system"]
    assert "prompt 必须是英文" in captured["system"]
