"""Thin, synchronous MCP client API used by the rest of the app."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_CALL_TIMEOUT_SECONDS,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAX_TOOL_RETRIES,
    DEFAULT_RETRY_BACKOFF_BASE_SECONDS,
)
from mcp_pool import MCPConnectionPool
from security import is_retryable_exception

__all__ = [
    "get_pool",
    "load_mcp_config",
    "fetch_all_mcp_tools",
    "call_mcp_tool_by_name",
]

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logger = logging.getLogger("mcp_client")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_MCP_CONFIG_PATH = "mcp_servers.json"
_HERE = Path(__file__).resolve().parent


def _resolve_skills_dir() -> Path:
    """Tentukan folder skills: absolut dipakai langsung, relatif → berbasis lokasi file ini."""
    raw = os.environ.get("SKILLS_DIR", "skills")
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (_HERE / candidate).resolve()


SKILLS_DIR = _resolve_skills_dir()

#: Nama server semu untuk tool bawaan (agar UI tidak menampilkan "unknown")
LOCAL_SERVER_NAME = "local"

# --------------------------------------------------------------------------- #
# Connection pool (lazy singleton)
# --------------------------------------------------------------------------- #
_pool: MCPConnectionPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> MCPConnectionPool:
    """Return the process-wide MCP connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = MCPConnectionPool()
    return _pool


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_mcp_config(config_path: str = DEFAULT_MCP_CONFIG_PATH) -> dict[str, dict]:
    if not os.path.exists(config_path):
        logger.warning("MCP config not found at '%s'", config_path)
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.error("Failed to load MCP config: %s", exc)
        return {}

    if not isinstance(data, dict):
        logger.error("MCP config root must be a JSON object, got %s", type(data).__name__)
        return {}

    mcp_servers = data.get("mcpServers")
    return mcp_servers if isinstance(mcp_servers, dict) else data


