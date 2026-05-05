from __future__ import annotations

from agent.state import AgentState

# Fields that must be non-empty for the design to be considered complete
_REQUIRED_FIELDS = ["building_type", "style", "facade_material", "lighting", "viewpoint"]

# Weights for completeness calculation
_FIELD_WEIGHTS: dict[str, float] = {
    "building_type": 0.25,
    "style": 0.25,
    "facade_material": 0.20,
    "lighting": 0.15,
    "viewpoint": 0.15,
}


def compute_completeness(design_state: dict) -> float:
    """Rule-based completeness score 0.0~1.0. Does not trust LLM self-assessment."""
    score = 0.0
    for field, weight in _FIELD_WEIGHTS.items():
        if design_state.get(field, "").strip():
            score += weight
    return round(score, 2)


def compute_missing_fields(design_state: dict) -> list[str]:
    return [f for f in _REQUIRED_FIELDS if not design_state.get(f, "").strip()]


def update_completeness(design_state: dict) -> dict:
    """Return a copy of design_state with missing_fields and completeness updated."""
    updated = dict(design_state)
    updated["missing_fields"] = compute_missing_fields(updated)
    updated["completeness"] = compute_completeness(updated)
    return updated


def make_search_signature(design_state: dict) -> dict:
    return {
        "building_type": design_state.get("building_type", ""),
        "style": design_state.get("style", ""),
        "facade_material": design_state.get("facade_material", ""),
        "surroundings": design_state.get("surroundings", ""),
    }


def signature_changed(current: dict, last: dict | None) -> bool:
    """Return True if any core design field changed since the last RAG search."""
    if last is None:
        return True
    return make_search_signature(current) != last


def reset_generation_run(state: AgentState) -> dict:
    """Return state updates that reset per-task runtime fields for a new generation intent."""
    return {
        "retry_count": 0,
        "best_generation_result": None,
        "current_task_id": None,
        "last_evaluation": None,
    }
