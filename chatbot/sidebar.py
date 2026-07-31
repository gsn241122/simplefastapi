"""Sidebar UI: model settings, advanced tuning, MCP server status, login
form, and Safe Mode.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from dataclasses import dataclass

import streamlit as st

from config import (
    AVAILABLE_MODELS,
    DANGEROUS_NAME_KEYWORDS,
    DEFAULT_CALL_TIMEOUT_SECONDS,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_TOOL_ROUNDS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    MCP_CONFIG_PATH,
    SYSTEM_PROMPT,
)
from history_manager import (
    delete_session,
    generate_session_id,
    get_default_session_title,
    list_saved_sessions,
    load_session,
    save_session,
)
from mcp_client import call_mcp_tool_by_name, fetch_all_mcp_tools, load_mcp_config


@dataclass
class SidebarSettings:
    """Values collected from the sidebar that the main app needs."""

    api_key: str
    model: str
    safe_mode: bool
    stream_response: bool
    bearer_token: str
    temperature: float
    max_tokens: int | None
    max_tool_rounds: int
    connect_timeout: float
    call_timeout: float
    dangerous_keywords: tuple[str, ...]


@dataclass
class _Tuning:
    temperature: float
    max_tokens: int | None
    max_tool_rounds: int
    connect_timeout: float
    call_timeout: float
    dangerous_keywords: tuple[str, ...]


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


def _render_advanced_tuning() -> _Tuning:
    with st.expander("🎛️ Advanced tuning"):
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=DEFAULT_TEMPERATURE,
            step=0.1,
            help="Higher = more creative/random, lower = more focused/deterministic.",
        )

        limit_tokens = st.checkbox("Limit max output tokens", value=False)
        max_tokens: int | None = None
        if limit_tokens:
            max_tokens = st.number_input(
                "Max output tokens",
                min_value=64,
                max_value=32000,
                value=DEFAULT_MAX_OUTPUT_TOKENS,
                step=64,
            )

        max_tool_rounds = st.slider(
            "Max tool-call rounds",
            min_value=1,
            max_value=20,
            value=DEFAULT_MAX_TOOL_ROUNDS,
            help="How many back-and-forth tool calls the assistant may make before giving up.",
        )

        st.caption("MCP connection")
        connect_timeout = st.number_input(
            "Connect timeout (s)",
            min_value=1.0,
            max_value=120.0,
            value=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            step=1.0,
            help="Max time to wait when opening a new MCP server connection (e.g. spawning a stdio subprocess).",
        )
        call_timeout = st.number_input(
            "Tool-call timeout (s)",
            min_value=1.0,
            max_value=300.0,
            value=DEFAULT_CALL_TIMEOUT_SECONDS,
            step=5.0,
            help="Max time to wait for a single tool call to finish.",
        )

        keywords_raw = st.text_input(
            "Safe Mode keywords (comma-separated)",
            value=", ".join(DANGEROUS_NAME_KEYWORDS),
            help="Tool names containing any of these words require confirmation when Safe Mode is on.",
        )
        dangerous_keywords = tuple(k.strip().lower() for k in keywords_raw.split(",") if k.strip())

    return _Tuning(
        temperature=temperature,
        max_tokens=int(max_tokens) if max_tokens else None,
        max_tool_rounds=max_tool_rounds,
        connect_timeout=connect_timeout,
        call_timeout=call_timeout,
        dangerous_keywords=dangerous_keywords or DANGEROUS_NAME_KEYWORDS,
    )


def _render_mcp_server_list() -> None:
    st.subheader("🔌 MCP Servers")
    if not st.session_state.mcp_config:
        st.warning("mcp_servers.json not found or empty.")
        return
    st.success(f"Loaded {len(st.session_state.mcp_config)} server(s):")
    for name in st.session_state.mcp_config:
        st.caption(f"• {name}")


def _build_saved_session_selection(saved_sessions: list[dict]) -> tuple[list[str], dict[str, str]]:
    session_ids: list[str] = []
    session_labels: dict[str, str] = {}
    for s in saved_sessions:
        created_at = s.get("created_at", "")
        try:
            created_at_str = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            created_at_str = created_at.replace("T", " ") if created_at else s["session_id"]

        label = f"{s['title']} ({created_at_str})"
        if label in session_labels.values():
            label = f"{label} [{s['session_id']}]"

        session_ids.append(s["session_id"])
        session_labels[s["session_id"]] = label
    return session_ids, session_labels


def _ensure_tool_mapping_loaded(connect_timeout: float) -> bool:
    """Make sure `tool_to_server` is populated before the login form calls
    `call_api`. Returns False (and shows an error) on failure.
    """
    if st.session_state.tool_to_server:
        return True
    try:
        tools, mapping, real_mapping, _ = fetch_all_mcp_tools(st.session_state.mcp_config, connect_timeout=connect_timeout)
        st.session_state.mcp_tools = tools
        st.session_state.tool_to_server = mapping
        st.session_state.tool_to_real_name = real_mapping
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


def _handle_login(login_path: str, username: str, password: str, connect_timeout: float, call_timeout: float) -> None:
    if not _ensure_tool_mapping_loaded(connect_timeout):
        st.stop()

    login_args = {
        "method": "POST",
        "path": login_path,
        "data": {"username": username, "password": password},
    }
    with st.spinner("Logging in via MCP server..."):
        result = call_mcp_tool_by_name(
            st.session_state.mcp_config,
            st.session_state.tool_to_server,
            "call_api",
            login_args,
            tool_to_real_name=st.session_state.get("tool_to_real_name"),
            connect_timeout=connect_timeout,
            call_timeout=call_timeout,
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


def _render_login_form(connect_timeout: float, call_timeout: float) -> None:
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
                _handle_login(login_path, username, password, connect_timeout, call_timeout)
            except Exception as exc:
                st.error(f"❌ Error calling MCP tool: {exc}")


def _render_mcp_tools_status(connect_timeout: float) -> None:
    if st.button("🔄 Refresh MCP tools"):
        st.session_state.mcp_config = load_mcp_config(MCP_CONFIG_PATH)
        st.session_state.pop("mcp_tools", None)
        st.session_state.pop("tool_to_server", None)
        st.session_state.pop("tool_to_real_name", None)
        st.session_state.pop("server_errors", None)
        st.rerun()

    if "mcp_tools" not in st.session_state:
        try:
            tools, mapping, real_mapping, errors = fetch_all_mcp_tools(st.session_state.mcp_config, connect_timeout=connect_timeout)
            st.session_state.mcp_tools = tools
            st.session_state.tool_to_server = mapping
            st.session_state.tool_to_real_name = real_mapping
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


def _on_new_chat_click() -> None:
    """Callback for ➕ Chat Baru button."""
    new_id = generate_session_id()
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.current_session_id = new_id
    st.session_state.saved_session_select = new_id
    st.session_state.pop("pending_tool_call", None)
    st.session_state.pop("pending_args", None)
    st.session_state.pop("pending_tool_queue", None)
    st.session_state.pop("resume_llm", None)


def _on_delete_session_click(target_id: str) -> None:
    """Callback for 🗑️ Hapus Sesi button."""
    delete_session(target_id)
    if st.session_state.get("current_session_id") == target_id:
        new_id = generate_session_id()
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.current_session_id = new_id
        st.session_state.saved_session_select = new_id
    else:
        st.session_state.saved_session_select = st.session_state.get("current_session_id")


def _on_clear_chat_click() -> None:
    """Callback for 🧹 Bersihkan Chat Aktif button."""
    new_id = generate_session_id()
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.current_session_id = new_id
    st.session_state.saved_session_select = new_id
    st.session_state.pop("pending_tool_call", None)
    st.session_state.pop("pending_args", None)
    st.session_state.pop("pending_tool_queue", None)
    st.session_state.pop("resume_llm", None)


def _on_session_select_change() -> None:
    """Auto-load chosen session into session_state as soon as user changes dropdown."""
    selected_id = st.session_state.get("saved_session_select")
    if selected_id:
        loaded_msgs = load_session(selected_id)
        if loaded_msgs:
            st.session_state.messages = loaded_msgs
        else:
            st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.current_session_id = selected_id
        st.session_state.pop("pending_tool_call", None)
        st.session_state.pop("pending_args", None)
        st.session_state.pop("pending_tool_queue", None)
        st.session_state.pop("resume_llm", None)


def _render_chat_history_management() -> None:
    st.subheader("📁 Riwayat Percakapan")

    col1, col2 = st.columns(2)
    with col1:
        st.button("➕ Chat Baru", on_click=_on_new_chat_click)

    with col2:
        if st.session_state.messages and len(st.session_state.messages) > 1:
            # Auto save current session before export or action
            current_id = st.session_state.get("current_session_id", generate_session_id())
            title = get_default_session_title(st.session_state.messages)
            save_session(current_id, title, st.session_state.messages)

            chat_json = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 Ekspor",
                data=chat_json,
                file_name=f"{current_id}.json",
                mime="application/json",
            )

    saved_sessions = list_saved_sessions()
    if saved_sessions:
        session_ids, session_labels = _build_saved_session_selection(saved_sessions)
        current_id = st.session_state.get("current_session_id")
        if current_id and current_id not in session_ids:
            session_ids.insert(0, current_id)
            session_labels[current_id] = "➕ Percakapan Baru (Aktif)"
        default_index = session_ids.index(current_id) if current_id in session_ids else 0

        st.selectbox(
            "Pilih Sesi Tersimpan",
            options=session_ids,
            index=default_index,
            format_func=lambda sid: session_labels.get(sid, sid),
            key="saved_session_select",
            on_change=_on_session_select_change,
        )

        selected_id = st.session_state.get("saved_session_select")
        if selected_id:
            st.button("🗑️ Hapus Sesi", on_click=_on_delete_session_click, args=(selected_id,))


def _render_clear_conversation_button() -> None:
    st.button("🧹 Bersihkan Chat Aktif", on_click=_on_clear_chat_click)


def render_sidebar() -> SidebarSettings:
    """Render the full sidebar and return the settings the main app needs."""
    with st.sidebar:
        # 1. Chat History Management & Clear
        _render_chat_history_management()
        _render_clear_conversation_button()
        st.divider()

        # 2. Model Settings & Advanced Tuning
        st.header("⚙️ Settings")
        api_key, model = _render_model_settings()
        tuning = _render_advanced_tuning()
        st.divider()

        # 3. API Authentication & Bearer Token
        _render_login_form(tuning.connect_timeout, tuning.call_timeout)
        
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

        # 4. Security & Safety
        safe_mode = st.checkbox(
            "🛡️ Safe Mode (confirm dangerous actions)",
            value=True,
            help=(
                "Ask for explicit confirmation before running a DELETE, PUT, "
                "or PATCH method, or any tool whose name matches a keyword "
                "from the Safe Mode keyword list above."
            ),
        )
        stream_response = st.checkbox(
            "⚡ Stream response (typewriter effect)",
            value=True,
            help="Stream model response tokens in real-time as they are generated for faster response times.",
        )
        st.divider()

        # 5. MCP Servers & Tools Status
        _render_mcp_server_list()
        _render_mcp_tools_status(tuning.connect_timeout)

    return SidebarSettings(
        api_key=api_key,
        model=model,
        safe_mode=safe_mode,
        stream_response=stream_response,
        bearer_token=bearer_token,
        temperature=tuning.temperature,
        max_tokens=tuning.max_tokens,
        max_tool_rounds=tuning.max_tool_rounds,
        connect_timeout=tuning.connect_timeout,
        call_timeout=tuning.call_timeout,
        dangerous_keywords=tuning.dangerous_keywords,
    )