# --------------------------------------------------------------------------- #
# Local (non-MCP) tools execution
# --------------------------------------------------------------------------- #
def _handle_local_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Eksekusi tool bawaan (list_skills, read_skill) secara lokal."""
    try:
        if tool_name == "list_skills":
            if not SKILLS_DIR.is_dir():
                return {"skills": [], "message": "Skills directory not found."}
            files = sorted(
                str(p.relative_to(SKILLS_DIR)) for p in SKILLS_DIR.rglob("*.md")
            )
            return {"skills": files}

        if tool_name == "read_skill":
            skill_path = (arguments.get("skill_path") or "").strip()
            if not skill_path:
                return {"error": "'skill_path' is required."}

            root = SKILLS_DIR.resolve()
            target = (root / skill_path).resolve()
            # Cegah path traversal
            if not target.is_relative_to(root):
                return {"error": "Access denied: path escapes skills directory."}
            if not target.is_file():
                return {"error": f"Skill file not found: {skill_path}"}
            return target.read_text(encoding="utf-8")

        return {"error": f"Unknown local tool '{tool_name}'."}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _tool_input_schema(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    return schema or {"type": "object", "properties": {}}


def _extract_result(result: Any) -> Any:
    data = getattr(result, "data", None)
    if data is not None:
        return data
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None) or []
    parts = [block.text for block in content if getattr(block, "text", None)]
    return "\n".join(parts) if parts else str(result)


# --------------------------------------------------------------------------- #
# Tool discovery
# --------------------------------------------------------------------------- #
def fetch_all_mcp_tools(
    config: dict[str, dict],
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str], dict[str, str]]:
    
    openai_tools: list[dict[str, Any]] = []
    tool_to_server: dict[str, str] = {}
    tool_to_real_name: dict[str, str] = {}
    server_errors: dict[str, str] = {}

    # 1. Tambahkan tool lokal dengan prefix "local__"
    local_tools = [
        {
            "name": "list_skills",
            "description": "List all available skills in the skills directory.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "read_skill",
            "description": "Read the content of a specific skill file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_path": {"type": "string", "description": "The path to the skill file, e.g., 'coding/best_practices.md'"}
                },
                "required": ["skill_path"],
            },
        },
    ]

    for tool in local_tools:
        func_name = f"{LOCAL_SERVER_NAME}__{tool['name']}"
        openai_tools.append({
            "type": "function",
            "function": {
                "name": func_name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
        })
        tool_to_server[func_name] = LOCAL_SERVER_NAME
        tool_to_real_name[func_name] = tool["name"]

    # 2. Fetch tool dari MCP Servers
    logger.info("Connecting to %d server(s) in parallel...", len(config))
    results = get_pool().list_tools_many(config, connect_timeout=connect_timeout)

    if not isinstance(results, dict):
        logger.error("Unexpected results type from list_tools_many: %s", type(results).__name__)
        return openai_tools, tool_to_server, tool_to_real_name, server_errors

    for server_name, result_data in results.items():
        if not isinstance(result_data, (list, tuple)) or len(result_data) != 2:
            logger.error("Invalid result format from server '%s': %r", server_name, result_data)
            server_errors[server_name] = "Invalid response format from pool"
            continue

        tools, error = result_data
        if error:
            logger.error("Error fetching tools from '%s': %s", server_name, error)
            server_errors[server_name] = error
            continue

        tools = tools or []
        logger.info("Found %d tools from '%s'", len(tools), server_name)
        for tool in tools:
            func_name = f"{server_name}__{tool.name}"
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": func_name,
                    "description": tool.description or "",
                    "parameters": _tool_input_schema(tool),
                },
            })
            tool_to_server[func_name] = server_name
            tool_to_real_name[func_name] = tool.name

    return openai_tools, tool_to_server, tool_to_real_name, server_errors


# --------------------------------------------------------------------------- #
# Tool invocation
# --------------------------------------------------------------------------- #
def call_mcp_tool_by_name(
    config: dict[str, dict],
    tool_to_server: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
    tool_to_real_name: dict[str, str] | None = None,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    call_timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_TOOL_RETRIES,
) -> Any:
    
    server_name = tool_to_server.get(tool_name)

    # Fallback jika LLM memanggil tanpa prefix server
    if not server_name:
        for registered_name, sname in tool_to_server.items():
            if registered_name.endswith(f"__{tool_name}"):
                tool_name = registered_name
                server_name = sname
                break

    if not server_name:
        return {"error": f"Tool '{tool_name}' not found in any configured server."}

    real_tool_name = (tool_to_real_name or {}).get(tool_name, tool_name)

    # INTERSEP: Jika server-nya adalah "local", jalankan fungsi Python lokal
    if server_name == LOCAL_SERVER_NAME:
        logger.info("Executing local tool '%s'", real_tool_name)
        return _handle_local_tool(real_tool_name, arguments)

    # Sisanya adalah logika MCP Server standar
    server_config = config.get(server_name)
    if not server_config:
        return {"error": f"Server config for '{server_name}' not found."}

    max_retries = max(1, max_retries)
    last_exc: Exception | None = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Calling tool '%s' on server '%s' (attempt %d/%d)...", 
                        real_tool_name, server_name, attempt, max_retries)
            result = get_pool().call_tool(
                server_name, server_config, real_tool_name, arguments,
                connect_timeout=connect_timeout, call_timeout=call_timeout,
            )
            logger.info("Tool '%s' executed successfully", real_tool_name)
            return _extract_result(result)
        except Exception as e:
            last_exc = e
            retryable = is_retryable_exception(e)
            logger.warning("Attempt %d failed for '%s': %s (%s)", 
                           attempt, real_tool_name, e, "retryable" if retryable else "not retryable")
            if not retryable:
                break
            if attempt < max_retries:
                time.sleep(DEFAULT_RETRY_BACKOFF_BASE_SECONDS * attempt)

    error_msg = f"{type(last_exc).__name__}: {last_exc}"
    logger.error("Error calling tool '%s' after %d attempt(s): %s", real_tool_name, attempt, error_msg)
    return {"error": error_msg}