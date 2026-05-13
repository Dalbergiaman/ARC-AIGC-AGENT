from __future__ import annotations

from agent.prompts import agent_system


def test_agent_system_reply_guides_next_design_step() -> None:
    prompt = agent_system(
        design_state={
            "building_type": "商业办公",
            "style": "现代风格",
            "viewpoint": "鸟瞰视角",
            "missing_fields": [],
            "completeness": 1.0,
        },
        reference_analysis=[],
        prompt_template=None,
    )

    assert "第四步：组织 reply" in prompt
    assert "少复述、多引导" in prompt
    assert "每轮围绕 1 个最自然的下一步展开" in prompt
    assert "灵感建议只能写在 `reply` 中" in prompt
    assert "不能擅自写入 `design_state_updates`" in prompt
