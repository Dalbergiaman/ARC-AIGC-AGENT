"""Style template API routes."""
from __future__ import annotations

from fastapi import APIRouter

from agent.tools.prompt_templates import STYLE_LIBRARY

router = APIRouter(prefix="/api/styles")


@router.get("/templates")
def list_style_templates() -> list[dict]:
    return [
        {
            "style": item["style"],
            "positive": item["positive"],
            "negative": item["negative"],
            "mood": item["mood"],
            "description": item["description"],
        }
        for item in STYLE_LIBRARY.values()
    ]
