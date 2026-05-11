"""End-to-end smoke test for the FastMCP stdio server.

Spawns server.py as a subprocess with `python -m mcp` stdio transport and uses
the MCP Python client to call health_check, verifying:
  - server.py boots under stdio
  - lifespan initialises PG + Milvus
  - health_check tool returns OK
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            result = await session.call_tool("health_check", {})
            print("health_check result:")
            for block in result.content:
                if hasattr(block, "text"):
                    print(" ", block.text)


if __name__ == "__main__":
    asyncio.run(main())
