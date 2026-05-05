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


class SSEEmitter(Protocol):
    async def emit(self, event_type: str, data: dict) -> None:
        ...


class NullEmitter:
    """No-op emitter used until C-6 wires the real SSE connection."""
    async def emit(self, event_type: str, data: dict) -> None:
        pass


_POLL_INTERVAL = 2      # seconds between Redis result checks
_TIMEOUT_SECONDS = 120  # max wait before treating as timeout


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

    # Build request dict for the Celery task
    ref_url: str | None = None
    ref_images = state.get("reference_images") or []
    if ref_images:
        ref_url = ref_images[-1].get("image_url")

    request_dict = {
        "prompt": enhanced_prompt.prompt,
        "negative_prompt": enhanced_prompt.negative_prompt,
        "ref_image_url": ref_url,
    }

    # Submit task
    from tasks.image_task import generate_image_task
    task = generate_image_task.delay(request_dict)

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
                raise asyncio.CancelledError(f"interrupted by user (run_id={run_id})")

        result = AsyncResult(task.id, app=celery_app)
        if result.ready():
            if result.successful():
                data = result.get()
                gen_result: GenerationResult = {
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
                return gen_result
            else:
                raise RuntimeError(f"generation task failed: {result.result}")

    # Timeout
    task.revoke(terminate=True)
    raise TimeoutError(f"generation timed out after {_TIMEOUT_SECONDS}s")
