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
from chat_ui.header import render_header
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
    initial_sidebar_state="auto",
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
_active_theme_name = st.session_state.get("current_theme", "dark")
_active_theme_css = apply_theme_css(get_theme(_active_theme_name))
st.markdown(_active_theme_css, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Force Sidebar Open/Closed State helper for Mobile / Responsive viewports
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <script>
    // Ensure localStorage reflects collapsed state properly on mobile if missing
    try {
        const key = 'stSidebarCollapsed';
        if (window.innerWidth <= 768 && !localStorage.getItem(key)) {
            localStorage.setItem(key, 'true');
        }
    } catch (e) {}
    </script>
    """,
    unsafe_allow_html=True,
)

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
render_header(settings)

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────────────
st.subheader("💬 Chat Area")
render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)
