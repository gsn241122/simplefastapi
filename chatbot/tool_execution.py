"""Helpers for parsing, executing, and gating MCP tool calls."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from config import DANGEROUS_HTTP_METHODS, DANGEROUS_NAME_KEYWORDS
from mcp_client import call_mcp_tool_by_name


def get_thought_signature(tool_call: Any) -> dict | None:
    """Extract the `extra_content.google.thought_signature` field Gemini
    attaches to function-call parts.

    Gemini 3.x models require this to be echoed back on the next request, or
    tool calling breaks with a 400 error.
    """
    extra = getattr(tool_call, "extra_content", None)
    if extra is None:
        model_extra = getattr(tool_call, "model_extra", None) or {}
        extra = model_extra.get("extra_content")
    return extra


def parse_tool_arguments(tool_call: Any) -> dict[str, Any]:
    """Safely parse a tool call's JSON arguments, defaulting to {} on failure."""
    try:
        return json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        return {}


def is_dangerous_tool_call(tool_call: Any, args: dict[str, Any], safe_mode: bool) -> bool:
    """Decide whether a tool call should be confirmed by the user before running."""
    if not safe_mode:
        return False

    name = tool_call.function.name

    if name == "call_api" and args.get("method", "").upper() in DANGEROUS_HTTP_METHODS:
        return True

    return any(keyword in name.lower() for keyword in DANGEROUS_NAME_KEYWORDS)


def run_tool_call(
    tool_call: Any,
    mcp_config: dict,
    tool_to_server: dict,
    bearer_token: str | None,
) -> dict:
    """Execute one OpenAI-style tool_call against the correct MCP server.

    Returns a chat message dict (role="tool") ready to append to the
    conversation history.
    """
    name = tool_call.function.name
    args = parse_tool_arguments(tool_call)

    # Auto-inject the Bearer token for call_api so the model never has to
    # know or ask about credentials.
    if name == "call_api" and bearer_token:
        headers = dict(args.get("headers") or {})
        headers.setdefault("Authorization", f"Bearer {bearer_token}")
        args["headers"] = headers

    try:
        result = asyncio.run(call_mcp_tool_by_name(mcp_config, tool_to_server, name, args))
    except Exception as exc:
        result = {"error": str(exc)}

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, default=str),
    }


def cancelled_tool_result(tool_call: Any) -> dict:
    """Build a tool-result message for a call the user rejected in Safe Mode."""
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(
            {"error": "Action cancelled by the user because Safe Mode is enabled."}
        ),
    }