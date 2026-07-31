"""Streamlit chatbot that talks to Gemini (through the OpenAI-compatible
endpoint) and can call tools exposed by multiple MCP servers configured in
mcp_servers.json.

Supports: FastAPI wrapper, filesystem, bash, git, and any other MCP servers.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from chat_ui import handle_chat_input, render_chat_history, render_pending_confirmation
from sidebar import render_sidebar
from state import init_session_state

st.set_page_config(
    page_title="FastAPI MCP Chatbot",
    page_icon=":material/smart_toy:",
    layout="wide",
)

init_session_state()
settings = render_sidebar()

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_badges = st.columns([3, 2], vertical_alignment="bottom")

with col_title:
    st.title(":material/smart_toy: FastAPI MCP chatbot")

with col_badges:
    mcp_cfg = st.session_state.get("mcp_config")
    server_names = list(mcp_cfg.keys()) if isinstance(mcp_cfg, dict) and mcp_cfg else []
    server_count = len(server_names)
    server_label = ", ".join(server_names) if server_names else "none"

    with st.container(horizontal=True):
        st.badge(
            f"Model: {settings.model}",
            icon=":material/model_training:",
            color="blue",
        )
        st.badge(
            f"{server_count} MCP server{'s' if server_count != 1 else ''} active",
            icon=":material/check_circle:" if server_count else ":material/warning:",
            color="green" if server_count else "orange",
        )

    if server_names:
        st.caption(f":material/hub: {server_label}")

st.divider()

# ── Chat ──────────────────────────────────────────────────────────────────────
render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)