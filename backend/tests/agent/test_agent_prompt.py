from __future__ import annotations

from agent.graph import _vision_urls_for_agent
from agent.prompts import _reference_prompt_line, agent_system


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


def test_agent_system_requires_image_specific_reply_guidance() -> None:
    prompt = agent_system(design_state={}, reference_analysis=[], prompt_template=None)

    assert "发送图生图结构底图" in prompt
    assert "体量关系、透视、立面层次" in prompt
    assert "发送参考图且说明了参考方向" in prompt
    assert "全图简要分析" in prompt


def test_vision_urls_for_agent_uses_current_turn_images_only() -> None:
    state = {
        "control_image": {
            "image_url": "https://example.com/old-control.png",
            "sent": True,
        },
        "_current_vision_images": [
            "https://example.com/current-control.png",
            "https://example.com/current-control.png",
            "https://example.com/current-ref.png",
        ],
    }

    assert _vision_urls_for_agent(state) == [
        "https://example.com/current-control.png",
        "https://example.com/current-ref.png",
    ]


def test_reference_prompt_line_is_restrained_by_intent() -> None:
    line = _reference_prompt_line({
        "description": "低机位商业街入口，暖色灯光，深色金属板和玻璃幕墙",
        "reference_intent": "material",
        "facade_material": "深色金属板和玻璃幕墙",
        "lighting": "暖色灯光",
        "viewpoint": "低机位",
        "color_palette": "暖色",
    })

    assert "材质：深色金属板和玻璃幕墙" in line
    assert "参考意图：material" in line
