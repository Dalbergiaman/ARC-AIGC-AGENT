import time
import httpx
import json
from core.image.base import GenerationRequest, GenerationResult, ImageGeneratorBase


class GrsaiClient(ImageGeneratorBase):
    api_mapping = {
        "gpt-image": "/v1/draw/completions",
        "nano-banana": "/v1/draw/nano-banana",
    }
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        for key in self.api_mapping:
            if key in model:
                self._endpoint = "https://grsai.dakka.com.cn" + self.api_mapping[key]
                break

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        start = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if "gpt-image" in self._model:
            payload = {
                "model": self._model,
                "prompt": request.prompt,
                "aspectRatio": "1:1",
                "quality": "auto",
                "shutProgress": True
            }
        elif "nano-banana" in self._model:
            payload = {
                "model": self._model,
                "prompt": request.prompt,
                "aspectRatio": "auto",
                "imageSize": "2k",
                "shutProgress": True
            }

        async with httpx.AsyncClient(timeout=120.0) as client:
            # 关键修改点 1: 使用 stream 上下文管理器
            response = await client.post(self._endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.text
            data = json.loads(data[6:])

        image_url = data["results"][0]["url"]
        # print("id: ", data["id"])
        return GenerationResult(
            image_url=image_url,
            provider="grsai",
            generation_time=time.perf_counter() - start,
            raw_response=data,
        )
