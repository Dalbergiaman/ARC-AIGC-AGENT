"""LangGraph Agent graph definition."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import agent_system
from agent.state import AgentState, EvaluationResult, PromptDraft, default_agent_state
from agent.state_utils import (
    reset_generation_run,
    signature_changed,
    make_search_signature,
    update_completeness,
)
from agent.tools.image_analysis import analyze_reference_image
from agent.tools.image_evaluator import evaluate_generated_image
from agent.tools.image_generator import NullEmitter, generate_image
from core.llm.streaming import get_current_emitter
from agent.tools.prompt_builder import EnhancedPrompt, enhance_prompt, refine_prompt
from agent.tools.style_lookup import lookup_style_keywords
from agent.tools.search_library import search_similar_cases
from core.llm.client import LLMClient
from core.observability import message_preview, observe, update_current_span

_llm = LLMClient()

# Regex to find image URLs in message content
_IMAGE_URL_RE = re.compile(r'https?://\S+\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)

_GENERATION_NEGATIVE_RE = re.compile(
    r"(不要|别|先不|暂不|不用|无需|先别)\s*(生成|出图|渲染)|"
    r"(do\s+not|don't|dont|no)\s+(generate|render|create\s+(an?\s+)?image|generation)",
    re.IGNORECASE,
)
_GENERATION_INTENT_RE = re.compile(
    r"(生成图片|生成图像|开始生成|开始出图|开始渲染|帮我出一张|帮我生成一张|出图|渲染|生成)|"
    r"\b(generate|render)\b|"
    r"\b(create|make)\s+(an?\s+)?(image|rendering|render)\b|"
    r"\bstart\s+(generation|rendering)\b",
    re.IGNORECASE,
)


def _prompt_keywords(design_state: dict, style_keywords: dict | None = None) -> dict[str, str]:
    keywords: dict[str, str] = {}
    mapping = {
        "building_type": "building_type",
        "style": "style",
        "facade_material": "facade_material",
        "lighting": "lighting",
        "viewpoint": "viewpoint",
        "season": "season",
        "surroundings": "surroundings",
        "color_palette": "color_palette",
        "special_requirements": "special_requirements",
    }
    for key, target in mapping.items():
        value = design_state.get(key)
        if value:
            keywords[target] = str(value)
    if style_keywords and style_keywords.get("found"):
        pos = style_keywords.get("positive", [])
        neg = style_keywords.get("negative", [])
        if pos:
            keywords["style_positive"] = ", ".join(pos)
        if neg:
            keywords["style_negative"] = ", ".join(neg)
    return keywords


def _compose_llm_description(
    design_state: dict,
    reference_images: list[dict],
    similar_cases: list[dict],
    user_prompt_hint: str = "",
    llm_reply_hint: str = "",
) -> str:
    parts: list[str] = []
    building_type = design_state.get("building_type", "")
    style = design_state.get("style", "")
    facade_material = design_state.get("facade_material", "")
    lighting = design_state.get("lighting", "")
    viewpoint = design_state.get("viewpoint", "")
    surroundings = design_state.get("surroundings", "")
    color_palette = design_state.get("color_palette", "")
    special_requirements = design_state.get("special_requirements", "")

    if building_type or style:
        parts.append("画面主体清晰、结构完整，强调建筑类型与整体风格的一致性。")
    if facade_material or color_palette:
        parts.append("外立面材质和色彩需要写得更具体，避免过于笼统。")
    if lighting or viewpoint:
        parts.append("补充明确的光线方向、时间感和观看视角，让画面更有摄影感。")
    if surroundings:
        parts.append("把建筑与周边环境的关系交代出来，避免主体悬浮。")
    if reference_images:
        parts.append("参考图中的构图、体块关系和视觉重心需要被吸收进描述里。")
    if similar_cases:
        parts.append("描述需要参考历史案例的成熟表达，但保持当前项目的独立性。")
    if special_requirements:
        parts.append(f"特别要求是：{special_requirements}。")
    if user_prompt_hint:
        parts.append(user_prompt_hint.strip())
    if llm_reply_hint:
        parts.append(llm_reply_hint.strip())
    if not parts:
        parts.append("画面描述保持自然完整，尽量补足人物语言中的细节表达。")
    return " ".join(parts)


def _build_prompt_draft(
    design_state: dict,
    reference_images: list[dict],
    similar_cases: list[dict],
    custom_description: str = "",
    user_prompt_hint: str = "",
    llm_reply_hint: str = "",
    style_keywords: dict | None = None,
    negative_prompt: str = "",
    prompt_template: dict | None = None,
) -> PromptDraft:
    return {
        "keywords": _prompt_keywords(design_state, style_keywords),
        "llm_description": _compose_llm_description(
            design_state=design_state,
            reference_images=reference_images,
            similar_cases=similar_cases,
            user_prompt_hint=user_prompt_hint,
            llm_reply_hint=llm_reply_hint,
        ),
        "custom_description": custom_description or "",
        "negative_prompt": negative_prompt or "",
        "prompt_template": prompt_template,
    }


def _extract_image_urls(messages: list) -> list[str]:
    """Extract image URLs from the latest human message."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            return _IMAGE_URL_RE.findall(content)
    return []


