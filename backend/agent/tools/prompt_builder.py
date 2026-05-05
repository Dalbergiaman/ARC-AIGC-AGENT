"""Prompt construction tools for the deterministic generation sub-flow.

These are not @tool functions — they are called directly by graph nodes,
not exposed to the agent for autonomous invocation.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from agent.prompts import enhance_prompt_system, refine_prompt_system
from agent.state import DesignState, EvaluationResult, ReferenceImageAnalysis
from agent.tools.prompt_templates import StyleKeywords, get_style
from core.llm.client import LLMClient

_llm = LLMClient()


class EnhancedPrompt(BaseModel):
    prompt: str
    negative_prompt: str


def _parse_prompt_response(raw: str) -> EnhancedPrompt:
    """Parse LLM JSON output into EnhancedPrompt, with one retry on failure."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    return EnhancedPrompt(**data)


async def enhance_prompt(
    design_state: DesignState,
    reference_analysis: list[ReferenceImageAnalysis] | None = None,
    similar_cases: list[dict] | None = None,
) -> EnhancedPrompt:
    """Build image generation prompt from DesignState, reference images, and similar cases.

    Called by enhance_prompt_node in the deterministic generation sub-flow.
    """
    style_keywords: StyleKeywords | None = None
    style = design_state.get("style", "")
    if style:
        kw = get_style(style)
        if kw:
            style_keywords = {**kw, "found": True}

    messages = [
        SystemMessage(content=enhance_prompt_system(
            design_state=design_state,
            reference_analysis=reference_analysis,
            similar_cases=similar_cases,
            style_keywords=style_keywords,
        )),
        HumanMessage(content="请根据以上设计参数生成提示词。"),
    ]

    raw = await _llm.ainvoke(messages)

    try:
        return _parse_prompt_response(raw)
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Retry once with an explicit reminder
        messages.append(HumanMessage(content="请严格按照 JSON 格式输出，只包含 prompt 和 negative_prompt 两个字段。"))
        raw2 = await _llm.ainvoke(messages)
        try:
            return _parse_prompt_response(raw2)
        except (json.JSONDecodeError, ValidationError, KeyError):
            # Fallback: construct a basic prompt from design_state fields
            fallback_prompt = ", ".join(filter(None, [
                design_state.get("building_type", ""),
                design_state.get("style", ""),
                design_state.get("facade_material", ""),
                design_state.get("lighting", ""),
                design_state.get("viewpoint", ""),
                "architectural rendering, high quality, photorealistic",
            ]))
            return EnhancedPrompt(
                prompt=fallback_prompt,
                negative_prompt="blurry, distorted, watermark, low quality, deformed",
            )


async def refine_prompt(
    original_prompt: EnhancedPrompt,
    evaluation: EvaluationResult,
) -> EnhancedPrompt:
    """Refine prompt based on evaluation feedback.

    Called by refine_prompt_node when score < 0.8 and retry_count < 3.
    """
    messages = [
        SystemMessage(content=refine_prompt_system(
            original_prompt=original_prompt.prompt,
            evaluation=evaluation,
        )),
        HumanMessage(content="请根据评估反馈修正提示词。"),
    ]

    raw = await _llm.ainvoke(messages)

    try:
        return _parse_prompt_response(raw)
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Fallback: return original prompt unchanged
        return original_prompt
