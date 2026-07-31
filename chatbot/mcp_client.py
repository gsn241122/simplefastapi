"""Thin, synchronous MCP client API used by the rest of the app.

Tuning yang diterapkan:
- Mengganti `print` mentah dengan standar Python `logging`.
- Retry otomatis dengan backoff saat tool call mengalami transient error.
- Caching/Safe validation pada load_mcp_config.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from config import DEFAULT_CALL_TIMEOUT_SECONDS, DEFAULT_CONNECT_TIMEOUT_SECONDS
from mcp_pool import MCPConnectionPool

logger = logging.getLogger("mcp_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_pool: MCPConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> MCPConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = MCPConnectionPool()
    return _pool


def load_mcp_config(config_path: str = "mcp_servers.json") -> dict[str, dict]:
    if not os.path.exists(config_path):
        logger.warning(f"MCP config not found at '{config_path}'")
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
    except Exception as exc:
        logger.error(f"Failed to load MCP config: {exc}")
        return {}


def _tool_input_schema(tool: Any) -> dict:
    schema = getattr(tool, "inputSchema", None)
    if schema is None:
        schema = getattr(tool, "input_schema", None)
    return schema or {"type": "object", "properties": {}}


def _extract_result(result: Any) -> Any:
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
    openai_tools: list[dict[str, Any]] = []
    tool_to_server: dict[str, str] = {}
    tool_to_real_name: dict[str, str] = {}
    server_errors: dict[str, str] = {}

    logger.info(f"Connecting to {len(config)} server(s) in parallel...")
    results = get_pool().list_tools_many(config, connect_timeout=connect_timeout)

    for server_name, (tools, error) in results.items():
        if error:
            logger.error(f"Error fetching tools from '{server_name}': {error}")
            server_errors[server_name] = error
            continue

        logger.info(f"Found {len(tools or [])} tools from '{server_name}'")
        for tool in (tools or []):
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
    max_retries: int = 2,
) -> Any:
    server_name = tool_to_server.get(tool_name)
    if not server_name:
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

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"Calling tool '{real_tool_name}' on server '{server_name}' (attempt {attempt}/{max_retries})..."
            )
            result = get_pool().call_tool(
                server_name,
                server_config,
                real_tool_name,
                arguments,
                connect_timeout=connect_timeout,
                call_timeout=call_timeout,
            )
            logger.info(f"Tool '{real_tool_name}' executed successfully")
            return _extract_result(result)
        except Exception as e:
            last_exc = e
            logger.warning(f"Attempt {attempt} failed for '{real_tool_name}': {e}")
            if attempt < max_retries:
                time.sleep(0.5 * attempt)  # exponential backoff

    error_msg = f"{type(last_exc).__name__}: {last_exc}"
    logger.error(f"Error calling tool '{real_tool_name}' after {max_retries} attempts: {error_msg}")
    return {"error": error_msg}
