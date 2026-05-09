import time
import httpx
import json
from core.image.base import GenerationRequest, GenerationResult, ImageGeneratorBase


def _parse_grsai_response(text: str) -> dict:
    """Parse GrsAI response, tolerating both SSE-style ('data: {...}') and bare JSON.

    Some endpoints / models return SSE chunks where the last data line carries the
    final result; others return a plain JSON body. Pick the last 'data: ' line if
    present, otherwise fall back to the whole body as JSON.
    """
    stripped = text.strip()
    if not stripped:
        raise RuntimeError("GrsAI returned empty response")

    last_payload: str | None = None
    for line in stripped.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            last_payload = line[len("data:"):].strip()
    payload = last_payload if last_payload is not None else stripped
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GrsAI response is not valid JSON: {text[:200]}") from exc


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

        image_urls = request.input_image_urls or [
            url for url in [request.control_image_url or request.ref_image_url] if url
        ]
        if image_urls:
            payload["urls"] = image_urls

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self._endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = _parse_grsai_response(response.text)

        if not data.get("results"):
            status = data.get("status", "unknown")
            error = data.get("error") or data.get("failure_reason") or "no results returned"
            raise RuntimeError(f"GrsAI generation failed (status={status}): {error}")
        image_url = data["results"][0]["url"]
        return GenerationResult(
            image_url=image_url,
            provider="grsai",
            generation_time=time.perf_counter() - start,
            raw_response=data,
        )
