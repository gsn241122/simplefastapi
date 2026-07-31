"""Small helper layer to support multiple MCP servers configured via
mcp_servers.json.

- HTTP/SSE servers: via fastmcp.Client
- Stdio servers: via mcp.ClientSession + mcp.client.stdio.stdio_client
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Any


def load_mcp_config(config_path: str = "mcp_servers.json") -> dict[str, dict]:
    """Load MCP server configurations from a JSON file.

    Returns an empty dict if the file doesn't exist. Accepts both
    `{"mcpServers": {...}}` and a bare `{...}` mapping at the top level.
    """
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("mcpServers", data)


def _is_stdio_server(server_config: dict) -> bool:
    """Check if server config is for a stdio-based server."""
    return "command" in server_config


def _is_http_server(server_config: dict) -> bool:
    """Check if server config is for an HTTP/SSE-based server."""
    return "url" in server_config


def _tool_input_schema(tool: Any) -> dict:
    """Get a tool's JSON schema, tolerating both SDK naming conventions.

    Older `mcp` SDK versions expose `tool.inputSchema` (camelCase); newer
    versions expose `tool.input_schema` (snake_case). Fall back to an empty
    object schema if neither is present.
    """
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    return schema or {"type": "object", "properties": {}}


async def _fetch_stdio_tools(server_config: dict) -> list:
    """Fetch tools from a stdio-based MCP server using the `mcp` package directly."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = server_config["command"]
    args = server_config.get("args", [])
    env = server_config.get("env")

    if not shutil.which(command):
        raise ValueError(f"Command '{command}' not found in PATH. Make sure it's installed.")

    params = StdioServerParameters(command=command, args=args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


async def _fetch_http_tools(server_config: dict) -> list:
    """Fetch tools from an HTTP/SSE-based MCP server using fastmcp.Client."""
    from fastmcp import Client

    url = server_config["url"]
    async with Client(url) as client:
        return await client.list_tools()


async def fetch_all_mcp_tools(
    config: dict[str, dict],
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """Connect to all configured MCP servers and return their tool definitions.

    Returns:
        - openai_tools: tool definitions in OpenAI function-calling format
        - tool_to_server: mapping of tool_name -> server_name
        - server_errors: mapping of server_name -> error_message (for
          servers that failed to connect)
    """
    openai_tools: list[dict[str, Any]] = []
    tool_to_server: dict[str, str] = {}
    server_errors: dict[str, str] = {}

    for server_name, server_config in config.items():
        try:
            print(f"[MCP] Connecting to '{server_name}'...", file=sys.stderr)

            if _is_stdio_server(server_config):
                tools = await _fetch_stdio_tools(server_config)
            elif _is_http_server(server_config):
                tools = await _fetch_http_tools(server_config)
            else:
                raise ValueError("Server config must contain 'url' or 'command'")

            print(f"[MCP] Found {len(tools)} tools from '{server_name}'", file=sys.stderr)

            for tool in tools:
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": _tool_input_schema(tool),
                        },
                    }
                )
                tool_to_server[tool.name] = server_name
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            print(f"[MCP] Error fetching tools from '{server_name}': {error_msg}", file=sys.stderr)
            server_errors[server_name] = error_msg

    return openai_tools, tool_to_server, server_errors


def _extract_text_content(result: Any) -> str:
    """Join every `.text` block found in an MCP tool result's `.content` list."""
    parts = [block.text for block in getattr(result, "content", []) or [] if getattr(block, "text", None)]
    return "\n".join(parts) if parts else str(result)


async def _call_stdio_tool(server_config: dict, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool on a stdio-based MCP server."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = server_config["command"]
    args = server_config.get("args", [])
    env = server_config.get("env")

    params = StdioServerParameters(command=command, args=args, env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return _extract_text_content(result)


async def _call_http_tool(server_config: dict, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool on an HTTP/SSE-based MCP server."""
    from fastmcp import Client

    url = server_config["url"]
    async with Client(url) as client:
        result = await client.call_tool(tool_name, arguments)

        if getattr(result, "data", None) is not None:
            return result.data
        if getattr(result, "structured_content", None) is not None:
            return result.structured_content

        return _extract_text_content(result)


async def call_mcp_tool_by_name(
    config: dict[str, dict],
    tool_to_server: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Invoke a single MCP tool by routing it to the correct server.

    Returns the tool's result, or a dict with an "error" key if the tool
    couldn't be found, isn't configured, or raised an exception.
    """
    server_name = tool_to_server.get(tool_name)
    if not server_name:
        return {"error": f"Tool '{tool_name}' not found in any configured MCP server."}

    server_config = config.get(server_name)
    if not server_config:
        return {"error": f"Server config for '{server_name}' not found."}

    try:
        print(
            f"[MCP] Calling tool '{tool_name}' on server '{server_name}' with args: {arguments}",
            file=sys.stderr,
        )

        if _is_stdio_server(server_config):
            result = await _call_stdio_tool(server_config, tool_name, arguments)
        elif _is_http_server(server_config):
            result = await _call_http_tool(server_config, tool_name, arguments)
        else:
            return {"error": "Invalid server configuration"}

        print(f"[MCP] Tool '{tool_name}' executed successfully", file=sys.stderr)
        return result
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"[MCP] Error calling tool '{tool_name}': {error_msg}", file=sys.stderr)
        return {"error": error_msg}