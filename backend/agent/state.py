from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import MessagesState


# ---------------------------------------------------------------------------
# Sub-structures (TypedDict for LangGraph JSON serialization compatibility)
# ---------------------------------------------------------------------------

class DesignState(TypedDict, total=False):
    building_type: str
    style: str
    facade_material: str
    lighting: str
    viewpoint: str
    season: str
    surroundings: str
    color_palette: str
    special_requirements: str
    missing_fields: list[str]
    field_confidence: dict[str, float]
    completeness: float


class ReferenceImageAnalysis(TypedDict, total=False):
    image_url: str
    building_type: str
    style: str
    facade_material: str
    lighting: str
    viewpoint: str
    color_palette: str
    description: str


class GenerationResult(TypedDict, total=False):
    image_url: str
    provider: str
    generation_time: float
    score: float
    raw_response: dict


class EvaluationResult(TypedDict):
    score: float
    style_score: float
    material_score: float
    lighting_score: float
    composition_score: float
    quality_score: float
    reference_score: float | None
    feedback: str


class ImageRecord(TypedDict):
    id: str
    image_url: str
    caption: str
    prompt: str
    design_state: dict
    provider: str


# ---------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------

class AgentState(MessagesState):
    design_state: DesignState
    reference_images: list[ReferenceImageAnalysis]
    ready_to_generate: bool
    generation_results: list[GenerationResult]
    retry_count: int
    last_evaluation: EvaluationResult | None
    similar_cases: list[ImageRecord]
    last_search_signature: dict | None
    best_generation_result: GenerationResult | None
    current_task_id: str | None
    phase: Literal["collecting", "generating", "evaluating", "interrupted", "done"]
    turn_id: str
    run_id: str
    # Internal fields passed between generation sub-flow nodes (not persisted long-term)
    _enhanced_prompt: dict | None
    _current_gen_result: GenerationResult | None


def default_agent_state() -> dict:
    """Return a fresh AgentState dict with all fields initialized."""
    return {
        "messages": [],
        "design_state": {
            "building_type": "",
            "style": "",
            "facade_material": "",
            "lighting": "",
            "viewpoint": "",
            "season": "",
            "surroundings": "",
            "color_palette": "",
            "special_requirements": "",
            "missing_fields": [],
            "field_confidence": {},
            "completeness": 0.0,
        },
        "reference_images": [],
        "ready_to_generate": False,
        "generation_results": [],
        "retry_count": 0,
        "last_evaluation": None,
        "similar_cases": [],
        "last_search_signature": None,
        "best_generation_result": None,
        "current_task_id": None,
        "phase": "collecting",
        "turn_id": "",
        "run_id": "",
        "_enhanced_prompt": None,
        "_current_gen_result": None,
    }
