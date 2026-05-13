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
from agent.tools.image_analysis import _to_data_url
from core.llm.client import LLMClient
from core.observability import message_preview, observe, update_current_generation

_llm = LLMClient()

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_WEIGHTS_NO_REF = {
    "overall_quality_score":        0.35,
    "composition_score":            0.20,
    "color_lighting_score":         0.15,
    "architectural_detail_score":   0.15,
    "requirement_score":            0.15,
}

_WEIGHTS_WITH_REF = {
    "overall_quality_score":        0.30,
    "composition_score":            0.17,
    "color_lighting_score":         0.13,
    "architectural_detail_score":   0.13,
    "requirement_score":            0.12,
    "reference_score":              0.15,
}


# ---------------------------------------------------------------------------
# LLM output schema (raw dimension scores only, no weighted total)
# ---------------------------------------------------------------------------

class _RawScores(BaseModel):
    overall_quality_score: float
    composition_score: float
    color_lighting_score: float
    architectural_detail_score: float
    requirement_score: float
    reference_score: float | None = None
    fatal_issues: list[str] = []
    improvement_focus: str = ""
    feedback: str

    @field_validator(
        "overall_quality_score", "composition_score", "color_lighting_score",
        "architectural_detail_score", "requirement_score", "reference_score", mode="before"
    )
    @classmethod
    def clamp(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return max(0.0, min(1.0, float(v)))

    @property
    def has_fatal_issue(self) -> bool:
        return bool(self.fatal_issues)


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

@observe(name="tool:evaluate_generated_image", as_type="generation")
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

    # Convert localhost/relative URLs to base64 data URLs so external VLMs can access them.
    images = [_to_data_url(image_url)] + [
        _to_data_url(r["image_url"]) for r in reference_images if r.get("image_url")
    ]

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

    raw = await _llm.ainvoke(messages, images=images, enable_thinking=False)
    update_current_generation(
        input={
            "image_url": image_url,
            "design_state": design_state,
            "reference_image_count": len(reference_images),
        },
        output=message_preview(raw),
        metadata={"attempt": 1, "has_reference": has_reference},
    )

    try:
        scores = _parse_scores(raw)
    except (json.JSONDecodeError, ValidationError, KeyError):
        # Retry once with explicit reminder
        messages.append(HumanMessage(
            content="请严格按照 JSON 格式输出各维度分数，不要包含其他内容。"
        ))
        raw2 = await _llm.ainvoke(messages, images=images, enable_thinking=False)
        update_current_generation(output=message_preview(raw2), metadata={"attempt": 2})
        try:
            scores = _parse_scores(raw2)
        except (json.JSONDecodeError, ValidationError, KeyError):
            # Fallback: neutral scores so the graph can continue
            scores = _RawScores(
                overall_quality_score=0.5,
                composition_score=0.5,
                color_lighting_score=0.5,
                architectural_detail_score=0.5,
                requirement_score=0.5,
                reference_score=0.5 if has_reference else None,
                fatal_issues=["评估解析失败"],
                improvement_focus="人工检查生成结果",
                feedback="评估解析失败，建议人工检查生成结果",
            )
            update_current_generation(
                metadata={"parse_ok": False, "fallback": True},
                level="WARNING",
                status_message="image evaluation JSON parse failed",
            )

    weighted_score = _compute_weighted_score(scores, has_reference)

    result: EvaluationResult = {
        "score": weighted_score,
        "overall_quality_score": scores.overall_quality_score,
        "composition_score": scores.composition_score,
        "color_lighting_score": scores.color_lighting_score,
        "architectural_detail_score": scores.architectural_detail_score,
        "requirement_score": scores.requirement_score,
        "reference_score": scores.reference_score,
        "fatal_issues": scores.fatal_issues,
        "improvement_focus": scores.improvement_focus,
        "feedback": scores.feedback,
        # Legacy compatibility for existing downstream prompt code and persisted rows.
        "style_score": scores.requirement_score,
        "material_score": scores.architectural_detail_score,
        "lighting_score": scores.color_lighting_score,
        "quality_score": scores.overall_quality_score,
    }
    update_current_generation(output=result, metadata={"parse_ok": True, "score": weighted_score})
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
        print(f"第一眼质量: {result['overall_quality_score']:.2f}")
        print(f"构图与视角: {result['composition_score']:.2f}")
        print(f"色彩与光影: {result['color_lighting_score']:.2f}")
        print(f"建筑细节:   {result['architectural_detail_score']:.2f}")
        print(f"需求符合度: {result['requirement_score']:.2f}")
        print(f"参考图相似度: {result['reference_score']}")
        print(f"严重问题:   {result['fatal_issues']}")
        print(f"修正重点:   {result['improvement_focus']}")
        print(f"改进建议:   {result['feedback']}")

    asyncio.run(main())
