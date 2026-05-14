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
from core.image.dimensions import canvas_from_image_url
from core.observability import observe, update_current_span


class SSEEmitter(Protocol):
    async def emit(self, event_type: str, data: dict) -> None:
        ...


class NullEmitter:
    """No-op emitter used until C-6 wires the real SSE connection."""
    async def emit(self, event_type: str, data: dict) -> None:
        pass


_POLL_INTERVAL = 2      # seconds between Redis result checks
_TIMEOUT_SECONDS = 240  # max wait before treating as timeout
_MAX_REFERENCE_INPUT_IMAGES = 3
_IMAGE_QUALITY_SUFFIX = (
    "图片质量要求：真实顶级照片级建筑可视化、渲染效果，建筑比例稳定，透视准确，结构清晰，"
    "边缘细节自然，画面完成度高，避免模型图感、塑料感、廉价渲染感和学生作业感。"
)


def _append_quality_suffix(prompt: str) -> str:
    prompt = prompt.strip()
    if _IMAGE_QUALITY_SUFFIX in prompt:
        return prompt
    return f"{prompt}\n{_IMAGE_QUALITY_SUFFIX}" if prompt else _IMAGE_QUALITY_SUFFIX


def _reference_usage_rule(image: dict) -> str:
    intent = str(image.get("reference_intent") or image.get("intent") or "").strip()
    note = str(image.get("intent_note") or image.get("note") or "").strip()
    rules = {
        "composition": "只参考构图、视角和画面关系，不覆盖结构底图的建筑体量、透视和空间关系。",
        "color": "只参考色彩关系、饱和度、冷暖倾向和明暗对比，不复制建筑形体。",
        "style": "只参考建筑表达语言、立面气质和细部密度，不复制具体建筑体量。",
        "material": "只参考材质肌理、玻璃反射、金属/石材/木材等质感，不参考构图和体量。",
        "lighting": "只参考光线时段、方向、色温、阴影和氛围，不改变主体结构。",
        "surroundings": "只参考环境关系、植被、水面、街景或场地氛围，不改变主体建筑形体。",
        "other": "只按用户说明限定的方向参考，不覆盖结构底图和最新文字要求。",
    }
    rule = rules.get(intent) or "作为全图视觉参考，但不得覆盖结构底图的体量、透视和空间关系。"
    if note:
        rule += f"用户说明：{note}"
    return rule


def _reference_input_images(state: AgentState) -> list[dict]:
    images: list[dict] = []
    seen: set[str] = set()
    for image in state.get("reference_images") or []:
        if not isinstance(image, dict):
            continue
        url = str(image.get("image_url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        images.append(image)
        if len(images) >= _MAX_REFERENCE_INPUT_IMAGES:
            break
    return images


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

    # Build request dict for the Celery task. control_image is the strongest
    # structure anchor; reference_images are visual evidence constrained by
    # their user intent. Image numbers are assigned after empty slots are
    # filtered so prompt labels always match provider input order.
    control_image = state.get("control_image") or {}
    annotated_image = state.get("annotated_image") or {}
    rag_image = state.get("rag_image") or {}
    reference_images = _reference_input_images(state)
    control_url: str | None = control_image.get("image_url") if isinstance(control_image, dict) else None
    annotated_url: str | None = annotated_image.get("image_url") if isinstance(annotated_image, dict) else None
    rag_url: str | None = rag_image.get("image_url") if isinstance(rag_image, dict) else None

    # Build prompt header explaining each image slot by its actual position
    prompt = _append_quality_suffix(enhanced_prompt.prompt)
    input_image_urls: list[str] = []
    slot_labels: list[str] = []
    fallback_input_image_urls: list[str] = []
    fallback_slot_labels: list[str] = []
    if control_url:
        input_image_urls.append(control_url)
        fallback_input_image_urls.append(control_url)
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
        fallback_slot_labels.append(line)
    if annotated_url:
        input_image_urls.append(annotated_url)
        fallback_input_image_urls.append(annotated_url)
        annotated_note = str(annotated_image.get("note", "") or "").strip()
        line = (
            f"图{len(input_image_urls)}为带批注效果图，是上一版结果的修改指令图；"
            "按批注说明执行明确编辑，允许重绘相关区域以满足指令，不要仅做小修小改。"
        )
        if annotated_note:
            line += f"批注说明：{annotated_note}"
        slot_labels.append(line)
        fallback_slot_labels.append(line)
    for reference_image in reference_images:
        reference_url = str(reference_image.get("image_url") or "").strip()
        if not reference_url:
            continue
        input_image_urls.append(reference_url)
        slot_labels.append(
            f"图{len(input_image_urls)}为参考图：{_reference_usage_rule(reference_image)}"
        )
    if rag_url:
        input_image_urls.append(rag_url)
        ambience_note = str(rag_image.get("ambience_note", "") or "").strip()
        line = f"图{len(input_image_urls)}为氛围参考"
        if ambience_note:
            line += f"：{ambience_note}"
        else:
            line += "。"
        slot_labels.append(line)
    if slot_labels:
        prompt = "\n".join([*slot_labels, prompt])

    canvas_source_url = control_url or annotated_url
    canvas = canvas_from_image_url(canvas_source_url)
    request_dict = {
        "prompt": prompt,
        "negative_prompt": enhanced_prompt.negative_prompt,
        "control_image_url": control_url,
        "input_image_urls": input_image_urls,
        "width": canvas.width,
        "height": canvas.height,
        "aspectRatio": canvas.aspect_ratio,
        # Backward compatibility for providers or tasks still reading the old field.
        "ref_image_url": control_url,
    }
    fallback_prompt = _append_quality_suffix(enhanced_prompt.prompt)
    if fallback_slot_labels:
        fallback_prompt = "\n".join([*fallback_slot_labels, fallback_prompt])
    fallback_request_dict = {
        **request_dict,
        "prompt": fallback_prompt,
        "input_image_urls": fallback_input_image_urls,
    }
    update_current_span(
        input={
            "prompt": prompt,
            "negative_prompt": enhanced_prompt.negative_prompt,
            "control_image_url": control_url,
            "annotated_image_url": annotated_url,
            "reference_image_urls": [image.get("image_url") for image in reference_images],
            "rag_image_url": rag_url,
            "input_image_count": len(input_image_urls),
            "semantic_reference_image_count": len(state.get("reference_images") or []),
            "canvas": {
                "width": canvas.width,
                "height": canvas.height,
                "aspect_ratio": canvas.aspect_ratio,
                "source_width": canvas.source_width,
                "source_height": canvas.source_height,
                "source_url": canvas.source_url,
                "used_default": canvas.used_default,
            },
            "session_id": session_id,
            "run_id": run_id,
        }
    )

    # Submit task
    from tasks.image_task import generate_image_task
    task = generate_image_task.delay(request_dict)
    fallback_attempted = False
    can_fallback = bool(reference_images) and request_dict["input_image_urls"] != fallback_input_image_urls
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
                if can_fallback and not fallback_attempted:
                    fallback_attempted = True
                    update_current_span(
                        level="WARNING",
                        status_message=f"generation task failed with reference image inputs; retrying without weak visual references: {result.result}",
                        metadata={"failed_task_id": task.id},
                    )
                    task = generate_image_task.delay(fallback_request_dict)
                    update_current_span(metadata={"fallback_task_id": task.id})
                    await emitter.emit("generation_start", {
                        "task_id": task.id,
                        "run_id": run_id,
                        "fallback": True,
                    })
                    continue
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
