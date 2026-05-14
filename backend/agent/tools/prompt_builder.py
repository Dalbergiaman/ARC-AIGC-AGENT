"""Prompt construction tools for the deterministic generation sub-flow.

These are not @tool functions — they are called directly by graph nodes,
not exposed to the agent for autonomous invocation.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from agent.prompts import enhance_prompt_system, rag_search_query_system, refine_prompt_system
from agent.state import AnnotatedImage, ControlImage, DesignState, EvaluationResult, ReferenceImageAnalysis
from agent.tools.image_analysis import _to_data_url
from core.llm.client import LLMClient
from core.observability import message_preview, observe, update_current_generation

_llm = LLMClient()


class EnhancedPrompt(BaseModel):
    prompt: str
    negative_prompt: str


def clean_rag_search_query(raw: str, max_chars: int = 260) -> str:
    """Normalize LLM output into a single compact retrieval query."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("text"):
            text = text.lstrip()[4:]
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    text = text.strip("`# -*\t\n\r")
    return text[:max_chars].strip()


def fallback_rag_search_query(design_state: DesignState) -> str:
    return " ".join(filter(None, [
        str(design_state.get("building_type", "") or ""),
        str(design_state.get("style", "") or ""),
        str(design_state.get("facade_material", "") or ""),
    ])).strip()


def resolve_prompt_language(image_model: str | None = None) -> str:
    """Default to Chinese prompts; keep English for models known to prefer it."""
    model = (image_model or "").lower()
    if "nano-banana" in model:
        return "en"
    return "zh"


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


@observe(name="tool:enhance_prompt", as_type="generation")
async def enhance_prompt(
    design_state: DesignState,
    reference_analysis: list[ReferenceImageAnalysis] | None = None,
    llm_description: str = "",
    custom_description: str = "",
    prompt_template: dict | None = None,
    latest_user_request: str = "",
    control_image: ControlImage | None = None,
    annotated_image: AnnotatedImage | None = None,
    prompt_language: str = "zh",
) -> EnhancedPrompt:
    """Build image generation prompt from DesignState and reference images.

    Called by enhance_prompt_node in the deterministic generation sub-flow.
    """
    messages = [
        SystemMessage(content=enhance_prompt_system(
            design_state=design_state,
            reference_analysis=reference_analysis,
            llm_description=llm_description,
            custom_description=custom_description,
            prompt_template=prompt_template,
            latest_user_request=latest_user_request,
            control_image=control_image,
            annotated_image=annotated_image,
            prompt_language=prompt_language,
        )),
        HumanMessage(content="请根据以上设计参数生成提示词。"),
    ]

    raw = await _llm.ainvoke(messages, enable_thinking=False)
    update_current_generation(
        input={
            "design_state": design_state,
            "reference_image_count": len(reference_analysis or []),
            "has_prompt_template": bool(prompt_template),
            "has_latest_user_request": bool(latest_user_request),
            "has_control_image": bool(control_image),
            "has_annotated_image": bool(annotated_image),
            "prompt_language": prompt_language,
        },
        output=message_preview(raw),
        metadata={"attempt": 1},
    )

    try:
        parsed = _parse_prompt_response(raw)
        update_current_generation(output=parsed.model_dump(), metadata={"parse_ok": True})
        return parsed
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Retry once with an explicit reminder
        messages.append(HumanMessage(content="请严格按照 JSON 格式输出，只包含 prompt 和 negative_prompt 两个字段。"))
        raw2 = await _llm.ainvoke(messages, enable_thinking=False)
        update_current_generation(output=message_preview(raw2), metadata={"attempt": 2})
        try:
            parsed = _parse_prompt_response(raw2)
            update_current_generation(output=parsed.model_dump(), metadata={"parse_ok": True, "retried": True})
            return parsed
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
            fallback = EnhancedPrompt(
                prompt=fallback_prompt,
                negative_prompt="blurry, distorted, watermark, low quality, deformed",
            )
            update_current_generation(
                output=fallback.model_dump(),
                metadata={"parse_ok": False, "fallback": True},
                level="WARNING",
                status_message="enhance_prompt JSON parse failed",
            )
            return fallback


@observe(name="tool:build_rag_search_query", as_type="generation")
async def build_rag_search_query(
    enhanced_prompt: EnhancedPrompt,
    design_state: DesignState,
) -> str:
    """Rewrite the final image prompt into a caption-style RAG retrieval query."""
    fallback = fallback_rag_search_query(design_state)
    messages = [
        SystemMessage(content=rag_search_query_system(design_state=design_state)),
        HumanMessage(content=(
            "请把下面最终生图提示词改写成图库检索专用文本。\n"
            f"正向提示词：{enhanced_prompt.prompt}\n"
            f"负向提示词：{enhanced_prompt.negative_prompt}"
        )),
    ]

    try:
        raw = await _llm.ainvoke(messages, enable_thinking=False)
        query = clean_rag_search_query(raw)
    except Exception as exc:
        update_current_generation(
            input={"prompt": message_preview(enhanced_prompt.prompt), "design_state": design_state},
            output={"query": fallback, "error": str(exc), "fallback": True},
            level="WARNING",
            status_message=f"rag search query generation failed: {exc}",
        )
        return fallback

    if not query:
        update_current_generation(
            input={"prompt": message_preview(enhanced_prompt.prompt), "design_state": design_state},
            output={"query": fallback, "empty_output": True, "fallback": True},
            level="WARNING",
            status_message="rag search query generation returned empty output",
        )
        return fallback

    update_current_generation(
        input={"prompt": message_preview(enhanced_prompt.prompt), "design_state": design_state},
        output={"query": query, "fallback": False},
    )
    return query


@observe(name="tool:refine_prompt", as_type="generation")
async def refine_prompt(
    original_prompt: EnhancedPrompt,
    evaluation: EvaluationResult,
    previous_generation_url: str | None = None,
    prompt_language: str = "zh",
) -> EnhancedPrompt:
    """Refine prompt based on evaluation feedback and the previous generation.

    Called by refine_prompt_node when automatic retry policy decides the image needs repair.
    """
    images = [_to_data_url(previous_generation_url)] if previous_generation_url else None
    messages = [
        SystemMessage(content=refine_prompt_system(
            original_prompt=original_prompt.prompt,
            evaluation=evaluation,
            has_previous_generation=bool(previous_generation_url),
            prompt_language=prompt_language,
        )),
        HumanMessage(content=(
            "请根据评估反馈和上一轮生成图像修正提示词。第一张图是上一轮生成结果。"
            if previous_generation_url
            else "请根据评估反馈修正提示词。"
        )),
    ]

    raw = await _llm.ainvoke(messages, images=images)
    update_current_generation(
        input={
            "original_prompt": original_prompt.model_dump(),
            "evaluation": evaluation,
            "previous_generation_url": previous_generation_url,
            "has_previous_generation": bool(previous_generation_url),
            "prompt_language": prompt_language,
        },
        output=message_preview(raw),
        metadata={"attempt": 1},
    )

    try:
        parsed = _parse_prompt_response(raw)
        update_current_generation(output=parsed.model_dump(), metadata={"parse_ok": True})
        return parsed
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Fallback: return original prompt unchanged
        update_current_generation(
            output=original_prompt.model_dump(),
            metadata={"parse_ok": False, "fallback": True},
            level="WARNING",
            status_message="refine_prompt JSON parse failed",
        )
        return original_prompt
