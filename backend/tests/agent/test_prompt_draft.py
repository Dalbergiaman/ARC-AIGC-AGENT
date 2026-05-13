from __future__ import annotations

from agent.graph import _build_prompt_draft, _latest_human_text


def test_prompt_draft_contains_all_fields() -> None:
    template = {"style": "极简主义", "positive": ["minimalist"], "negative": ["ornate"]}
    draft = _build_prompt_draft(
        design_state={"building_type": "villa", "style": "modern"},
        reference_images=[],
        custom_description="用户自定义描述",
        llm_reply_hint="模型补全描述",
        negative_prompt="blurry",
        prompt_template=template,
    )

    assert draft["keywords"]["building_type"] == "villa"
    assert draft["keywords"]["style"] == "modern"
    assert draft["llm_description"]
    assert draft["custom_description"] == "用户自定义描述"
    assert draft["negative_prompt"] == "blurry"
    assert draft["prompt_template"] == template


def test_prompt_draft_llm_description_stays_visual_description() -> None:
    draft = _build_prompt_draft(
        design_state={
            "building_type": "商业办公",
            "style": "日系漫画风格",
            "facade_material": "金属板",
            "lighting": "明亮日光",
            "viewpoint": "低视角平视街景视角",
            "special_requirements": "保留原有窗户，维持底图体量和透视关系不变",
        },
        reference_images=[],
        control_image={"image_url": "/static/uploads/base.png"},
        llm_reply_hint="日系漫画风格商业办公建筑效果图。",
    )

    description = draft["llm_description"]
    assert description.count("日系漫画风格商业办公建筑效果图") == 1
    assert "避免过于笼统" not in description
    assert "补充明确" not in description
    assert "画面主体清晰" not in description
    assert "金属板" in description
    assert "低视角平视街景视角" in description


def test_prompt_draft_does_not_reuse_previous_llm_description() -> None:
    draft = _build_prompt_draft(
        design_state={
            "building_type": "商业办公",
            "style": "现代风格",
            "viewpoint": "鸟瞰视角",
        },
        reference_images=[],
        llm_reply_hint="更新为鸟瞰视角。",
    )

    description = draft["llm_description"]
    assert "鸟瞰视角" in description
    assert "人视角" not in description


def test_prompt_draft_prefers_complete_llm_description_without_field_duplication() -> None:
    draft = _build_prompt_draft(
        design_state={
            "building_type": "住宅",
            "style": "温润新中式",
            "facade_material": "主体米白色真石漆，下部入口采用黄色真石漆",
            "viewpoint": "人视视角（低于参考底图视角）",
        },
        reference_images=[],
        control_image={"image_url": "/static/uploads/base.png"},
        llm_reply_hint=(
            "温润新中式住宅建筑，采用低于参考底图的人视角度呈现，"
            "外立面主体为米白色真石漆，下部入口区域使用黄色真石漆，质感温润雅致。"
        ),
    )

    description = draft["llm_description"]
    assert description.count("温润新中式") == 1
    assert description.count("米白色真石漆") == 1
    assert description.count("黄色真石漆") == 1
    assert "建筑效果图。 外立面采用" not in description
    assert "观看视角为" not in description
    assert "以图生图底图作为建筑要素参考" in description


def test_latest_human_text_ignores_workspace_json_block() -> None:
    from langchain_core.messages import HumanMessage

    text = "继续调整立面\n[用户草稿 workspace: {\"custom_description\":\"abc\"}]"
    assert _latest_human_text([HumanMessage(content=text)]) == "继续调整立面"
