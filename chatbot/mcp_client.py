"""Thin, synchronous MCP client API used by the rest of the app.

Connection lifecycle (opening stdio subprocesses / HTTP sessions, keeping
them alive, tearing them down on failure) is delegated to the persistent
connection pool in `mcp_pool.py`. This module is responsible for:
  - loading mcp_servers.json
  - converting MCP tool definitions into OpenAI function-calling format
  - normalizing tool-call results into plain Python values
"""
from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any

from config import DEFAULT_CALL_TIMEOUT_SECONDS, DEFAULT_CONNECT_TIMEOUT_SECONDS
from mcp_pool import MCPConnectionPool

_pool: MCPConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> MCPConnectionPool:
    """Return the process-wide MCP connection pool, creating it on first use.

    A single pool is shared across all Streamlit sessions in this process,
    which is what lets tool connections persist across reruns instead of
    reconnecting on every interaction.
    """
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = MCPConnectionPool()
    return _pool


def load_mcp_config(config_path: str = "mcp_servers.json") -> dict[str, dict]:
    """Load MCP server configurations from a JSON file.

    Returns an empty dict if the file doesn't exist, is invalid JSON, or doesn't
    contain a dictionary. Accepts both `{"mcpServers": {...}}` and a bare
    `{...}` mapping at the top level.
    """
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {}
            mcp_servers = data.get("mcpServers")
            if isinstance(mcp_servers, dict):
                return mcp_servers
            return data
    except Exception:
        return {}


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


def _extract_result(result: Any) -> Any:
    """Normalize a tool-call result from either `mcp.ClientSession` or
    `fastmcp.Client` into a plain string/dict/list.
    """
    if getattr(result, "data", None) is not None:
        return result.data
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content

    parts = [block.text for block in getattr(result, "content", []) or [] if getattr(block, "text", None)]
    return "\n".join(parts) if parts else str(result)


def fetch_all_mcp_tools(
    config: dict[str, dict],
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str], dict[str, str]]:
    """Connect to every configured MCP server *concurrently* (reusing any
    already-open connections) and return their tool definitions.

    Returns:
        - openai_tools: tool definitions in OpenAI function-calling format
        - tool_to_server: mapping of tool_name -> server_name
        - tool_to_real_name: mapping of tool_name -> actual_mcp_tool_name
        - server_errors: mapping of server_name -> error_message (for
          servers that failed to connect)
    """
    openai_tools: list[dict[str, Any]] = []
    tool_to_server: dict[str, str] = {}
    tool_to_real_name: dict[str, str] = {}
    server_errors: dict[str, str] = {}

    print(f"[MCP] Connecting to {len(config)} server(s) in parallel...", file=sys.stderr)
    results = get_pool().list_tools_many(config, connect_timeout=connect_timeout)

    for server_name, (tools, error) in results.items():
        if error:
            print(f"[MCP] Error fetching tools from '{server_name}': {error}", file=sys.stderr)
            server_errors[server_name] = error
            continue

        print(f"[MCP] Found {len(tools)} tools from '{server_name}'", file=sys.stderr)
        for tool in tools:
            # Always prefix tool names with server_name__ for clarity and collision prevention
            func_name = f"{server_name}__{tool.name}"

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "description": tool.description or "",
                        "parameters": _tool_input_schema(tool),
                    },
                }
            )
            tool_to_server[func_name] = server_name
            tool_to_real_name[func_name] = tool.name

    return openai_tools, tool_to_server, tool_to_real_name, server_errors


def call_mcp_tool_by_name(
    config: dict[str, dict],
    tool_to_server: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
    tool_to_real_name: dict[str, str] | None = None,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    call_timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS,
) -> Any:
    """Invoke a single MCP tool, reusing the server's persistent connection."""
    server_name = tool_to_server.get(tool_name)
    if not server_name:
        # Fallback: match if tool_name was passed without prefix (e.g. "call_api" -> "fastapi__call_api")
        for registered_name, sname in tool_to_server.items():
            if registered_name.endswith(f"__{tool_name}"):
                tool_name = registered_name
                server_name = sname
                break

    if not server_name:
        return {"error": f"Tool '{tool_name}' not found in any configured MCP server."}

    server_config = config.get(server_name)
    if not server_config:
        return {"error": f"Server config for '{server_name}' not found."}

    real_tool_name = (tool_to_real_name or {}).get(tool_name, tool_name)

    try:
        print(
            f"[MCP] Calling tool '{real_tool_name}' (registered as '{tool_name}') on server '{server_name}' with args: {arguments}",
            file=sys.stderr,
        )
        result = get_pool().call_tool(
            server_name,
            server_config,
            real_tool_name,
            arguments,
            connect_timeout=connect_timeout,
            call_timeout=call_timeout,
        )
        print(f"[MCP] Tool '{real_tool_name}' executed successfully", file=sys.stderr)
        return _extract_result(result)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        print(f"[MCP] Error calling tool '{real_tool_name}': {error_msg}", file=sys.stderr)
        return {"error": error_msg}