"""Streamlit chatbot that talks to an OpenAI-compatible LLM endpoint and can
call tools exposed by multiple MCP servers configured in mcp_servers.json.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    logger.warning("python-dotenv not found, skipping .env loading.")
except Exception as e:
    logger.error(f"Error loading .env file: {e}")

from chat_ui import handle_chat_input, render_chat_history, render_pending_confirmation
from sidebar import render_sidebar
from state import init_session_state
from themes import apply_theme_css, get_theme

# ──────────────────────────────────────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCP Chatbot",
    page_icon=":material/smart_toy:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "MCP Chatbot",
        "Get Help": "https://modelcontextprotocol.io/",
        "Report a bug": None,
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────
init_session_state()
settings = render_sidebar()


@st.cache_data
def load_css(file_name: str) -> str:
    with open(file_name) as f:
        return f"<style>{f.read()}</style>"


# Load the base layout CSS (path corrected: was "chatbot/style.css", which 404'd)
try:
    st.markdown(load_css("chatbot2/style.css"), unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning("style.css not found at app startup; using default Streamlit styling.")

# Apply the active theme (driven by the sidebar theme selector).
# Done after the base layout CSS so the theme variables can override it.
_active_theme_name = st.session_state.get("current_theme", "light")
_active_theme_css = apply_theme_css(get_theme(_active_theme_name))
st.markdown(_active_theme_css, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Early-exit guard: ensure MCP state is initialised
# ──────────────────────────────────────────────────────────────────────────────
if "mcp_config" not in st.session_state or st.session_state.mcp_config is None:
    with st.container(border=True):
        st.warning(
            ":material/warning: **MCP config not loaded.** "
            "Check your `mcp_servers.json` configuration, then refresh the page.",
            icon=":material/error:",
        )
    render_chat_history()
    handle_chat_input(settings)
    st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────
mcp_cfg = st.session_state.get("mcp_config") or {}
all_servers: list[str] = list(mcp_cfg.keys()) if isinstance(mcp_cfg, dict) else []
server_errors: dict = st.session_state.get("server_errors") or {}
mcp_tools = st.session_state.get("mcp_tools")

active_server_count: int = max(0, len(all_servers) - len(server_errors))
disabled_tools = st.session_state.get("disabled_tools") or set()
total_tool_count: int = len(mcp_tools) if mcp_tools is not None else 0
active_tool_count: int = len([t for t in (mcp_tools or []) if t.get("function", {}).get("name") not in disabled_tools])

cols = st.columns([2, 3])
col_title, col_status = cols[0], cols[1]

with col_title:
    st.title(":material/smart_toy: MCP Chatbot")
    st.caption(":material/hub: Powered by MCP Tool Servers")

with col_status:
    with st.container(border=True):
        with st.container(horizontal=True):
            st.badge(f"{settings.model}", icon=":material/model_training:", color="blue")
            st.badge(f"{active_tool_count}/{total_tool_count} Tools", icon=":material/build:", color="violet")
            st.badge(
                "Safe Mode: ON" if settings.safe_mode else "Safe Mode: OFF",
                icon=":material/shield:" if settings.safe_mode else ":material/gpp_maybe:",
                color="green" if settings.safe_mode else "red",
            )
            if settings.stream_response:
                st.badge("Streaming", icon=":material/bolt:", color="blue")

        if all_servers:
            server_chips = [
                f":material/check_circle: `{s}`" if s not in server_errors
                else f":material/cancel: `{s}` ({server_errors[s]})"
                for s in all_servers
            ]
            st.caption(
                f"**:material/dns: MCP Servers ({active_server_count}/{len(all_servers)}):** "
                + " • ".join(server_chips)
            )
        else:
            st.caption(":material/dns: **MCP Servers:** _none configured_")

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("💬 Chat Area")
render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)
