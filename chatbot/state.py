"""Streamlit `session_state` initialization for the chatbot.

Centralizing all `session_state` defaults here makes it easy to inspect and
tune the runtime behavior of the chatbot (e.g. default safe mode, default
stream behavior, default temperature, etc.).
"""
from __future__ import annotations

import streamlit as st

from config import MCP_CONFIG_PATH, SYSTEM_PROMPT
from history_manager import generate_session_id
from mcp_client import load_mcp_config


# Default values that mirror the sidebar defaults. Kept here so the rest of
# the app can rely on them without importing the sidebar module.
DEFAULT_SAFE_MODE: bool = True
DEFAULT_STREAM_RESPONSE: bool = True
DEFAULT_TEMPERATURE: float = 0.7


def _set_default(key: str, value: object) -> None:
    """Set `st.session_state[key] = value` only if it isn't already set.

    This is equivalent to `setdefault`, but spelled out so it's greppable
    and easy to extend with logging / telemetry later.
    """
    if key not in st.session_state:
        st.session_state[key] = value


def init_session_state() -> None:
    """Set up every `session_state` key the app relies on, with safe defaults.

    Must be called once at the top of the script, before any other module
    reads from `st.session_state`.
    """
    initial_session_id = generate_session_id()

    # ── Chat-related state ───────────────────────────────────────────────────
    _set_default("messages", [])
    _set_default("system_prompt", SYSTEM_PROMPT)  # tuned: custom system prompt state
    _set_default("pending_tool_call", None)
    _set_default("pending_args", None)
    _set_default("pending_tool_queue", None)
    _set_default("resume_llm", False)
    _set_default("enable_debug_panel", False)
    _set_default("audit_logs", [])

    # ── Tool / MCP mapping ──────────────────────────────────────────────────
    _set_default("tool_to_server", {})
    _set_default("tool_to_real_name", {})

    # ── Session / history ───────────────────────────────────────────────────
    _set_default("current_session_id", initial_session_id)
    _set_default("saved_session_select", initial_session_id)

    # ── Authentication ─────────────────────────────────────────────────────
    import os  # local import to avoid circular import at module load
    _set_default("api_bearer_token", os.getenv("API_BEARER_TOKEN", ""))

    # ── MCP configuration (loaded from disk once) ───────────────────────────
    if "mcp_config" not in st.session_state:
        st.session_state.mcp_config = load_mcp_config(MCP_CONFIG_PATH)

    # ── Seed the conversation with the system prompt ───────────────────────
    current_prompt = st.session_state.get("system_prompt", SYSTEM_PROMPT)
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "system", "content": current_prompt})
    elif st.session_state.messages[0].get("role") == "system":
        # Keep system prompt in sync if updated
        st.session_state.messages[0]["content"] = current_prompt


def log_audit(event_type: str, details: dict) -> None:
    """Record an audit/debug event if the debug panel is enabled."""
    if not st.session_state.get("enable_debug_panel", False):
        return

    if "audit_logs" not in st.session_state:
        st.session_state.audit_logs = []

    from datetime import datetime
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": event_type,
        "data": details,
    }
    st.session_state.audit_logs.insert(0, entry)
    if len(st.session_state.audit_logs) > 100:
        st.session_state.audit_logs.pop()

