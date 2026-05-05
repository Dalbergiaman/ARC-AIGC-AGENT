"""LangGraph Agent graph definition.

Current state: C-2 skeleton — nodes are stubs, no tools wired yet.
Tools will be added in C-3 (info-collection), C-4 (generation), C-5 (evaluation).
"""
from __future__ import annotations

import uuid
from typing import Literal

from langgraph.graph import END, START, StateGraph

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from agent.state import AgentState, EvaluationResult, default_agent_state
from agent.state_utils import (
    compute_missing_fields,
    reset_generation_run,
)


# ---------------------------------------------------------------------------
# Node stubs
# ---------------------------------------------------------------------------

async def agent_node(state: AgentState) -> dict:
    """Main decision node: understands intent, updates DesignState, decides next step.

    Stub: echoes back current phase without calling LLM.
    Will be replaced in C-3/C-4 with real LLM + tool calls.
    """
    design_state = state.get("design_state", {})
    missing = compute_missing_fields(design_state)

    if missing:
        return {"phase": "collecting"}

    # All required fields present — trigger generation
    return {
        "phase": "generating",
        "ready_to_generate": True,
        **reset_generation_run(state),
    }


async def rag_gate_node(state: AgentState) -> dict:
    """Rule-based gate: decides whether to call search_similar_cases.

    Stub: always skips RAG for now.
    Will be wired to search_library tool in C-3/D-4.
    """
    return {}


async def enhance_prompt_node(state: AgentState) -> dict:
    """Build the image generation prompt from DesignState + similar cases.

    Stub: returns placeholder prompt.
    Will call enhance_prompt tool in C-4.
    """
    return {"phase": "generating"}


async def generate_image_node(state: AgentState) -> dict:
    """Submit Celery task and poll for result.

    Stub: returns placeholder result.
    Will call generate_image tool in C-4.
    """
    return {"phase": "evaluating"}


async def evaluate_image_node(state: AgentState) -> dict:
    """Evaluate the generated image with VLM.

    Stub: returns a passing score so the graph exits cleanly.
    Will call evaluate_generated_image tool in C-5.
    """
    stub_eval: EvaluationResult = {
        "score": 0.9,
        "style_score": 0.9,
        "material_score": 0.9,
        "lighting_score": 0.9,
        "composition_score": 0.9,
        "quality_score": 0.9,
        "reference_score": None,
        "feedback": "stub evaluation",
    }
    return {"last_evaluation": stub_eval, "phase": "done"}


async def refine_prompt_node(state: AgentState) -> dict:
    """Refine the prompt based on evaluation feedback.

    Stub: pass-through.
    Will call refine_prompt tool in C-5.
    """
    return {}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_agent(state: AgentState) -> Literal["rag_gate", END]:  # type: ignore[valid-type]
    if state.get("ready_to_generate"):
        return "rag_gate"
    return END


def route_after_evaluate(
    state: AgentState,
) -> Literal["refine_prompt", END]:  # type: ignore[valid-type]
    eval_result = state.get("last_evaluation")
    retry_count = state.get("retry_count", 0)

    if eval_result is not None and eval_result.score < 0.8 and retry_count < 3:
        return "refine_prompt"
    return END


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("agent", agent_node)
    g.add_node("rag_gate", rag_gate_node)
    g.add_node("enhance_prompt", enhance_prompt_node)
    g.add_node("generate_image", generate_image_node)
    g.add_node("evaluate_image", evaluate_image_node)
    g.add_node("refine_prompt", refine_prompt_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent)

    # Deterministic generation sub-flow
    g.add_edge("rag_gate", "enhance_prompt")
    g.add_edge("enhance_prompt", "generate_image")
    g.add_edge("generate_image", "evaluate_image")
    g.add_conditional_edges("evaluate_image", route_after_evaluate)

    # Retry loop: refine → generate → evaluate
    g.add_edge("refine_prompt", "generate_image")

    return g


def compile_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    return build_graph().compile(
        checkpointer=checkpointer,
        interrupt_before=["agent"],
    )
