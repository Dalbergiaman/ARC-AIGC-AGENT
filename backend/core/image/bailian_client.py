import asyncio
import time

import httpx

from core.image.base import GenerationRequest, GenerationResult, ImageGeneratorBase


class BailianClient(ImageGeneratorBase):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._submit_endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
        self._task_endpoint_prefix = "https://dashscope.aliyuncs.com/api/v1/tasks"

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": self._model,
            "input": {
                "messages": [
                    {"role": "user", "content": [
                        {"text": request.prompt},
                    ]},
                ]
            },
            "parameters": {
                "size": f"{request.width}*{request.height}",
                "steps": request.steps,
            },
        }
        if request.seed is not None:
            payload["parameters"]["seed"] = request.seed
        if request.ref_image_url:
            payload["input"]["ref_img"] = request.ref_image_url

        async with httpx.AsyncClient(timeout=120.0) as client:
            submit_resp = await client.post(self._submit_endpoint, headers=headers, json=payload)
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            task_id = submit_data.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"Bailian submit missing task_id: {submit_data}")

            for _ in range(40):
                task_resp = await client.get(f"{self._task_endpoint_prefix}/{task_id}", headers=headers)
                task_resp.raise_for_status()
                task_data = task_resp.json()
                status = task_data.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                    # image_url = task_data["output"]["results"][0]["url"]
                    # output = task_data.get("output", {})
                    image_url = task_data["output"]["choices"][0]["message"]["content"][0]["image"]
                    return GenerationResult(
                        image_url=image_url,
                        provider="bailian",
                        generation_time=time.perf_counter() - start,
                        raw_response=task_data,
                    )
                if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise RuntimeError(f"Bailian task failed: {task_data}")
                await asyncio.sleep(3)

        raise TimeoutError("Bailian image generation timed out after 120s")
