"""Streamlit chatbot that talks to Gemini (through the OpenAI-compatible
endpoint) and can call tools exposed by multiple MCP servers configured in
mcp_servers.json.

Supports: FastAPI wrapper, filesystem, bash, git, and any other MCP servers.

Run:
    streamlit run app.py
"""
from __future__ import annotations

import subprocess
import streamlit as st

import logging

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

# ──────────────────────────────────────────────────────────────────────────────
# Page Config (tuned: added initial_sidebar_state + menu_items)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCP Chatbot",
    page_icon=":material/smart_toy:",
    layout="wide",
    initial_sidebar_state="expanded",  # tuned: auto → expanded (better discoverability)
    menu_items={
        "About": "MCP Chatbot",
        "Get Help": "https://modelcontextprotocol.io/",
        "Report a bug": None,  # tuned: hide Report a bug menu
    },
)

# ──────────────────────────────────────────────────────────────────────────────
# Init
# ──────────────────────────────────────────────────────────────────────────────
init_session_state()
settings = render_sidebar()

@st.cache_data
def load_css(file_name: str):
    with open(file_name) as f:
        return f"<style>{f.read()}</style>"

# ──────────────────────────────────────────────────────────────────────────────
# Custom Styling (tuned: full padding control + hide Streamlit chrome)
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(load_css("chatbot/style.css"), unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Early-exit guard: ensure MCP state is initialised
# ──────────────────────────────────────────────────────────────────────────────
if "mcp_config" not in st.session_state or st.session_state.mcp_config is None:
    with st.container(border=True):
        st.warning(
            ":material/warning: **MCP config belum dimuat.** "
            "Cek konfigurasi `mcp_servers.json` lalu refresh halaman.",
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
tool_count: int = len(mcp_tools) if mcp_tools is not None else 0

# tuned: 2:1 ratio untuk memberi lebih ruang pada status panel
cols = st.columns([2, 1])
col_title, col_status = cols[0], cols[1]

with col_title:
    st.title(":material/smart_toy: MCP Chatbot")
    st.caption(":material/hub: Powered by MCP Tool Servers")

with col_status:
    with st.container(border=True):
        with st.container(horizontal=True):
            st.badge(
                f"{settings.model}",
                icon=":material/model_training:",
                color="blue",
            )
            st.badge(
                f"{tool_count} Tools",
                icon=":material/build:",
                color="violet",
            )
            st.badge(
                "Safe Mode: ON" if settings.safe_mode else "Safe Mode: OFF",
                icon=":material/shield:" if settings.safe_mode else ":material/gpp_maybe:",
                color="green" if settings.safe_mode else "red",
            )
            if settings.stream_response:
                st.badge(
                    "Streaming",
                    icon=":material/bolt:",
                    color="blue",
                )

        if all_servers:
            server_chips = [
                f":material/check_circle: `{s}`" if s not in server_errors
                else f":material/cancel: `{s}` ({server_errors[s]})"
                for s in all_servers
            ]
            st.caption(
                f"**:material/dns: MCP Servers "
                f"({active_server_count}/{len(all_servers)}):** "
                + " • ".join(server_chips)
            )
        else:
            st.caption(":material/dns: **MCP Servers:** _none configured_")

st.divider()

# ──────────────────────────────────────────────────────────────────────────────
# Chat
# ──────────────────────────────────────────────────────────────────────────────
# Buat layout 2 kolom di area utama
st.subheader("💬 Chat Area")
render_chat_history()
render_pending_confirmation(settings)
handle_chat_input(settings)
# col_chat, col_right_bar = st.columns([7, 3])

# with col_chat:
#     st.subheader("💬 Chat Area")
#     render_chat_history()
#     render_pending_confirmation(settings)
#     handle_chat_input(settings)

# with col_right_bar:
#     with st.container(border=True):
#         st.subheader("📊 Right Panel / Inspector")
#         st.caption("Panel informasi tambahan atau Live Debug Log.")

#         # --- Git Status ---
#         st.markdown("### 🗂️ Git Status")
#         try:
#             result = subprocess.run(
#                 ["git", "status"],
#                 capture_output=True,
#                 text=True,
#                 cwd="/home/dell/Desktop/workspace/simplefastapi"
#             )
#             if result.returncode == 0:
#                 st.code(result.stdout, language="text")
#             else:
#                 st.error(result.stderr or "Gagal menjalankan git status.")
#         except Exception as e:
#             st.error(f"Error: {e}")
#         # ------------------

#         # Contoh isi Panel Kanan (misal: Audit Log)
#         logs = st.session_state.get("audit_logs", [])
#         if st.button("Clear Logs", key="right_clear_logs"):
#             st.session_state.audit_logs = []
#             st.rerun()

#         for log in logs[:10]:
#             with st.expander(f"[{log['type']}] {log['timestamp']}", expanded=False):
#                 st.json(log['data'])