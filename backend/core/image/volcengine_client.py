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
        image_urls = request.input_image_urls or [
            url for url in [request.control_image_url or request.ref_image_url] if url
        ]
        if image_urls:
            payload["image"] = image_urls if len(image_urls) > 1 else image_urls[0]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._endpoint, headers=headers, json=payload)
            if not response.is_success:
                raise ValueError(f"Volcengine API error {response.status_code}: {response.text}")
            data = response.json()

        image_url = data["data"][0]["url"]
        return GenerationResult(
            image_url=image_url,
            provider="volcengine",
            generation_time=time.perf_counter() - start,
            raw_response=data,
        )
