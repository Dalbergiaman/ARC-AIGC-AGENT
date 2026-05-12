"""Image generation tool for the deterministic generation sub-flow.

Not a @tool — called directly by generate_image_node.
SSEEmitter protocol allows testing without a real SSE connection (C-6 wires the real one).
"""
from __future__ import annotations

import asyncio
import time
from typing import Protocol

from celery.result import AsyncResult

from agent.state import AgentState, GenerationResult
from agent.tools.prompt_builder import EnhancedPrompt
from celery_app import celery_app
from core.observability import observe, update_current_span


class SSEEmitter(Protocol):
    async def emit(self, event_type: str, data: dict) -> None:
        ...


class NullEmitter:
    """No-op emitter used until C-6 wires the real SSE connection."""
    async def emit(self, event_type: str, data: dict) -> None:
        pass


_POLL_INTERVAL = 2      # seconds between Redis result checks
_TIMEOUT_SECONDS = 120  # max wait before treating as timeout


@observe(name="tool:generate_image", as_type="tool")
async def generate_image(
    state: AgentState,
    enhanced_prompt: EnhancedPrompt,
    emitter: SSEEmitter | None = None,
) -> GenerationResult:
    """Submit a Celery image generation task and poll until done or cancelled.

    Raises:
        asyncio.CancelledError: if Redis cancel flag is set by the user.
        TimeoutError: if the task exceeds TIMEOUT_SECONDS.
    """
    if emitter is None:
        emitter = NullEmitter()

    session_id = state.get("turn_id", "")
    run_id = state.get("run_id", "")

    # Build request dict for the Celery task. reference_images are semantic-only;
    # control_image, annotated_image, and rag_image are explicit img2img anchors sent to providers.
    control_image = state.get("control_image") or {}
    annotated_image = state.get("annotated_image") or {}
    rag_image = state.get("rag_image") or {}
    control_url: str | None = control_image.get("image_url") if isinstance(control_image, dict) else None
    annotated_url: str | None = annotated_image.get("image_url") if isinstance(annotated_image, dict) else None
    rag_url: str | None = rag_image.get("image_url") if isinstance(rag_image, dict) else None
    input_image_urls = [url for url in [control_url, annotated_url, rag_url] if url]

    # Build prompt header explaining each image slot by its actual position
    prompt = enhanced_prompt.prompt
    slot_labels: list[str] = []
    slot_index = 0
    if control_url:
        slot_index += 1
        slot_labels.append(
            f"图{slot_index}为结构底图，保持建筑体量、透视、尺度和主要空间关系。"
        )
    if annotated_url:
        slot_index += 1
        annotated_note = str(annotated_image.get("note", "") or "").strip()
        line = f"图{slot_index}为带批注效果图，按批注说明调整。"
        if annotated_note:
            line += f"批注说明：{annotated_note}"
        slot_labels.append(line)
    if rag_url:
        slot_index += 1
        ambience_note = str(rag_image.get("ambience_note", "") or "").strip()
        line = f"图{slot_index}为氛围参考"
        if ambience_note:
            line += f"：{ambience_note}"
        else:
            line += "。"
        slot_labels.append(line)
    if slot_labels:
        prompt = "\n".join([*slot_labels, prompt])

    request_dict = {
        "prompt": prompt,
        "negative_prompt": enhanced_prompt.negative_prompt,
        "control_image_url": control_url,
        "input_image_urls": input_image_urls,
        # Backward compatibility for providers or tasks still reading the old field.
        "ref_image_url": control_url,
    }
    update_current_span(
        input={
            "prompt": prompt,
            "negative_prompt": enhanced_prompt.negative_prompt,
            "control_image_url": control_url,
            "annotated_image_url": annotated_url,
            "rag_image_url": rag_url,
            "input_image_count": len(input_image_urls),
            "semantic_reference_image_count": len(state.get("reference_images") or []),
            "session_id": session_id,
            "run_id": run_id,
        }
    )

    # Submit task
    from tasks.image_task import generate_image_task
    task = generate_image_task.delay(request_dict)
    update_current_span(metadata={"task_id": task.id})

    await emitter.emit("generation_start", {
        "task_id": task.id,
        "run_id": run_id,
    })

    # Poll for result
    cancel_key = f"cancel:{session_id}:{run_id}"
    start_time = time.monotonic()
    max_polls = _TIMEOUT_SECONDS // _POLL_INTERVAL

    for _ in range(max_polls):
        await asyncio.sleep(_POLL_INTERVAL)

        # Check cancel flag
        if run_id and session_id:
            from redis.asyncio import Redis
            from config import settings
            redis = Redis.from_url(settings.REDIS_URL)
            try:
                cancelled = await redis.exists(cancel_key)
            finally:
                await redis.aclose()
            if cancelled:
                task.revoke(terminate=True)
                update_current_span(
                    level="WARNING",
                    status_message=f"interrupted by user (run_id={run_id})",
                    metadata={"task_id": task.id},
                )
                raise asyncio.CancelledError(f"interrupted by user (run_id={run_id})")

        result = AsyncResult(task.id, app=celery_app)
        if result.ready():
            if result.successful():
                data = result.get()
                gen_result: GenerationResult = {
                    "task_id": task.id,
                    "image_url": data["image_url"],
                    "provider": data["provider"],
                    "generation_time": data["generation_time"],
                    "score": 0.0,
                    "raw_response": data.get("raw_response", {}),
                }
                await emitter.emit("generation_done", {
                    "task_id": task.id,
                    "image_url": data["image_url"],
                    "run_id": run_id,
                })
                update_current_span(
                    output={
                        "task_id": task.id,
                        "image_url": data["image_url"],
                        "provider": data["provider"],
                        "generation_time": data["generation_time"],
                    }
                )
                return gen_result
            else:
                update_current_span(
                    level="ERROR",
                    status_message=f"generation task failed: {result.result}",
                    metadata={"task_id": task.id},
                )
                raise RuntimeError(f"generation task failed: {result.result}")

    # Timeout
    task.revoke(terminate=True)
    update_current_span(
        level="WARNING",
        status_message=f"generation timed out after {_TIMEOUT_SECONDS}s",
        metadata={"task_id": task.id},
    )
    raise TimeoutError(f"generation timed out after {_TIMEOUT_SECONDS}s")
