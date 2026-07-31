"""Sidebar UI: model settings, MCP server status, login form, and Safe Mode."""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass

import streamlit as st

from config import AVAILABLE_MODELS, DEFAULT_MODEL
from mcp_client import call_mcp_tool_by_name, fetch_all_mcp_tools


@dataclass
class SidebarSettings:
    """Values collected from the sidebar that the main app needs."""

    api_key: str
    model: str
    safe_mode: bool
    bearer_token: str


def _render_model_settings() -> tuple[str, str]:
    api_key = st.text_input(
        "Gemini API key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Get one at https://aistudio.google.com/apikey",
    )
    model = st.selectbox(
        "Gemini model",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0,
    )
    custom_model = st.text_input("...or use a custom model id", value="")
    if custom_model.strip():
        model = custom_model.strip()
    return api_key, model


def _render_mcp_server_list() -> None:
    st.subheader("🔌 MCP Servers")
    if not st.session_state.mcp_config:
        st.warning("mcp_servers.json not found or empty.")
        return
    st.success(f"Loaded {len(st.session_state.mcp_config)} server(s):")
    for name in st.session_state.mcp_config:
        st.caption(f"• {name}")


def _ensure_tool_mapping_loaded() -> bool:
    """Make sure `tool_to_server` is populated before the login form calls
    `call_api`. Returns False (and shows an error) on failure.
    """
    if st.session_state.tool_to_server:
        return True
    try:
        _, mapping, _ = asyncio.run(fetch_all_mcp_tools(st.session_state.mcp_config))
        st.session_state.tool_to_server = mapping
        return True
    except Exception as exc:
        st.error(f"Failed to load tool mapping: {exc}")
        return False


def _extract_login_error(body: object) -> str:
    if isinstance(body, dict):
        return body.get("message") or body.get("detail") or body.get("error") or str(body)
    if isinstance(body, str):
        return body[:300]
    return "Unknown error"


def _handle_login(login_path: str, username: str, password: str) -> None:
    if not _ensure_tool_mapping_loaded():
        st.stop()

    login_args = {
        "method": "POST",
        "path": login_path,
        "data": {"username": username, "password": password},
    }
    with st.spinner("Logging in via MCP server..."):
        result = asyncio.run(
            call_mcp_tool_by_name(
                st.session_state.mcp_config,
                st.session_state.tool_to_server,
                "call_api",
                login_args,
            )
        )

    body = result.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass

    if isinstance(body, dict) and body.get("success") and isinstance(body.get("data"), dict):
        token = body["data"].get("access_token")
        if token:
            st.session_state.api_bearer_token = token
            st.success("✅ Login successful! Token has been saved.")
        else:
            st.error("❌ Login succeeded, but no access_token was found in the response.")
        return

    error_msg = _extract_login_error(body)
    status_code = result.get("status_code") or result.get("status", "?")
    st.error(f"❌ Login failed (Status: {status_code}).")
    st.caption(f"Details: {error_msg}")


def _render_login_form() -> None:
    st.subheader("🔐 API Authentication")
    if "api_bearer_token" not in st.session_state:
        st.session_state.api_bearer_token = os.getenv("API_BEARER_TOKEN", "")

    login_path = st.text_input(
        "Login endpoint path",
        value=os.getenv("LOGIN_PATH", "/auth/login"),
        help="Login endpoint path, e.g. /auth/login, /token",
    )
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("🔑 Login via MCP")

    if submitted:
        if not username or not password:
            st.error("Username and password are required!")
        else:
            try:
                _handle_login(login_path, username, password)
            except Exception as exc:
                st.error(f"❌ Error calling MCP tool: {exc}")


def _render_mcp_tools_status() -> None:
    if st.button("🔄 Refresh MCP tools"):
        st.session_state.pop("mcp_tools", None)
        st.session_state.pop("tool_to_server", None)
        st.session_state.pop("server_errors", None)
        st.rerun()

    if "mcp_tools" not in st.session_state:
        try:
            tools, mapping, errors = asyncio.run(fetch_all_mcp_tools(st.session_state.mcp_config))
            st.session_state.mcp_tools = tools
            st.session_state.tool_to_server = mapping
            st.session_state.server_errors = errors
            st.session_state.mcp_error = None
        except Exception as exc:
            st.session_state.mcp_tools = []
            st.session_state.mcp_error = str(exc)

    if st.session_state.get("mcp_error"):
        st.error(f"Could not reach MCP server:\n{st.session_state.mcp_error}")
        return

    if st.session_state.get("server_errors"):
        st.warning(f"⚠️ {len(st.session_state.server_errors)} server(s) failed to connect:")
        for server_name, error in st.session_state.server_errors.items():
            with st.expander(f"🔴 {server_name}"):
                st.code(error)

    st.success(f"Connected — {len(st.session_state.mcp_tools)} tool(s) available")
    for tool in st.session_state.mcp_tools:
        server_name = st.session_state.tool_to_server.get(tool["function"]["name"], "?")
        st.caption(f"• {tool['function']['name']} ({server_name})")


def _render_clear_conversation_button() -> None:
    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.pop("pending_tool_call", None)
        st.session_state.pop("pending_args", None)
        st.session_state.pop("resume_llm", None)
        st.rerun()


def render_sidebar() -> SidebarSettings:
    """Render the full sidebar and return the settings the main app needs."""
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key, model = _render_model_settings()
        st.divider()

        _render_mcp_server_list()
        st.divider()

        _render_login_form()
        st.divider()

        bearer_token = st.text_input(
            "Bearer token for the target API",
            key="api_bearer_token",
            type="password",
            help=(
                "This token is automatically added as an "
                "'Authorization: Bearer <token>' header every time the "
                "`call_api` tool is called. Filled in automatically after a "
                "successful login."
            ),
        )
        st.divider()

        safe_mode = st.checkbox(
            "🛡️ Safe Mode (confirm dangerous actions)",
            value=True,
            help=(
                "Ask for explicit confirmation before running a DELETE, PUT, "
                "or PATCH method, or any tool whose name contains 'delete', "
                "'write_file', or 'execute'."
            ),
        )
        st.divider()

        _render_mcp_tools_status()
        st.divider()

        _render_clear_conversation_button()

    return SidebarSettings(api_key=api_key, model=model, safe_mode=safe_mode, bearer_token=bearer_token)