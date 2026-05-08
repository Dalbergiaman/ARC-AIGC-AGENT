from langchain_core.tools import tool

from agent.state import ImageRecord
from core.observability import observe, update_current_span


@tool
@observe(name="tool:search_similar_cases", as_type="retriever")
async def search_similar_cases(
    query: str,
    building_type: str = "",
    style: str = "",
) -> list[dict]:
    """Search the image library for similar architectural cases using text query.

    Uses RAG (MCP search_by_text) to find relevant historical cases.
    Results are used by enhance_prompt to improve generation quality.

    Stub: MCP integration will be wired in D-4.
    """
    # D-4: replace with MCP client call
    # from langchain_mcp_adapters.client import MultiServerMCPClient
    # results = await mcp_client.call_tool("search_by_text", {...})
    results: list[dict] = []
    update_current_span(
        input={"query": query, "building_type": building_type, "style": style},
        output={"result_count": len(results), "results": results},
        metadata={"stub": True},
    )
    return results
