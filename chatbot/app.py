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

st.set_page_config(page_title="FastAPI MCP Chatbot (Gemini)", page_icon="🤖")

init_session_state()
settings = render_sidebar()

st.title("🤖 FastAPI MCP Chatbot")
server_names = ", ".join(st.session_state.mcp_config.keys()) if st.session_state.mcp_config else "None"
st.caption(f"Model: `{settings.model}` · MCP Servers: `{server_names}`")

render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)