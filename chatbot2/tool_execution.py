"""Helpers for parsing, executing, and gating MCP tool calls."""
from __future__ import annotations

import base64
import json
import time
from typing import Any

from config import TOOL_RESULT_LLM_TRUNCATE_CHARS
from mcp_client import call_mcp_tool_by_name
from security import classify_tool_risk, redact_secrets


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
        return True  # dry-run mode forces confirmation on every tool call

    if not safe_mode:
        return False

    name = get_tool_call_name(tool_call)
    return classify_tool_risk(name, args, dangerous_keywords)


def _inject_auth_header(name: str, args: dict[str, Any], bearer_token: str | None) -> dict[str, Any]:
    """Attach the app-managed Bearer token to `call_api` calls.

    This ALWAYS overwrites any `Authorization` header the model itself
    supplied in its tool-call arguments, rather than only filling it in if
    absent. A model should never be able to substitute its own auth value —
    the token the user logged in with is the only one that should ever be
    sent, whether the model's own value was a hallucination or (in a
    prompt-injection scenario) an attacker-controlled string.
    """
    if not ((name == "call_api" or name.endswith("__call_api")) and bearer_token):
        return args
    headers = dict(args.get("headers") or {})
    headers["Authorization"] = f"Bearer {bearer_token}"
    return {**args, "headers": headers}


def _truncate_for_llm(result: Any) -> Any:
    """Optionally truncate a large tool result before it is sent back to the
    LLM as a `tool` message. The full, untruncated result is still what gets
    audit-logged and can still be inspected via the debug panel.

    Unlike the old behaviour (truncate only at display time, always send the
    full payload to the model), this caps token/context usage for very large
    tool outputs (e.g. reading a big file) while leaving small results
    untouched. Set config.TOOL_RESULT_LLM_TRUNCATE_CHARS = None to disable.
    """
    if TOOL_RESULT_LLM_TRUNCATE_CHARS is None:
        return result
    try:
        serialized = json.dumps(result, default=_json_default)
    except Exception:
        return result
    if len(serialized) <= TOOL_RESULT_LLM_TRUNCATE_CHARS:
        return result
    truncated = serialized[:TOOL_RESULT_LLM_TRUNCATE_CHARS]
    return {
        "truncated": True,
        "note": (
            f"Result truncated to {TOOL_RESULT_LLM_TRUNCATE_CHARS:,} of "
            f"{len(serialized):,} characters to control context size."
        ),
        "content": truncated,
    }


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
    reconnecting from scratch on every call. Returns a chat message dict
    (role="tool") ready to append to the conversation history.
    """
    name = get_tool_call_name(tool_call)
    tool_id = get_tool_call_id(tool_call)
    args = parse_tool_arguments(tool_call)
    args = _inject_auth_header(name, args, bearer_token)

    t0 = time.perf_counter()
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
    duration = time.perf_counter() - t0

    # Redact secrets ONCE, here, at the source. `redacted_result` is what
    # flows into: the audit log, the message that gets sent back to the LLM,
    # what gets rendered in the chat UI, what gets saved to a session JSON
    # file on disk, and what a user can later Export from the sidebar.
    # There is no legitimate reason for a raw bearer token / password /
    # access_token to persist past this point -- if the app needs the token
    # for later `call_api` calls, it already has it in
    # `st.session_state.api_bearer_token` via the dedicated login form,
    # independent of this redacted copy.
    #
    # Known limitation: this only covers TOOL RESULTS. If a user types a raw
    # password directly into the chat box (instead of using the sidebar
    # login form), that password ends up in a `role="user"` message and in
    # the model's tool_call arguments, neither of which passes through this
    # function -- the sidebar login form exists specifically so users don't
    # have to do that.
    redacted_result = redact_secrets(result)

    try:
        from state import log_audit

        log_audit(
            "TOOL_EXECUTION",
            {
                "tool_name": name,
                "tool_id": tool_id,
                "arguments": redact_secrets(args),
                "duration_s": round(duration, 3),
                "result": redacted_result,
            },
        )
    except Exception:
        pass

    llm_result = _truncate_for_llm(redacted_result)

    return {
        "role": "tool",
        "tool_call_id": tool_id,
        "content": json.dumps(llm_result, default=_json_default),
        "execution_time_s": duration,
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
