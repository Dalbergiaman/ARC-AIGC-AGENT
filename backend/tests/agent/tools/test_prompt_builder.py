from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.prompt_builder import (
    EnhancedPrompt,
    build_rag_search_query,
    clean_rag_search_query,
    enhance_prompt,
    fallback_rag_search_query,
    refine_prompt,
    resolve_prompt_language,
)


def test_resolve_prompt_language_defaults_to_chinese_except_nano_banana() -> None:
    assert resolve_prompt_language("wan2.7-image-pro") == "zh"
    assert resolve_prompt_language("doubao-seedream-5-0-260128") == "zh"
    assert resolve_prompt_language("gpt-image-2") == "zh"
    assert resolve_prompt_language("nano-banana-pro") == "en"


def test_clean_rag_search_query_strips_markdown_and_newlines() -> None:
    raw = """```text
现代住宅建筑，米白真石漆外立面，黄昏暖光氛围。
人视角街景构图，周边为安静庭院。
```"""

    assert clean_rag_search_query(raw) == (
        "现代住宅建筑，米白真石漆外立面，黄昏暖光氛围。 人视角街景构图，周边为安静庭院。"
    )


def test_fallback_rag_search_query_uses_original_core_fields() -> None:
    assert fallback_rag_search_query({
        "building_type": "别墅",
        "style": "现代主义",
        "facade_material": "玻璃幕墙",
    }) == "别墅 现代主义 玻璃幕墙"


@pytest.mark.anyio
async def test_build_rag_search_query_matches_caption_style_and_disables_thinking() -> None:
    captured: dict = {}

    async def fake_ainvoke(messages, images=None, enable_thinking=True):
        captured["system"] = messages[0].content
        captured["human"] = messages[1].content
        captured["enable_thinking"] = enable_thinking
        return "现代别墅建筑，玻璃幕墙外立面，黄昏暖光氛围。人视角街景构图，周边为安静庭院。"

    with patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=fake_ainvoke)):
        query = await build_rag_search_query(
            enhanced_prompt=EnhancedPrompt(
                prompt="现代别墅，玻璃幕墙，黄昏暖光，高质量建筑效果图",
                negative_prompt="模糊，水印",
            ),
            design_state={"building_type": "别墅", "style": "现代", "facade_material": "玻璃幕墙"},
        )

    assert query == "现代别墅建筑，玻璃幕墙外立面，黄昏暖光氛围。人视角街景构图，周边为安静庭院。"
    assert captured["enable_thinking"] is False
    assert "图库 caption 标准" in captured["system"]
    assert "负向提示词" in captured["human"]


@pytest.mark.anyio
async def test_build_rag_search_query_falls_back_when_llm_fails() -> None:
    with patch("agent.tools.prompt_builder._llm.ainvoke", AsyncMock(side_effect=RuntimeError("boom"))):
        query = await build_rag_search_query(
            enhanced_prompt=EnhancedPrompt(prompt="ignored", negative_prompt="ignored"),
            design_state={"building_type": "办公楼", "style": "极简主义", "facade_material": "金属板"},
        )

    assert query == "办公楼 极简主义 金属板"


@pytest.mark.anyio
async def test_refine_prompt_passes_previous_generation_to_llm() -> None:
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
            previous_generation_url="/static/generated/previous.png",
        )

    assert result.prompt == "fixed prompt"
    to_data_url.assert_called_once_with("/static/generated/previous.png")
    assert captured["images"] == ["data:image/png;base64,abc"]
    assert "上一轮生成图像" in captured["messages"][0].content
    assert "不要默认否定整张图" in captured["messages"][0].content
    assert "失败图像" not in captured["messages"][0].content
    assert "低分生成结果" not in captured["messages"][0].content
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
    assert "建筑效果图品质护栏" in captured["system"]
    assert "画面克制" in captured["system"]
    assert "主体建筑必须是第一视觉中心" in captured["system"]
    assert "玻璃要通透、反射受控" in captured["system"]
    assert "杂乱前景" in captured["system"]
    assert "随机车辆" in captured["system"]
    assert "学生作业感" in captured["system"]
    assert "建筑变形" in captured["system"]


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
