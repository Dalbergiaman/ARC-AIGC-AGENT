import json
from collections.abc import AsyncIterator

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from core.llm.base import LLMClientBase

_MAX_RETRIES = 2
_TIMEOUT = 60.0


def _build_messages(
    messages: list[BaseMessage],
    images: list[str] | None = None,
) -> list[dict]:
    result = []
    for i, msg in enumerate(messages):
        if isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        else:
            role = "user"

        # attach images to the last human message only
        if images and role == "user" and i == len(messages) - 1:
            content: list[dict] | str = [{"type": "text", "text": str(msg.content)}]
            for url in images:
                content.append({"type": "image_url", "image_url": {"url": url}})
        else:
            content = str(msg.content)

        result.append({"role": role, "content": content})
    return result


class _BaseHTTPLLMClient(LLMClientBase):
    _endpoint: str  # subclasses must set this

    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, payload: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    response = await client.post(
                        self._endpoint,
                        headers=self._headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
        raise RuntimeError(f"LLM request failed after {_MAX_RETRIES + 1} attempts") from last_exc

    async def ainvoke(self, messages: list[BaseMessage]) -> str:
        payload = {
            "model": self._model,
            "messages": _build_messages(messages),
        }
        data = await self._post(payload)
        return data["choices"][0]["message"]["content"]

    async def ainvoke_with_vision(
        self,
        messages: list[BaseMessage],
        images: list[str],
    ) -> str:
        payload = {
            "model": self._model,
            "messages": _build_messages(messages, images),
        }
        data = await self._post(payload)
        return data["choices"][0]["message"]["content"]

    async def astream(
        self,
        messages: list[BaseMessage],
        images: list[str] | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": _build_messages(messages, images),
            "stream": True,
        }
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    async with client.stream(
                        "POST",
                        self._endpoint,
                        headers=self._headers,
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            chunk = line[len("data:"):].strip()
                            if chunk == "[DONE]":
                                return
                            try:
                                delta = json.loads(chunk)
                                content = delta["choices"][0]["delta"].get("content")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError):
                                continue
                        return
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
        raise RuntimeError(f"LLM stream failed after {_MAX_RETRIES + 1} attempts") from last_exc
