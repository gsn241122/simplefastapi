"""Streamlit `session_state` initialization for the chatbot.

Centralizing all `session_state` defaults here makes it easy to inspect and
tune the runtime behavior of the chatbot.
"""
from __future__ import annotations

import json
import os
import streamlit as st

from config import AUDIT_LOG_MAX_ENTRIES, MCP_CONFIG_PATH, SYSTEM_PROMPT
from history_manager import generate_session_id
from mcp_client import load_mcp_config

# NOTE: default_safe_mode / default_stream_response / default_temperature
# used to be re-declared here as a second copy of the constants in
# config.py. They are gone — `config.py` is now the single source of truth.
# Import from there if a default value is needed outside the sidebar.


TOOL_PREFS_FILE = os.path.join(os.path.dirname(__file__), 'tool_prefs.json')


def load_tool_prefs() -> set[str]:
    if not os.path.exists(TOOL_PREFS_FILE):
        return set()
    try:
        with open(TOOL_PREFS_FILE, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
            return set(prefs.get("disabled_tools", []))
    except Exception as e:
        st.toast(f"Error loading tool preferences: {e}", icon=":material/warning:")
        return set()


def save_tool_prefs(disabled_tools: set[str]) -> None:
    try:
        with open(TOOL_PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"disabled_tools": list(disabled_tools)}, f, indent=4)
    except Exception as e:
        st.toast(f"Error saving tool preferences: {e}", icon=":material/warning:")


def get_current_system_prompt() -> str:
    """Return the system prompt currently configured by the user.

    The sidebar's "System Prompt" text area is the single source of truth:
    whatever the user has typed there (possibly with leading/trailing spaces)
    is what we'll send to the LLM. Falls back to the built-in default from
    ``config.SYSTEM_PROMPT`` when the session_state value is missing or
    empty (e.g. first run, or the user cleared the text area).

    Both ``state.init_session_state`` and ``sidebar._reset_active_conversation``
    call this helper so the two paths can never drift apart again.
    """
    return st.session_state.get("system_prompt") or SYSTEM_PROMPT


def _set_default(key: str, value: object) -> None:
    """Set `st.session_state[key] = value` only if it isn't already set.

    Equivalent to `setdefault`, spelled out so it's greppable.
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
    _set_default("system_prompt", SYSTEM_PROMPT)
    _set_default("pending_tool_call", None)
    _set_default("pending_args", None)
    _set_default("pending_tool_queue", None)
    _set_default("resume_llm", False)
    _set_default("enable_debug_panel", False)
    _set_default("audit_logs", [])

    # ── Tool / MCP mapping ──────────────────────────────────────────────────
    _set_default("tool_to_server", {})
    _set_default("tool_to_real_name", {})
    _set_default("disabled_tools", load_tool_prefs())

    # ── Session / history ───────────────────────────────────────────────────
    _set_default("current_session_id", initial_session_id)
    _set_default("saved_session_select", initial_session_id)

    # ── Authentication ─────────────────────────────────────────────────────
    _set_default("api_bearer_token", os.getenv("API_BEARER_TOKEN", ""))

    # ── MCP configuration (loaded from disk once) ───────────────────────────
    if "mcp_config" not in st.session_state:
        st.session_state.mcp_config = load_mcp_config(MCP_CONFIG_PATH)

    # Theme selection (default: light; sidebar selector may override on first render)
    _set_default("current_theme", "light")

    # ── Seed the conversation with the system prompt ───────────────────────
    # Helper ensures we always read from the same single source of truth
    # (the sidebar text area) instead of duplicating the lookup logic.
    current_prompt = get_current_system_prompt()
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "system", "content": current_prompt})
    elif st.session_state.messages[0].get("role") == "system":
        # Keep messages[0] in sync with whatever the sidebar currently shows,
        # so live edits to the System Prompt take effect on the next LLM call.
        st.session_state.messages[0]["content"] = current_prompt
    else:
        # Saved session was loaded without a system message at the head.
        # Prepend one so the LLM always sees the configured instructions.
        st.session_state.messages.insert(0, {"role": "system", "content": current_prompt})


def log_audit(event_type: str, details: dict) -> None:
    """Record an audit/debug event if the debug panel is enabled.

    `details` is expected to already have secrets redacted by the caller
    (see tool_execution.run_tool_call using security.redact_secrets) —
    this function does not re-redact, so any new call site MUST redact
    before calling this.
    """
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
    if len(st.session_state.audit_logs) > AUDIT_LOG_MAX_ENTRIES:
        st.session_state.audit_logs.pop()
