"""LangGraph Agent graph definition."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.prompts import agent_system
from agent.state import AgentState, EvaluationResult, PromptDraft, default_agent_state
from agent.state_utils import (
    reset_generation_run,
    update_completeness,
)
from agent.tools.image_analysis import _to_data_url, analyze_reference_image
from agent.tools.image_evaluator import evaluate_generated_image
from agent.tools.image_generator import NullEmitter, generate_image
from api.routes.library import RAG_PICK_KEY, RAG_PICK_SKIP_VALUE
from config import settings
from core.llm.streaming import get_current_emitter
from agent.tools.prompt_builder import (
    EnhancedPrompt,
    build_rag_search_query,
    enhance_prompt,
    fallback_rag_search_query,
    refine_prompt,
    resolve_prompt_language,
)
from core.llm.client import LLMClient
from core.observability import message_preview, observe, update_current_span
from services import dashboard_service, library_service

_llm = LLMClient()

# ---------------------------------------------------------------------------
# MCP client accessor — injected from main.py lifespan
# ---------------------------------------------------------------------------

_MCP_CLIENT: MultiServerMCPClient | None = None


def set_mcp_client(client: MultiServerMCPClient | None) -> None:
    """Register the lifespan-owned MCP client so graph nodes can reach it."""
    global _MCP_CLIENT
    _MCP_CLIENT = client


def get_mcp_client() -> MultiServerMCPClient | None:
    return _MCP_CLIENT


# Regex to find image URLs in message content
_IMAGE_URL_RE = re.compile(r'https?://\S+\.(?:jpg|jpeg|png|webp)', re.IGNORECASE)

_GENERATION_NEGATIVE_RE = re.compile(
    r"(不要|别|先不|暂不|不用|无需|先别)\s*(生成|出图|渲染)|"
    r"(do\s+not|don't|dont|no)\s+(generate|render|create\s+(an?\s+)?image|generation)",
    re.IGNORECASE,
)
_IMAGE_SEND_CONTEXT_RE = re.compile(
    r"(我发送了一张|发送.*(参考图|结构底图|底图|图片)|上传.*(参考图|结构底图|底图|图片)|"
    r"(参考图|结构底图|底图).*分析|请分析这张)",
    re.IGNORECASE,
)
_GENERATION_INTENT_RE = re.compile(
    r"(生成图片|生成图像|开始生成|开始出图|开始渲染|帮我出一张|帮我生成一张|出图|渲染|生成)|"
    r"\b(generate|render)\b|"
    r"\b(create|make)\s+(an?\s+)?(image|rendering|render)\b|"
    r"\bstart\s+(generation|rendering)\b",
    re.IGNORECASE,
)


def _prompt_keywords(design_state: dict) -> dict[str, str]:
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
    return keywords


def _compose_llm_description(
    design_state: dict,
    reference_images: list[dict],
    llm_reply_hint: str = "",
) -> str:
    def normalize_text(value: str) -> str:
        return re.sub(r"[\s，。,.；;：:（）()、]+", "", value)

    def is_covered(value: str, text: str) -> bool:
        normalized_value = normalize_text(value)
        normalized_text = normalize_text(text)
        return bool(normalized_value) and normalized_value in normalized_text

    def has_shared_phrase(value: str, text: str, window: int = 4) -> bool:
        normalized_value = normalize_text(value)
        normalized_text = normalize_text(text)
        if len(normalized_value) < window:
            return False
        return any(
            normalized_value[index:index + window] in normalized_text
            for index in range(0, len(normalized_value) - window + 1)
        )

    def important_terms(value: str) -> list[str]:
        terms = re.split(r"[，,；;、\s（）()]+", value)
        return [term for term in terms if len(normalize_text(term)) >= 3]

    def is_mostly_covered(value: str, text: str) -> bool:
        if is_covered(value, text):
            return True
        terms = important_terms(value)
        if not terms:
            return False
        covered_count = sum(1 for term in terms if is_covered(term, text) or has_shared_phrase(term, text))
        return covered_count / len(terms) >= 0.5

    parts: list[str] = []
    hint = llm_reply_hint.strip()
    building_type = design_state.get("building_type", "")
    style = design_state.get("style", "")
    facade_material = design_state.get("facade_material", "")
    lighting = design_state.get("lighting", "")
    viewpoint = design_state.get("viewpoint", "")
    surroundings = design_state.get("surroundings", "")
    color_palette = design_state.get("color_palette", "")
    special_requirements = design_state.get("special_requirements", "")

    if hint:
        parts.append(hint)
    if (building_type or style) and not all(is_mostly_covered(str(v), hint) for v in (building_type, style) if v):
        parts.append(f"{style}{building_type}建筑效果图。".strip())
    if facade_material and not is_mostly_covered(str(facade_material), hint):
        material_text = f"外立面采用{facade_material}"
        if color_palette and not is_mostly_covered(str(color_palette), hint):
            material_text += f"，色彩以{color_palette}为主"
        parts.append(material_text + "。")
    elif color_palette and not is_mostly_covered(str(color_palette), hint):
        parts.append(f"整体色彩以{color_palette}为主。")
    if lighting and not is_mostly_covered(str(lighting), hint):
        parts.append(f"光线为{lighting}。")
    if viewpoint and not is_mostly_covered(str(viewpoint), hint):
        parts.append(f"观看视角为{viewpoint}。")
    if surroundings and not is_mostly_covered(str(surroundings), hint):
        parts.append(f"周边环境为{surroundings}。")
    if special_requirements and not is_mostly_covered(str(special_requirements), hint):
        parts.append(f"特别要求：{special_requirements}。")

    seen: set[str] = set()
    deduped: list[str] = []
    for part in parts:
        normalized = " ".join(part.split())
        comparable = normalized.rstrip("。.!！")
        if not comparable:
            continue
        if comparable in seen or any(comparable in existing or existing in comparable for existing in seen):
            continue
        deduped.append(normalized)
        seen.add(comparable)
    return " ".join(deduped)


def _build_prompt_draft(
    design_state: dict,
    reference_images: list[dict],
    control_image: dict | None = None,
    custom_description: str = "",
    llm_reply_hint: str = "",
    negative_prompt: str = "",
    prompt_template: dict | None = None,
) -> PromptDraft:
    return {
        "keywords": _prompt_keywords(design_state),
        "llm_description": _compose_llm_description(
            design_state=design_state,
            reference_images=reference_images,
            llm_reply_hint=" ".join(filter(None, [
                "以图生图底图作为建筑要素参考，并按照用户要求进行修改。" if control_image else "",
                llm_reply_hint,
            ])),
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


def _vision_urls_for_agent(state: AgentState) -> list[str]:
    """Return images explicitly sent in the current turn for the main VLM reply."""
    urls = [str(url) for url in (state.get("_current_vision_images") or []) if url]

    seen: set[str] = set()
    return [_to_data_url(url) for url in urls if not (url in seen or seen.add(url))]


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
    if _IMAGE_SEND_CONTEXT_RE.search(text):
        return False
    return _GENERATION_INTENT_RE.search(text) is not None


def resolve_generation_gate(llm_phase: str, explicit_generation_intent: bool) -> tuple[bool, str]:
    """Resolve final generation control state from deterministic user intent."""
    if explicit_generation_intent:
        return True, "generating"
    if llm_phase == "generating":
        return False, "collecting"
    return False, llm_phase


def _coerce_enhanced_prompt(value: object) -> EnhancedPrompt | None:
    if isinstance(value, EnhancedPrompt):
        return value
    if isinstance(value, dict):
        try:
            return EnhancedPrompt(**value)
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@observe(name="node:agent", as_type="agent")
async def agent_node(state: AgentState) -> dict:
    """Main decision node: understands intent, updates DesignState, decides next step.

    Tool calls are rule-based (deterministic), not LLM-driven:
    - Image URL in latest message → analyze_reference_image
    - RAG gate is handled by rag_gate_node, not here
    """
    design_state = dict(state.get("design_state") or {})
    reference_images = list(state.get("reference_images") or [])
    control_image = state.get("control_image")
    vision_image_urls = _vision_urls_for_agent(state)
    messages = list(state.get("messages") or [])
    explicit_generation_intent = has_explicit_generation_intent(messages)
    workspace = dict(state.get("workspace") or {})
    custom_description = str(workspace.get("custom_description", "") or "")
    prompt_template = workspace.get("prompt_template") if isinstance(workspace.get("prompt_template"), dict) else None
    updates: dict = {}
    update_current_span(
        input={
            "latest_message": message_preview(messages[-1].content) if messages else "",
            "design_state": design_state,
            "reference_image_count": len(reference_images),
            "vision_image_count": len(vision_image_urls),
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

    # --- Call LLM for intent understanding and DesignState update ---
    llm_messages = [
        SystemMessage(content=agent_system(
            design_state=design_state,
            reference_analysis=reference_images,
            prompt_template=prompt_template,
        )),
        *messages,
    ]

    emitter = get_current_emitter()
    raw_parts: list[str] = []

    try:
        stream = await _llm.astream(llm_messages, images=vision_image_urls or None)
        async for chunk in stream:
            if not chunk:
                continue
            raw_parts.append(chunk)
            if emitter is not None:
                await emitter.emit("text_delta", {"content": chunk})
        raw = "".join(raw_parts)
    except Exception:
        raw = await _llm.ainvoke(llm_messages, images=vision_image_urls or None)
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
        control_image=control_image if isinstance(control_image, dict) else None,
        custom_description=custom_description,
        llm_reply_hint=llm_description,
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
            "vision_image_count": len(vision_image_urls),
        }
    )
    return result


@observe(name="node:rag_gate")
async def rag_gate_node(state: AgentState) -> dict:
    """Search MCP library, then optionally block for user candidate pick.

    When RAG_BLOCKING_ENABLED is False (default during development):
      - Runs the search and stashes candidates in state; no SSE, no blocking.

    When RAG_BLOCKING_ENABLED is True:
      - Emits a ``rag_candidates`` SSE event so the frontend can show the popup.
      - Polls Redis for ``rag_pick:{session_id}:{run_id}`` (1 s interval, up to
        RAG_BLOCKING_TIMEOUT seconds).
      - Exits on: pick (writes ``_picked_image_id``), skip sentinel, timeout
        (treated as skip), or cancel flag (raises CancelledError).
    """
    design_state = dict(state.get("design_state") or {})

    client = get_mcp_client()
    if client is None:
        update_current_span(
            input={"design_state": design_state},
            output={"searched": False, "reason": "mcp_client not registered"},
            level="WARNING",
            status_message="MCP client missing; skipping RAG search",
        )
        return {}

    enhanced_prompt = _coerce_enhanced_prompt(state.get("_enhanced_prompt"))
    if enhanced_prompt is not None:
        query = await build_rag_search_query(
            enhanced_prompt=enhanced_prompt,
            design_state=design_state,
        )
    else:
        query = fallback_rag_search_query(design_state)
    if not query:
        query = fallback_rag_search_query(design_state)
    if not query:
        update_current_span(
            input={"design_state": design_state},
            output={"searched": False, "reason": "rag query empty"},
        )
        return {}
    try:
        results = await library_service.search_by_text(
            client,
            query=query,
            top_k=5,
            filters=None,
        )
    except Exception as exc:
        update_current_span(
            input={"query": query, "filters": None},
            output={"searched": False, "error": str(exc)},
            level="WARNING",
            status_message=f"RAG search failed: {exc}",
        )
        return {}

    candidates = list(results or [])
    update_current_span(
        input={"query": query, "filters": None},
        output={
            "searched": True,
            "candidate_count": len(candidates),
            "blocking_enabled": settings.RAG_BLOCKING_ENABLED,
        },
    )

    if not candidates or not settings.RAG_BLOCKING_ENABLED:
        return {"pending_rag_candidates": candidates}

    # --- Blocking path (RAG_BLOCKING_ENABLED=True) ---
    session_id = str(state.get("turn_id") or "")
    run_id = str(state.get("run_id") or "")

    emitter = get_current_emitter()
    if emitter is not None:
        await emitter.emit("rag_candidates", {
            "candidates": candidates,
            "timeout": settings.RAG_BLOCKING_TIMEOUT,
        })

    picked_image_id = await _poll_for_rag_pick(
        session_id=session_id,
        run_id=run_id,
        timeout=settings.RAG_BLOCKING_TIMEOUT,
    )

    out: dict = {"pending_rag_candidates": candidates}
    if picked_image_id:
        rag_image = await _materialise_rag_image(client, picked_image_id)
        if rag_image is not None:
            out["rag_image"] = rag_image
            if emitter is not None:
                await emitter.emit("rag_image_update", rag_image)
            update_current_span(output={
                "picked_image_id": picked_image_id,
                "rag_image_file_id": rag_image.get("file_id"),
                "ambience_note_preview": (rag_image.get("ambience_note", "") or "")[:80],
            })
        else:
            update_current_span(
                level="WARNING",
                status_message=f"failed to materialise rag_image for {picked_image_id}",
            )
    return out


async def _materialise_rag_image(
    client: MultiServerMCPClient,
    image_id: str,
) -> dict | None:
    """Download the picked library image into backend/uploads and run VLM ambience.

    Returns a RagImage dict, or None if the library record is missing or any
    step fails (the run continues without a rag_image).
    """
    from agent.prompts import ambience_rag_image_system
    from services.storage_service import download_and_save_library_image

    try:
        record = await library_service.get_image_by_id(client, image_id=image_id)
    except Exception:
        return None
    if not record:
        return None

    source_url = record.get("image_url") or ""
    if not source_url:
        return None

    try:
        file_id, url = await download_and_save_library_image(source_url)
    except Exception:
        return None

    # Build an absolute URL for the VLM call (the saved file is /static/uploads/<id>.<ext>).
    # We pass the relative path; image_analysis converts it to a data URL internally.
    from agent.tools.image_analysis import _to_data_url
    try:
        data_url = _to_data_url(url)
    except Exception:
        data_url = url

    try:
        ambience_note = await _llm.ainvoke(
            messages=[SystemMessage(content=ambience_rag_image_system()),
                      HumanMessage(content="请描述这张图的氛围。")],
            images=[data_url],
            enable_thinking=False,
        )
    except Exception:
        ambience_note = ""

    return {
        "file_id": file_id,
        "image_url": url,
        "source_image_id": image_id,
        "ambience_note": (ambience_note or "").strip(),
        "sent": False,
    }


async def _poll_for_rag_pick(
    session_id: str,
    run_id: str,
    timeout: int,
) -> str | None:
    """Poll Redis until the user picks a candidate, skips, cancels, or times out.

    Returns the picked image_id string, or None for skip/timeout/cancel.
    Raises asyncio.CancelledError if the run was cancelled by a new message.
    """
    from redis.asyncio import Redis

    pick_key = RAG_PICK_KEY.format(session_id=session_id, run_id=run_id)
    cancel_key = f"cancel:{session_id}:{run_id}"
    max_polls = timeout  # 1 s per poll

    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        for _ in range(max_polls):
            await asyncio.sleep(1)

            # Check cancel flag first (new message from user)
            if run_id and session_id:
                if await redis.exists(cancel_key):
                    raise asyncio.CancelledError(
                        f"rag_gate interrupted by new message (run_id={run_id})"
                    )

            # Check pick key
            value = await redis.get(pick_key)
            if value is not None:
                await redis.delete(pick_key)
                if value == RAG_PICK_SKIP_VALUE:
                    return None  # user clicked skip
                return value  # image_id string
    finally:
        await redis.aclose()

    return None  # timeout — treat as skip


@observe(name="node:enhance_prompt")
async def enhance_prompt_node(state: AgentState) -> dict:
    """Build the image generation prompt from DesignState and reference images."""
    design_state = dict(state.get("design_state") or {})
    reference_images = list(state.get("reference_images") or [])
    control_image = state.get("control_image")
    annotated_image = state.get("annotated_image")
    latest_user_request = _latest_human_text(list(state.get("messages") or [])).strip()
    image_model = str(dashboard_service.get_config().get("image_provider", {}).get("model", "") or "")
    prompt_language = resolve_prompt_language(image_model)

    enhanced = await enhance_prompt(
        design_state=design_state,
        reference_analysis=reference_images,
        llm_description=str((state.get("workspace") or {}).get("llm_description", "") or ""),
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
        latest_user_request=latest_user_request,
        control_image=control_image if isinstance(control_image, dict) else None,
        annotated_image=annotated_image if isinstance(annotated_image, dict) else None,
        prompt_language=prompt_language,
    )
    workspace = _build_prompt_draft(
        design_state=design_state,
        reference_images=reference_images,
        control_image=control_image if isinstance(control_image, dict) else None,
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        negative_prompt=enhanced.negative_prompt,
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
    )
    emitter = get_current_emitter()
    if emitter is not None:
        workspace["negative_prompt"] = enhanced.negative_prompt
        await emitter.emit("prompt_update", {
            **workspace,
            "source": "enhance_prompt",
        })

    update_current_span(
        input={
            "design_state": design_state,
            "reference_image_count": len(reference_images),
            "has_latest_user_request": bool(latest_user_request),
            "has_control_image": isinstance(control_image, dict),
            "has_annotated_image": isinstance(annotated_image, dict),
            "prompt_language": prompt_language,
            "image_model": image_model,
        },
        output=enhanced.model_dump(),
    )
    return {
        "phase": "generating",
        "_enhanced_prompt": enhanced.model_dump(),  # checkpoint-safe dict
        "workspace": workspace,
    }


@observe(name="node:generate_image")
async def generate_image_node(state: AgentState) -> dict:
    """Submit Celery task and poll for result."""
    enhanced_prompt = _coerce_enhanced_prompt(state.get("_enhanced_prompt"))
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
        await emitter.emit("generation_error", {
            "task_id": state.get("current_task_id", ""),
            "reason": "timeout",
        })
        return {
            "retry_count": retry_count + 1,
            "phase": "evaluating",
        }
    except asyncio.CancelledError:
        update_current_span(level="WARNING", status_message="generation interrupted")
        return {"phase": "interrupted"}
    except RuntimeError as exc:
        update_current_span(level="ERROR", status_message=str(exc))
        return {
            "retry_count": retry_count + 1,
            "phase": "evaluating",
        }

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
    enhanced_prompt = _coerce_enhanced_prompt(state.get("_enhanced_prompt"))
    evaluation: EvaluationResult | None = state.get("last_evaluation")
    gen_result = state.get("_current_gen_result") or {}
    previous_generation_url = gen_result.get("image_url") if isinstance(gen_result, dict) else None
    image_model = str(dashboard_service.get_config().get("image_provider", {}).get("model", "") or "")
    prompt_language = resolve_prompt_language(image_model)

    if enhanced_prompt is None or evaluation is None:
        update_current_span(output={"skipped": True, "reason": "missing prompt or evaluation"})
        return {}

    update_current_span(
        input={
            "original_prompt": enhanced_prompt.model_dump(),
            "evaluation": evaluation,
            "previous_generation_url": previous_generation_url,
            "prompt_language": prompt_language,
            "image_model": image_model,
            "retry_count": state.get("retry_count", 0),
        }
    )
    refined = await refine_prompt(
        original_prompt=enhanced_prompt,
        evaluation=evaluation,
        previous_generation_url=previous_generation_url,
        prompt_language=prompt_language,
    )
    workspace = _build_prompt_draft(
        design_state=dict(state.get("design_state") or {}),
        reference_images=list(state.get("reference_images") or []),
        control_image=state.get("control_image") if isinstance(state.get("control_image"), dict) else None,
        custom_description=str((state.get("workspace") or {}).get("custom_description", "") or ""),
        negative_prompt=refined.negative_prompt,
        prompt_template=(state.get("workspace") or {}).get("prompt_template"),
    )
    emitter = get_current_emitter()
    if emitter is not None:
        workspace["negative_prompt"] = refined.negative_prompt
        await emitter.emit("prompt_update", {
            **workspace,
            "source": "refine_prompt",
        })

    update_current_span(output=refined.model_dump())
    return {
        "_enhanced_prompt": refined.model_dump(),
        "retry_count": state.get("retry_count", 0) + 1,
        "workspace": workspace,
    }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_agent(state: AgentState) -> Literal["enhance_prompt", END]:  # type: ignore[valid-type]
    if state.get("ready_to_generate"):
        return "enhance_prompt"
    return END


def route_after_evaluate(state: AgentState) -> Literal["refine_prompt", END]:  # type: ignore[valid-type]
    eval_result = state.get("last_evaluation")
    retry_count = state.get("retry_count", 0)

    if eval_result is None or retry_count >= 3:
        return END
    has_fatal_issue = bool(eval_result.get("fatal_issues"))
    if (has_fatal_issue or eval_result["score"] < 0.72) and retry_count < 3:
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

    g.add_edge("enhance_prompt", "rag_gate")
    g.add_edge("rag_gate", "generate_image")
    g.add_edge("generate_image", "evaluate_image")
    g.add_conditional_edges("evaluate_image", route_after_evaluate)

    g.add_edge("refine_prompt", "generate_image")

    return g


def compile_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    return build_graph().compile(
        checkpointer=checkpointer,
    )
