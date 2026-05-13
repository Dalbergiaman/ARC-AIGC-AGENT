from __future__ import annotations

from core.vlm_caption import _thinking_off_params


def test_bailian_caption_disables_thinking() -> None:
    assert _thinking_off_params("bailian") == {"enable_thinking": False}


def test_volcengine_caption_disables_thinking() -> None:
    assert _thinking_off_params("volcengine") == {"thinking": {"type": "disabled"}}
