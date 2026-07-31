"""
Small helper layer around the `fastmcp` Client so the Streamlit app can:
  1. discover tools exposed by server.py (the MCP wrapper around the FastAPI app)
  2. convert them into OpenAI-style tool/function definitions
  3. execute a tool call requested by the LLM and return a plain dict result

Everything here is async because fastmcp's Client is async; app.py drives it
with asyncio.run(...) since Streamlit itself is synchronous.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Client


async def fetch_mcp_tools(mcp_url: str) -> list[dict[str, Any]]:
    """Connect to the MCP server and return tool definitions in OpenAI function-calling format."""
    async with Client(mcp_url) as client:
        tools = await client.list_tools()

    openai_tools: list[dict[str, Any]] = []
    for tool in tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    # MCP tools already expose a JSON Schema, which is exactly
                    # what the OpenAI "parameters" field expects.
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}},
                },
            }
        )
    return openai_tools


async def call_mcp_tool(mcp_url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Invoke a single MCP tool and return its result as plain Python data."""
    async with Client(mcp_url) as client:
        result = await client.call_tool(tool_name, arguments)

    # fastmcp's CallToolResult exposes structured content when available,
    # falling back to the raw text/content blocks otherwise.
    if getattr(result, "data", None) is not None:
        return result.data
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content

    parts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts) if parts else str(result)