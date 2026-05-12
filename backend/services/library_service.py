"""Backend wrapper around image-rag-mcp tools.

Each call opens a short-lived MCP stdio session via the shared
``MultiServerMCPClient`` stored on ``app.state.mcp_client`` (started in
``main.lifespan``). Tool results are parsed from FastMCP's
``structuredContent`` / text blocks into plain Python objects.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

_SERVER_NAME = "image-rag"


def _parse_tool_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            return json.loads(text)
    return None


async def _call(client: MultiServerMCPClient, tool: str, arguments: dict[str, Any]) -> Any:
    async with client.session(_SERVER_NAME) as session:
        result = await session.call_tool(tool, arguments)
    return _parse_tool_result(result)


async def store_image(
    client: MultiServerMCPClient,
    *,
    image_url: str,
    prompt: str,
    session_id: str | None = None,
    negative_prompt: str | None = None,
    design_state: dict[str, Any] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        "store_generated_image",
        {
            "image_url": image_url,
            "prompt": prompt,
            "session_id": session_id,
            "negative_prompt": negative_prompt,
            "design_state": design_state,
            "provider": provider,
        },
    )


async def search_by_text(
    client: MultiServerMCPClient,
    *,
    query: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    return await _call(
        client,
        "search_by_text",
        {"query": query, "top_k": top_k, "filters": filters},
    )


async def search_by_image(
    client: MultiServerMCPClient,
    *,
    image_url: str,
    top_k: int = 5,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    return await _call(
        client,
        "search_by_image",
        {"image_url": image_url, "top_k": top_k, "filters": filters},
    )


async def get_image_by_id(
    client: MultiServerMCPClient,
    *,
    image_id: str,
) -> dict[str, Any] | None:
    return await _call(client, "get_image_by_id", {"image_id": image_id})
