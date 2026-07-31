"""Streamlit `session_state` initialization for the chatbot."""
from __future__ import annotations

import streamlit as st

from config import MCP_CONFIG_PATH, SYSTEM_PROMPT
from mcp_client import load_mcp_config


def init_session_state() -> None:
    """Set up every `session_state` key the app relies on, with safe defaults.

    Must be called once at the top of the script, before any other module
    reads from `st.session_state`.
    """
    defaults: dict[str, object] = {
        "messages": [],
        "pending_tool_call": None,
        "pending_args": None,
        "resume_llm": False,
        "tool_to_server": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if "mcp_config" not in st.session_state:
        st.session_state.mcp_config = load_mcp_config(MCP_CONFIG_PATH)

    if not st.session_state.messages:
        st.session_state.messages.append({"role": "system", "content": SYSTEM_PROMPT})