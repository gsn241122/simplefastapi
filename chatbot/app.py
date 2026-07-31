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
    page_title="FastAPI MCP Chatbot (Gemini)",
    page_icon="🤖",
    layout="wide",
)

# Custom CSS Polish for Streamlit UI
st.markdown(
    """
    <style>
    /* Sleek container styling */
    .stAppViewContainer {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    /* Modern badge styling */
    .mcp-badge-active {
        background-color: rgba(46, 204, 113, 0.15);
        color: #2ecc71;
        border: 1px solid rgba(46, 204, 113, 0.4);
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .mcp-badge-model {
        background-color: rgba(52, 152, 219, 0.15);
        color: #3498db;
        border: 1px solid rgba(52, 152, 219, 0.4);
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        margin-right: 8px;
    }
    /* Code block container tweaks */
    div[data-testid="stCodeBlock"] {
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_session_state()
settings = render_sidebar()

st.title("🤖 FastAPI MCP Chatbot")
mcp_cfg = st.session_state.get("mcp_config")
server_names = list(mcp_cfg.keys()) if isinstance(mcp_cfg, dict) and mcp_cfg else []
server_count = len(server_names)
server_label = ", ".join(server_names) if server_names else "None"

st.markdown(
    f"""
    <div style="margin-bottom: 20px;">
        <span class="mcp-badge-model">⚡ Model: {settings.model}</span>
        <span class="mcp-badge-active">🟢 {server_count} MCP Server Active ({server_label})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)