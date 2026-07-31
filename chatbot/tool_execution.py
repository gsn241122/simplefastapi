"""Helpers for parsing, executing, and gating MCP tool calls."""
from __future__ import annotations

import base64
import json
from typing import Any

from config import DANGEROUS_HTTP_METHODS
from mcp_client import call_mcp_tool_by_name


def _json_default(obj: Any) -> Any:
    """Safe serializer for non-JSON native objects, including binary byte data."""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return f"<binary_data: {len(obj)} bytes, base64={base64.b64encode(obj).decode('ascii')}>"
    return str(obj)


def get_tool_call_name(tool_call: Any) -> str:
    """Safely extract the function name from a tool call object or dict."""
    if isinstance(tool_call, dict):
        return tool_call.get("function", {}).get("name", "")
    return getattr(getattr(tool_call, "function", None), "name", "")


def get_tool_call_id(tool_call: Any) -> str:
    """Safely extract the tool call ID from a tool call object or dict."""
    if isinstance(tool_call, dict):
        return tool_call.get("id", "")
    return getattr(tool_call, "id", "")


def get_thought_signature(tool_call: Any) -> dict | None:
    """Extract the `extra_content.google.thought_signature` field Gemini
    attaches to function-call parts.

    Gemini 3.x models require this to be echoed back on the next request, or
    tool calling breaks with a 400 error.
    """
    if isinstance(tool_call, dict):
        return tool_call.get("extra_content")
    extra = getattr(tool_call, "extra_content", None)
    if extra is None:
        model_extra = getattr(tool_call, "model_extra", None) or {}
        extra = model_extra.get("extra_content")
    return extra


def parse_tool_arguments(tool_call: Any) -> dict[str, Any]:
    """Safely parse a tool call's JSON arguments, defaulting to {} on failure."""
    try:
        if isinstance(tool_call, dict):
            args_str = tool_call.get("function", {}).get("arguments", "{}")
        else:
            args_str = getattr(getattr(tool_call, "function", None), "arguments", "{}")
        return json.loads(args_str or "{}")
    except json.JSONDecodeError:
        return {}


def is_dangerous_tool_call(
    tool_call: Any,
    args: dict[str, Any],
    safe_mode: bool,
    dangerous_keywords: tuple[str, ...],
    dry_run_mode: bool = False,
) -> bool:
    """Decide whether a tool call should be confirmed by the user before running."""
    if dry_run_mode:
        return True  # tuned: dry-run mode forces confirmation on all tools

    if not safe_mode:
        return False

    name = get_tool_call_name(tool_call)

    if name.endswith("call_api") and args.get("method", "").upper() in DANGEROUS_HTTP_METHODS:
        return True

    return any(keyword in name.lower() for keyword in dangerous_keywords)


def run_tool_call(
    tool_call: Any,
    mcp_config: dict,
    tool_to_server: dict,
    tool_to_real_name: dict[str, str] | None,
    bearer_token: str | None,
    call_timeout: float,
) -> dict:
    """Execute one OpenAI-style tool_call against the correct MCP server.

    Reuses the server's persistent connection (see mcp_pool.py) instead of
    reconnecting from scratch on every call.
    Returns a chat message dict (role="tool") ready to append to the
    conversation history.
    """
    name = get_tool_call_name(tool_call)
    tool_id = get_tool_call_id(tool_call)
    args = parse_tool_arguments(tool_call)

    # Auto-inject the Bearer token for call_api so the model never has to
    # know or ask about credentials.
    if name.endswith("call_api") and bearer_token:
        headers = dict(args.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {bearer_token}")
        args["headers"] = headers

    try:
        result = call_mcp_tool_by_name(
            mcp_config,
            tool_to_server,
            name,
            args,
            tool_to_real_name=tool_to_real_name,
            call_timeout=call_timeout,
        )
    except Exception as exc:
        result = {"error": str(exc)}

    return {
        "role": "tool",
        "tool_call_id": tool_id,
        "content": json.dumps(result, default=_json_default),
    }


def cancelled_tool_result(tool_call: Any) -> dict:
    """Build a tool-result message for a call the user rejected in Safe Mode."""
    return {
        "role": "tool",
        "tool_call_id": get_tool_call_id(tool_call),
        "content": json.dumps(
            {"error": "Action cancelled by the user because Safe Mode is enabled."}
        ),
    }