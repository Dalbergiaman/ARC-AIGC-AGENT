from __future__ import annotations

from agent.graph import _build_prompt_draft, _latest_human_text


def test_prompt_draft_contains_all_fields() -> None:
    template = {"style": "极简主义", "positive": ["minimalist"], "negative": ["ornate"]}
    draft = _build_prompt_draft(
        design_state={"building_type": "villa", "style": "modern"},
        reference_images=[],
        custom_description="用户自定义描述",
        user_prompt_hint="模型补全描述",
        negative_prompt="blurry",
        prompt_template=template,
    )

    assert draft["keywords"]["building_type"] == "villa"
    assert draft["keywords"]["style"] == "modern"
    assert draft["llm_description"]
    assert draft["custom_description"] == "用户自定义描述"
    assert draft["negative_prompt"] == "blurry"
    assert draft["prompt_template"] == template


def test_latest_human_text_ignores_workspace_json_block() -> None:
    from langchain_core.messages import HumanMessage

    text = "继续调整立面\n[用户草稿 workspace: {\"custom_description\":\"abc\"}]"
    assert _latest_human_text([HumanMessage(content=text)]) == "继续调整立面"
