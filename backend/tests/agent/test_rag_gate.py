from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent import graph


@pytest.mark.anyio
async def test_rag_gate_searches_with_enhanced_prompt_without_structured_filters(monkeypatch) -> None:
    captured: dict = {}
    candidates = [{"image_id": "img-1", "image_url": "/static/library/img-1.png"}]

    async def fake_build_rag_search_query(enhanced_prompt, design_state):
        captured["enhanced_prompt"] = enhanced_prompt
        captured["design_state"] = design_state
        return "现代建筑效果图，玻璃幕墙外立面，黄昏暖光氛围。"

    async def fake_search_by_text(client, *, query, top_k=5, filters=None):
        captured["client"] = client
        captured["query"] = query
        captured["top_k"] = top_k
        captured["filters"] = filters
        return candidates

    monkeypatch.setattr(graph, "get_mcp_client", lambda: object())
    monkeypatch.setattr(graph, "build_rag_search_query", fake_build_rag_search_query)
    monkeypatch.setattr(graph.library_service, "search_by_text", fake_search_by_text)
    monkeypatch.setattr(graph.settings, "RAG_BLOCKING_ENABLED", False)

    result = await graph.rag_gate_node({
        "design_state": {},
        "_enhanced_prompt": {
            "prompt": "现代建筑效果图，玻璃幕墙，黄昏暖光。",
            "negative_prompt": "模糊，水印",
        },
    })

    assert result == {"pending_rag_candidates": candidates}
    assert captured["query"] == "现代建筑效果图，玻璃幕墙外立面，黄昏暖光氛围。"
    assert captured["filters"] is None
    assert captured["top_k"] == 5


@pytest.mark.anyio
async def test_rag_gate_uses_vector_search_without_structured_filters(monkeypatch) -> None:
    captured: dict = {}

    async def fake_search_by_text(client, *, query, top_k=5, filters=None):
        captured["query"] = query
        captured["filters"] = filters
        return []

    monkeypatch.setattr(graph, "get_mcp_client", lambda: object())
    monkeypatch.setattr(graph, "build_rag_search_query", AsyncMock(return_value="现代别墅建筑，石材外立面。"))
    monkeypatch.setattr(graph.library_service, "search_by_text", fake_search_by_text)
    monkeypatch.setattr(graph.settings, "RAG_BLOCKING_ENABLED", False)

    result = await graph.rag_gate_node({
        "design_state": {
            "building_type": "别墅",
            "style": "现代",
        },
        "_enhanced_prompt": {
            "prompt": "现代别墅建筑，石材外立面。",
            "negative_prompt": "模糊",
        },
    })

    assert result == {"pending_rag_candidates": []}
    assert captured["query"] == "现代别墅建筑，石材外立面。"
    assert captured["filters"] is None


@pytest.mark.anyio
async def test_rag_gate_skips_only_when_query_is_empty(monkeypatch) -> None:
    search = AsyncMock()

    monkeypatch.setattr(graph, "get_mcp_client", lambda: object())
    monkeypatch.setattr(graph, "build_rag_search_query", AsyncMock(return_value=""))
    monkeypatch.setattr(graph, "fallback_rag_search_query", lambda design_state: "")
    monkeypatch.setattr(graph.library_service, "search_by_text", search)

    result = await graph.rag_gate_node({
        "design_state": {},
        "_enhanced_prompt": {
            "prompt": "",
            "negative_prompt": "",
        },
    })

    assert result == {}
    search.assert_not_awaited()
