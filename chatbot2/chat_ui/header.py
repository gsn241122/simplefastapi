"""Header / status bar for the MCP chatbot.

Encapsulates the title + status-badge row that sits between the sidebar
and the chat area: page title, model badge, tool counters, safe-mode
indicator, streaming badge, and per-server status chips.

Lives in its own module so ``app.py`` stays a pure composition root
and so the header can be unit-tested or reused (e.g. on a help page)
without dragging in the rest of the chat UI.
"""
from __future__ import annotations

import streamlit as st


def render_header(settings) -> None:
    """Render the title and status-badge grid above the chat divider.

    Reads MCP state from ``st.session_state`` (``mcp_config``,
    ``server_errors``, ``mcp_tools``, ``disabled_tools``) and the user's
    settings from the sidebar (``settings.model``, ``settings.safe_mode``,
    ``settings.stream_response``).

    Returns ``None``; everything is rendered through ``st.*`` calls.
    """
    mcp_cfg = st.session_state.get("mcp_config") or {}
    all_servers: list[str] = (
        list(mcp_cfg.keys()) if isinstance(mcp_cfg, dict) else []
    )
    server_errors: dict = st.session_state.get("server_errors") or {}
    mcp_tools = st.session_state.get("mcp_tools")

    active_server_count: int = max(0, len(all_servers) - len(server_errors))
    disabled_tools = st.session_state.get("disabled_tools") or set()
    total_tool_count: int = len(mcp_tools) if mcp_tools is not None else 0
    active_tool_count: int = len(
        [
            t
            for t in (mcp_tools or [])
            if t.get("function", {}).get("name") not in disabled_tools
        ]
    )

    cols = st.columns([2, 3])
    col_title, col_status = cols

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
                    f"{active_tool_count}/{total_tool_count} Tools",
                    icon=":material/build:",
                    color="violet",
                )
                st.badge(
                    "Safe Mode: ON" if settings.safe_mode else "Safe Mode: OFF",
                    icon=":material/shield:"
                    if settings.safe_mode
                    else ":material/gpp_maybe:",
                    color="green" if settings.safe_mode else "red",
                )
                if settings.stream_response:
                    st.badge("Streaming", icon=":material/bolt:", color="blue")

            if all_servers:
                server_chips = [
                    f":material/check_circle: `{s}`"
                    if s not in server_errors
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
