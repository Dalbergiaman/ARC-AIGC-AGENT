import asyncio
import time

from celery_app import celery_app
from core.image.base import GenerationRequest
from core.image.generator import ImageGenerator
from agent.tools.image_analysis import _to_data_url
from services.storage_service import download_and_save_generated_image


async def _async_generate(request_dict: dict) -> dict:
    # Convert any localhost image URLs to base64 data URLs so cloud providers
    # (GrsAI, Bailian, Volcengine) can access them. The worker runs locally and
    # can read the upload directory directly.
    if request_dict.get("control_image_url"):
        request_dict = dict(request_dict)
        request_dict["control_image_url"] = _to_data_url(request_dict["control_image_url"])
    if request_dict.get("ref_image_url"):
        request_dict = dict(request_dict)
        request_dict["ref_image_url"] = _to_data_url(request_dict["ref_image_url"])
    if request_dict.get("input_image_urls"):
        request_dict = dict(request_dict)
        request_dict["input_image_urls"] = [
            _to_data_url(u) for u in request_dict["input_image_urls"]
        ]

    request = GenerationRequest(**request_dict)
    generator = ImageGenerator()
    result = await generator.generate(request)

    local_url = await download_and_save_generated_image(result.image_url)

    return {
        "image_url": local_url,
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
