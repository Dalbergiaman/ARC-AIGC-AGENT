from __future__ import annotations

from api.routes.styles import list_style_templates


def test_list_style_templates_returns_prompt_template_fields() -> None:
    templates = list_style_templates()

    assert templates
    first = templates[0]
    assert set(first) == {"style", "positive", "negative", "mood", "description"}
    assert isinstance(first["positive"], list)
    assert isinstance(first["negative"], list)
