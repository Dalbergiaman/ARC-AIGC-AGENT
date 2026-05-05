from langchain_core.tools import tool

from agent.state import ImageRecord


@tool
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
    return []
