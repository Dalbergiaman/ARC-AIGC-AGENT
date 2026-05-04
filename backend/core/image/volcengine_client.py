import time

import httpx

from core.image.base import GenerationRequest, GenerationResult, ImageGeneratorBase


class VolcengineClient(ImageGeneratorBase):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "prompt": request.prompt,
            "size": f"{request.width}x{request.height}",
            "response_format": "url",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        image_url = data["data"][0]["url"]
        return GenerationResult(
            image_url=image_url,
            provider="volcengine",
            generation_time=time.perf_counter() - start,
            raw_response=data,
        )
