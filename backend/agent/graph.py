"""LangGraph Agent graph definition."""
from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import agent_system
from agent.state import AgentState, EvaluationResult, default_agent_state
from agent.state_utils import (
    reset_generation_run,
    signature_changed,
    make_search_signature,
    update_completeness,
)
from agent.tools.image_analysis import analyze_reference_image
from agent.tools.style_lookup import lookup_style_keywords
from agent.tools.search_library import search_similar_cases
from core.llm.client import LLMClient

_llm = LLMClient()

# Regex to find image URLs in message content
_IMAGE_URL_RE = re.compile(r'https?://\S+\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)


def _extract_image_urls(messages: list) -> list[str]:
    """Extract image URLs from the latest human message."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            return _IMAGE_URL_RE.findall(content)
    return []


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def agent_node(state: AgentState) -> dict:
    """Main decision node: understands intent, updates DesignState, decides next step.

    Tool calls are rule-based (deterministic), not LLM-driven:
    - Image URL in latest message → analyze_reference_image
    - Style field just set → lookup_style_keywords
    - RAG gate is handled by rag_gate_node, not here
    """
    design_state = dict(state.get("design_state") or {})
    reference_images = list(state.get("reference_images") or [])
    similar_cases = list(state.get("similar_cases") or [])
    messages = list(state.get("messages") or [])
    style_keywords = None
    updates: dict = {}

    # --- Rule 1: analyze any new image URLs in the latest message ---
    image_urls = _extract_image_urls(messages)
    known_urls = {r.get("image_url") for r in reference_images}
    new_urls = [u for u in image_urls if u not in known_urls]
    for url in new_urls:
        analysis = await analyze_reference_image.ainvoke({"image_url": url})
        reference_images.append(analysis)
        # Pre-fill design_state from image analysis if fields are empty
        for field in ("building_type", "style", "facade_material", "lighting", "viewpoint"):
            if not design_state.get(field) and analysis.get(field):
                design_state[field] = analysis[field]
    if new_urls:
        updates["reference_images"] = reference_images

    # --- Rule 2: look up style keywords when style is set ---
    current_style = design_state.get("style", "")
    if current_style:
        kw_result = await lookup_style_keywords.ainvoke({"style": current_style})
        if kw_result.get("found"):
            style_keywords = kw_result

    # --- Call LLM for intent understanding and DesignState update ---
    llm_messages = [
        SystemMessage(content=agent_system(
            design_state=design_state,
            style_keywords=style_keywords,
            reference_analysis=reference_images,
            similar_cases=similar_cases,
        )),
        *messages,
    ]

    raw = await _llm.ainvoke(llm_messages)

    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            **updates,
            "design_state": update_completeness(design_state),
            "messages": [AIMessage(content="请继续描述您的设计需求。")],
            "phase": "collecting",
        }

    # Merge LLM-proposed design_state updates
    llm_updates = data.get("design_state_updates", {})
    for key, val in llm_updates.items():
        if val and key not in ("field_confidence",):
            design_state[key] = val
    if "field_confidence" in llm_updates and isinstance(llm_updates["field_confidence"], dict):
        existing = design_state.get("field_confidence", {})
        existing.update(llm_updates["field_confidence"])
        design_state["field_confidence"] = existing

    design_state = update_completeness(design_state)

    ready = bool(data.get("ready_to_generate", False))
    phase = data.get("phase", "collecting")
    reply = data.get("reply", "")

    result: dict = {
        **updates,
        "design_state": design_state,
        "messages": [AIMessage(content=reply)] if reply else [],
        "phase": phase,
        "ready_to_generate": ready,
    }

    if ready:
        result.update(reset_generation_run(state))

    return result

    design_state = update_completeness(design_state)

    ready = bool(data.get("ready_to_generate", False))
    phase = data.get("phase", "collecting")
    reply = data.get("reply", "")

    result: dict = {
        "design_state": design_state,
        "messages": [AIMessage(content=reply)] if reply else [],
        "phase": phase,
        "ready_to_generate": ready,
    }

    if ready:
        result.update(reset_generation_run(state))

    return result


async def rag_gate_node(state: AgentState) -> dict:
    """Rule-based gate: calls search_similar_cases when conditions are met.

    Triggers RAG if:
    - similar_cases is empty and building_type or style is set, OR
    - core design fields changed since last search
    """
    design_state = dict(state.get("design_state") or {})
    similar_cases = list(state.get("similar_cases") or [])
    last_sig = state.get("last_search_signature")

    building_type = design_state.get("building_type", "")
    style = design_state.get("style", "")

    should_search = (
        (building_type or style)
        and (not similar_cases or signature_changed(design_state, last_sig))
    )

    if not should_search:
        return {}

    query = " ".join(filter(None, [building_type, style,
                                    design_state.get("facade_material", "")]))
    results = await search_similar_cases.ainvoke({
        "query": query,
        "building_type": building_type,
        "style": style,
    })

    return {
        "similar_cases": results,
        "last_search_signature": make_search_signature(design_state),
    }


async def enhance_prompt_node(state: AgentState) -> dict:
    """Build the image generation prompt from DesignState + similar cases.

    Stub: returns placeholder. Will call enhance_prompt tool in C-4.
    """
    return {"phase": "generating"}


async def generate_image_node(state: AgentState) -> dict:
    """Submit Celery task and poll for result.

    Stub: returns placeholder. Will call generate_image tool in C-4.
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

    Stub: pass-through. Will call refine_prompt tool in C-5.
    """
    return {}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_agent(state: AgentState) -> Literal["rag_gate", END]:  # type: ignore[valid-type]
    if state.get("ready_to_generate"):
        return "rag_gate"
    return END


def route_after_evaluate(state: AgentState) -> Literal["refine_prompt", END]:  # type: ignore[valid-type]
    eval_result = state.get("last_evaluation")
    retry_count = state.get("retry_count", 0)

    if eval_result is not None and eval_result["score"] < 0.8 and retry_count < 3:
        return "refine_prompt"
    return END


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("agent", agent_node)
    g.add_node("rag_gate", rag_gate_node)
    g.add_node("enhance_prompt", enhance_prompt_node)
    g.add_node("generate_image", generate_image_node)
    g.add_node("evaluate_image", evaluate_image_node)
    g.add_node("refine_prompt", refine_prompt_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent)

    g.add_edge("rag_gate", "enhance_prompt")
    g.add_edge("enhance_prompt", "generate_image")
    g.add_edge("generate_image", "evaluate_image")
    g.add_conditional_edges("evaluate_image", route_after_evaluate)

    g.add_edge("refine_prompt", "generate_image")

    return g


def compile_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    return build_graph().compile(
        checkpointer=checkpointer,
        interrupt_before=["agent"],
    )
