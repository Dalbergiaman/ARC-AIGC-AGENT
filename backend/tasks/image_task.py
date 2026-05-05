import asyncio
import time

from celery_app import celery_app
from core.image.base import GenerationRequest
from core.image.generator import ImageGenerator


async def _async_generate(request_dict: dict) -> dict:
    request = GenerationRequest(**request_dict)
    generator = ImageGenerator()
    result = await generator.generate(request)
    return {
        "image_url": result.image_url,
        "provider": result.provider,
        "generation_time": result.generation_time,
        "raw_response": result.raw_response,
    }


@celery_app.task(name="tasks.generate_image")
def generate_image_task(request_dict: dict) -> dict:
    """Synchronous Celery task wrapping the async image generator.

    Returns a dict matching agent-layer GenerationResult fields.
    Migration to async task (celery-pool-asyncio) only requires changing
    this wrapper — _async_generate stays untouched.
    """
    return asyncio.run(_async_generate(request_dict))
