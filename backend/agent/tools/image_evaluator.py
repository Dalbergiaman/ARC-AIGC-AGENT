"""Image evaluation tool for the deterministic generation sub-flow.

Not a @tool — called directly by evaluate_image_node.
Scoring weights are defined here; LLM outputs raw dimension scores,
backend code computes the weighted total (more reliable than asking LLM to weight).
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError, field_validator

from agent.prompts import evaluate_image_system
from agent.state import DesignState, EvaluationResult, ReferenceImageAnalysis
from core.llm.client import LLMClient

_llm = LLMClient()

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_WEIGHTS_NO_REF = {
    "style_score":       0.30,
    "material_score":    0.20,
    "lighting_score":    0.20,
    "composition_score": 0.15,
    "quality_score":     0.15,
}

_WEIGHTS_WITH_REF = {
    "style_score":       0.25,
    "material_score":    0.15,
    "lighting_score":    0.15,
    "composition_score": 0.10,
    "quality_score":     0.10,
    "reference_score":   0.25,
}


# ---------------------------------------------------------------------------
# LLM output schema (raw dimension scores only, no weighted total)
# ---------------------------------------------------------------------------

class _RawScores(BaseModel):
    style_score: float
    material_score: float
    lighting_score: float
    composition_score: float
    quality_score: float
    reference_score: float | None = None
    feedback: str

    @field_validator(
        "style_score", "material_score", "lighting_score",
        "composition_score", "quality_score", mode="before"
    )
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


def _compute_weighted_score(raw: _RawScores, has_reference: bool) -> float:
    weights = _WEIGHTS_WITH_REF if has_reference else _WEIGHTS_NO_REF
    total = 0.0
    for field, weight in weights.items():
        val = getattr(raw, field)
        if val is None:
            val = 0.0
        total += val * weight
    return round(total, 4)


def _parse_scores(raw_text: str) -> _RawScores:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    return _RawScores(**data)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

async def evaluate_generated_image(
    image_url: str,
    design_state: DesignState,
    reference_images: list[ReferenceImageAnalysis],
) -> EvaluationResult:
    """Evaluate a generated image using VLM multi-dimensional scoring.

    LLM outputs raw dimension scores; weighted total is computed by backend code.
    When reference_images is non-empty, reference_score dimension is included.
    """
    has_reference = bool(reference_images)

    # Build image list: generated image first, then reference images
    images = [image_url] + [r["image_url"] for r in reference_images if r.get("image_url")]

    messages = [
        SystemMessage(content=evaluate_image_system(
            design_state=design_state,
            has_reference=has_reference,
        )),
        HumanMessage(content=(
            "请评估第一张图片（生成图）。"
            + ("后续图片为参考图，请对照评估参考图相似度。" if has_reference else "")
        )),
    ]

    raw = await _llm.ainvoke(messages, images=images)

    try:
        scores = _parse_scores(raw)
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Retry once with explicit reminder
        messages.append(HumanMessage(
            content="请严格按照 JSON 格式输出各维度分数，不要包含其他内容。"
        ))
        raw2 = await _llm.ainvoke(messages, images=images)
        try:
            scores = _parse_scores(raw2)
        except (json.JSONDecodeError, ValidationError, KeyError):
            # Fallback: neutral scores so the graph can continue
            scores = _RawScores(
                style_score=0.5,
                material_score=0.5,
                lighting_score=0.5,
                composition_score=0.5,
                quality_score=0.5,
                reference_score=0.5 if has_reference else None,
                feedback="评估解析失败，建议人工检查生成结果",
            )

    weighted_score = _compute_weighted_score(scores, has_reference)

    result: EvaluationResult = {
        "score": weighted_score,
        "style_score": scores.style_score,
        "material_score": scores.material_score,
        "lighting_score": scores.lighting_score,
        "composition_score": scores.composition_score,
        "quality_score": scores.quality_score,
        "reference_score": scores.reference_score,
        "feedback": scores.feedback,
    }
    return result


if __name__ == "__main__":
    import asyncio

    async def main():
        image_url = "https://pic.rmb.bdstatic.com/bjh/news/3c7d0066e7b8b1d0bb2b9eabb822f2e1.jpeg"

        design_state: DesignState = {
            "building_type": "住宅",
            "style": "现代主义",
            "facade_material": "玻璃幕墙",
            "lighting": "日间自然光",
            "viewpoint": "人视角",
            "season": "",
            "surroundings": "",
            "color_palette": "",
            "special_requirements": "",
            "missing_fields": [],
            "field_confidence": {},
            "completeness": 0.8,
        }

        print("正在评估图片（无参考图）...")
        result = await evaluate_generated_image(
            image_url=image_url,
            design_state=design_state,
            reference_images=[],
        )
        print("\n=== 评估结果（无参考图）===")
        print(f"综合得分:   {result['score']:.4f}")
        print(f"风格符合度: {result['style_score']:.2f}")
        print(f"材质还原度: {result['material_score']:.2f}")
        print(f"光线与氛围: {result['lighting_score']:.2f}")
        print(f"构图与视角: {result['composition_score']:.2f}")
        print(f"整体质量:   {result['quality_score']:.2f}")
        print(f"参考图相似度: {result['reference_score']}")
        print(f"改进建议:   {result['feedback']}")

    asyncio.run(main())