def _latest_human_text(messages: list) -> str:
    """Return the latest user-authored text for deterministic intent gates."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            return content.split("\n[用户草稿 prompt:", 1)[0].split("\n[用户草稿 workspace:", 1)[0]
    return ""


def has_explicit_generation_intent(messages: list) -> bool:
    """Return True only when the latest user message explicitly asks to generate.

    This is the hard backend gate for image generation. The LLM may still infer
    design state, but it cannot trigger the generation sub-flow on its own.
    """
    text = _latest_human_text(messages).strip()
    if not text:
        return False
    if _GENERATION_NEGATIVE_RE.search(text):
        return False
    return _GENERATION_INTENT_RE.search(text) is not None


def resolve_generation_gate(llm_phase: str, explicit_generation_intent: bool) -> tuple[bool, str]:
    """Resolve final generation control state from deterministic user intent."""
    if explicit_generation_intent:
        return True, "generating"
    if llm_phase == "generating":
        return False, "collecting"
    return False, llm_phase


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@observe(name="node:agent", as_type="agent")
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
    explicit_generation_intent = has_explicit_generation_intent(messages)
    style_keywords = None
    workspace = dict(state.get("workspace") or {})
    custom_description = str(workspace.get("custom_description", "") or "")
    prompt_hint = str(workspace.get("llm_description", "") or "")
    prompt_template = workspace.get("prompt_template") if isinstance(workspace.get("prompt_template"), dict) else None
    updates: dict = {}
    update_current_span(
        input={
            "latest_message": message_preview(messages[-1].content) if messages else "",
            "design_state": design_state,
            "reference_image_count": len(reference_images),
            "similar_case_count": len(similar_cases),
        },
        metadata={
            "phase": state.get("phase"),
            "retry_count": state.get("retry_count", 0),
            "ready_to_generate": state.get("ready_to_generate", False),
            "explicit_generation_intent": explicit_generation_intent,
        },
    )

    # --- Rule 1: analyze images that have a URL but no description yet ---
    # Pre-filled entries from input_state have image_url + intent/note but no VLM analysis.
    # Also pick up any URLs embedded in message text as a fallback.
    known_analyzed = {r.get("image_url") for r in reference_images if r.get("description")}
    pending_urls = [
        r.get("image_url") for r in reference_images
        if r.get("image_url") and not r.get("description")
    ]
    text_urls = _extract_image_urls(messages)
    # Add text-extracted URLs not already tracked at all
    all_tracked = {r.get("image_url") for r in reference_images}
    for u in text_urls:
        if u not in all_tracked:
            pending_urls.append(u)
    # Deduplicate while preserving order
    seen: set[str] = set()
    new_urls = [u for u in pending_urls if u and not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]

    for url in new_urls:
        analysis = await analyze_reference_image.ainvoke({"image_url": url})
        # Merge user-annotated intent/note from any pre-filled entry for this URL
        pre = next((r for r in reference_images if r.get("image_url") == url), {})
        if pre.get("file_id"):
            analysis["file_id"] = pre["file_id"]
        if pre.get("reference_intent"):
            analysis["reference_intent"] = pre["reference_intent"]
        if pre.get("intent_note"):
            analysis["intent_note"] = pre["intent_note"]
        emitter = get_current_emitter()
        if emitter is not None:
            await emitter.emit("reference_image_update", analysis)
        # Replace the pre-filled stub (or append if new)
        reference_images = [r for r in reference_images if r.get("image_url") != url]
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
            prompt_template=prompt_template,
        )),
        *messages,
    ]

    emitter = get_current_emitter()
    raw_parts: list[str] = []

    try:
        stream = await _llm.astream(llm_messages)
        async for chunk in stream:
            if not chunk:
                continue
            raw_parts.append(chunk)
            if emitter is not None:
                await emitter.emit("text_delta", {"content": chunk})
        raw = "".join(raw_parts)
    except Exception:
        raw = await _llm.ainvoke(llm_messages)
        if emitter is not None and raw:
            await emitter.emit("text_delta", {"content": raw})

    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        update_current_span(
            output={
                "parse_ok": False,
                "raw": message_preview(raw),
                "design_state": update_completeness(design_state),
                "phase": "collecting",
            },
            level="WARNING",
            status_message="agent JSON parse failed",
        )
        return {
            **updates,
            "design_state": update_completeness(design_state),
            "messages": [] if emitter is not None else [AIMessage(content=raw or "请继续描述您的设计需求。")],
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
    llm_description = str(data.get("llm_description", "") or "")
    prompt_draft = _build_prompt_draft(
        design_state=design_state,
        reference_images=reference_images,
        similar_cases=similar_cases,
        custom_description=custom_description,
        user_prompt_hint=prompt_hint,
        llm_reply_hint=llm_description,
        style_keywords=style_keywords,
        negative_prompt=str(workspace.get("negative_prompt", "") or ""),
        prompt_template=prompt_template,
    )
    if emitter is not None:
        await emitter.emit("prompt_update", {
            **prompt_draft,
            "source": "agent_node",
        })

    llm_ready = bool(data.get("ready_to_generate", False))
    ready, phase = resolve_generation_gate(
        llm_phase=data.get("phase", "collecting"),
        explicit_generation_intent=explicit_generation_intent,
    )
    result: dict = {
        **updates,
        "design_state": design_state,
        "workspace": prompt_draft,
        "messages": [] if emitter is not None else [AIMessage(content=raw)] if raw else [],
        "phase": phase,
        "ready_to_generate": ready,
    }

    if ready:
        result.update(reset_generation_run(state))

    update_current_span(
        output={
            "parse_ok": True,
            "reply": message_preview(data.get("reply", "")),
            "llm_description": message_preview(llm_description),
            "design_state": design_state,
            "llm_ready_to_generate": llm_ready,
            "explicit_generation_intent": explicit_generation_intent,
            "ready_to_generate": ready,
            "phase": phase,
            "reference_image_count": len(reference_images),
        }
    )
    return result


@observe(name="node:rag_gate")
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
        update_current_span(
            input={"design_state": design_state, "last_search_signature": last_sig},
            output={"searched": False, "reason": "signature unchanged or missing core fields"},
        )
        return {}

    query = " ".join(filter(None, [building_type, style,
                                    design_state.get("facade_material", "")]))
    results = await search_similar_cases.ainvoke({
        "query": query,
        "building_type": building_type,
        "style": style,
    })

    update_current_span(
        input={"query": query, "building_type": building_type, "style": style},
        output={"searched": True, "result_count": len(results)},
    )
    return {
        "similar_cases": results,
        "last_search_signature": make_search_signature(design_state),
    }


@observe(name="node:enhance_prompt")
async def enhance_prompt_node(state: AgentState) -> dict:
    """Build the image generation prompt from DesignState + similar cases."""
    design_state = dict(state.get("design_state") or {})
    reference_images = list(state.get("reference_images") or [])
    similar_cases = list(state.get("similar_cases") or [])

    enhanced = await enhance_prompt(
        design_state=design_state,
        reference_analysis=reference_images,
        similar_cases=similar_cases,
        llm_description=str((state.get("workspace") or {}).get("llm_description", "") or ""),
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
    )
    workspace = _build_prompt_draft(
        design_state=design_state,
        reference_images=reference_images,
        similar_cases=similar_cases,
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        user_prompt_hint=str((state.get("workspace") or {}).get("llm_description", "") or ""),
        llm_reply_hint=enhanced.prompt,
        negative_prompt=enhanced.negative_prompt,
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
    )
    emitter = get_current_emitter()
    if emitter is not None:
        workspace["llm_description"] = enhanced.prompt
        workspace["negative_prompt"] = enhanced.negative_prompt
        await emitter.emit("prompt_update", {
            **workspace,
            "source": "enhance_prompt",
        })

    update_current_span(
        input={
            "design_state": design_state,
            "reference_image_count": len(reference_images),
            "similar_case_count": len(similar_cases),
        },
        output=enhanced.model_dump(),
    )
    return {
        "phase": "generating",
        "_enhanced_prompt": enhanced,  # passed to generate_image_node via state
        "workspace": workspace,
    }


@observe(name="node:generate_image")
async def generate_image_node(state: AgentState) -> dict:
    """Submit Celery task and poll for result."""
    enhanced_prompt: EnhancedPrompt | None = state.get("_enhanced_prompt")
    if enhanced_prompt is None:
        # Fallback: build a minimal prompt from design_state
        design_state = dict(state.get("design_state") or {})
        enhanced_prompt = EnhancedPrompt(
            prompt=", ".join(filter(None, [
                design_state.get("building_type", ""),
                design_state.get("style", ""),
                "architectural rendering, high quality",
            ])),
            negative_prompt="blurry, distorted, watermark, low quality",
        )

    retry_count = state.get("retry_count", 0)
    best = state.get("best_generation_result")
    update_current_span(
        input={
            "prompt": enhanced_prompt.prompt,
            "negative_prompt": enhanced_prompt.negative_prompt,
            "retry_count": retry_count,
            "has_best_result": best is not None,
        }
    )

    emitter = get_current_emitter() or NullEmitter()
    try:
        gen_result = await generate_image(
            state=state,
            enhanced_prompt=enhanced_prompt,
            emitter=emitter,
        )
    except TimeoutError:
        update_current_span(level="WARNING", status_message="generation timeout")
        return {
            "retry_count": retry_count + 1,
            "phase": "evaluating",
        }
    except asyncio.CancelledError:
        update_current_span(level="WARNING", status_message="generation interrupted")
        return {"phase": "interrupted"}

    generation_results = list(state.get("generation_results") or [])
    generation_results.append(gen_result)
    workspace = dict(state.get("workspace") or {})

    update_current_span(
        output={
            "image_url": gen_result.get("image_url"),
            "provider": gen_result.get("provider"),
            "generation_time": gen_result.get("generation_time"),
            "result_count": len(generation_results),
        }
    )
    return {
        "generation_results": generation_results,
        "phase": "evaluating",
        "_current_gen_result": gen_result,
        "_current_generation_persist": {
            "task_id": gen_result.get("task_id"),
            "prompt": enhanced_prompt.prompt,
            "negative_prompt": enhanced_prompt.negative_prompt,
            "provider": gen_result.get("provider"),
            "image_url": gen_result.get("image_url"),
            "status": "done",
            "score": gen_result.get("score"),
            "raw_response": gen_result.get("raw_response", {}),
            "workspace": workspace,
        },
    }


@observe(name="node:evaluate_image", as_type="evaluator")
async def evaluate_image_node(state: AgentState) -> dict:
    """Evaluate the generated image with VLM multi-dimensional scoring."""
    gen_result = state.get("_current_gen_result")
    if gen_result is None:
        # No image to evaluate — skip with neutral score
        update_current_span(output={"skipped": True, "reason": "no current generation result"})
        return {"phase": "done"}

    design_state = dict(state.get("design_state") or {})
    reference_images = list(state.get("reference_images") or [])

    evaluation = await evaluate_generated_image(
        image_url=gen_result["image_url"],
        design_state=design_state,
        reference_images=reference_images,
    )

    # Track best result across retries
    scored = {**gen_result, "score": evaluation["score"]}
    best = state.get("best_generation_result")
    if best is None or scored["score"] > best.get("score", 0):
        best = scored
    persist_payload = dict(state.get("_current_generation_persist") or {})
    persist_payload.update(
        {
            "score": evaluation["score"],
            "status": "done",
            "raw_response": {
                **(persist_payload.get("raw_response") or {}),
                "evaluation": evaluation,
            },
        }
    )
    emitter = get_current_emitter()
    if emitter is not None:
        await emitter.emit("generation_done", persist_payload)

    update_current_span(
        input={
            "image_url": gen_result.get("image_url"),
            "design_state": design_state,
            "reference_image_count": len(reference_images),
        },
        output={
            "evaluation": evaluation,
            "best_score": best.get("score") if best else None,
        },
    )
    return {
        "last_evaluation": evaluation,
        "best_generation_result": best,
        "phase": "done",
    }


@observe(name="node:refine_prompt")
async def refine_prompt_node(state: AgentState) -> dict:
    """Refine the prompt based on evaluation feedback."""
    enhanced_prompt: EnhancedPrompt | None = state.get("_enhanced_prompt")
    evaluation: EvaluationResult | None = state.get("last_evaluation")

    if enhanced_prompt is None or evaluation is None:
        update_current_span(output={"skipped": True, "reason": "missing prompt or evaluation"})
        return {}

    update_current_span(
        input={
            "original_prompt": enhanced_prompt.model_dump(),
            "evaluation": evaluation,
            "retry_count": state.get("retry_count", 0),
        }
    )
    refined = await refine_prompt(
        original_prompt=enhanced_prompt,
        evaluation=evaluation,
    )
    workspace = _build_prompt_draft(
        design_state=dict(state.get("design_state") or {}),
        reference_images=list(state.get("reference_images") or []),
        similar_cases=list(state.get("similar_cases") or []),
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        user_prompt_hint=str((state.get("workspace") or {}).get("llm_description", "") or ""),
        llm_reply_hint=refined.prompt,
        negative_prompt=refined.negative_prompt,
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
    )
    emitter = get_current_emitter()
    if emitter is not None:
        workspace["llm_description"] = refined.prompt
        workspace["negative_prompt"] = refined.negative_prompt
        await emitter.emit("prompt_update", {
            **workspace,
            "source": "refine_prompt",
        })

    update_current_span(output=refined.model_dump())
    return {
        "_enhanced_prompt": refined,
        "retry_count": state.get("retry_count", 0) + 1,
        "workspace": workspace,
    }


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
    )
