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
    # control_image, annotated_image, rag_image, and failed_image are explicit
    # img2img anchors sent to providers. Image numbers are assigned after empty
    # slots are filtered so prompt labels always match provider input order.
    control_image = state.get("control_image") or {}
    annotated_image = state.get("annotated_image") or {}
    rag_image = state.get("rag_image") or {}
    current_gen_result = state.get("_current_gen_result") or {}
    control_url: str | None = control_image.get("image_url") if isinstance(control_image, dict) else None
    annotated_url: str | None = annotated_image.get("image_url") if isinstance(annotated_image, dict) else None
    rag_url: str | None = rag_image.get("image_url") if isinstance(rag_image, dict) else None
    failed_url: str | None = (
        current_gen_result.get("image_url") if isinstance(current_gen_result, dict) else None
    )

    # Build prompt header explaining each image slot by its actual position
    prompt = enhanced_prompt.prompt
    input_image_urls: list[str] = []
    slot_labels: list[str] = []
    if control_url:
        input_image_urls.append(control_url)
        control_note = str(control_image.get("note", "") or "").strip()
        line = (
            f"图{len(input_image_urls)}为图生图底图，是本次编辑的主约束图；"
            "保留建筑体量、透视、空间关系、立面分区、开窗节奏和可见主要材质，"
            "只按用户最新要求修改指定部分，不要只做轻微风格变化。"
        )
        if control_note:
            line += f"底图说明：{control_note}"
        slot_labels.append(
            line
        )
    if annotated_url:
        input_image_urls.append(annotated_url)
        annotated_note = str(annotated_image.get("note", "") or "").strip()
        line = (
            f"图{len(input_image_urls)}为带批注效果图，是上一版结果的修改指令图；"
            "按批注说明执行明确编辑，允许重绘相关区域以满足指令，不要仅做小修小改。"
        )
        if annotated_note:
            line += f"批注说明：{annotated_note}"
        slot_labels.append(line)
    if rag_url:
        input_image_urls.append(rag_url)
        ambience_note = str(rag_image.get("ambience_note", "") or "").strip()
        line = f"图{len(input_image_urls)}为氛围参考"
        if ambience_note:
            line += f"：{ambience_note}"
        else:
            line += "。"
        slot_labels.append(line)
    if failed_url:
        input_image_urls.append(failed_url)
        slot_labels.append(
            f"图{len(input_image_urls)}为上一轮低分生成结果，仅用于识别需要修正的问题；"
            "不要复制其中错误内容。优先以图生图底图中的建筑要素和用户最新要求为准。"
        )
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
            "failed_image_url": failed_url,
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
                await emitter.emit("generation_error", {
                    "task_id": task.id,
                    "run_id": run_id,
                    "reason": "task_failed",
                })
                raise RuntimeError(f"generation task failed: {result.result}")

    # Timeout
    task.revoke(terminate=True)
    update_current_span(
        level="WARNING",
        status_message=f"generation timed out after {_TIMEOUT_SECONDS}s",
        metadata={"task_id": task.id},
    )
    await emitter.emit("generation_error", {
        "task_id": task.id,
        "run_id": run_id,
        "reason": "timeout",
    })
    raise TimeoutError(f"generation timed out after {_TIMEOUT_SECONDS}s")
