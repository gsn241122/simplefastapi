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
    DEFAULT_PROVIDER,
    DEFAULT_TEMPERATURE,
    MCP_CONFIG_PATH,
    PROVIDERS,
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

    provider: str
    base_url: str
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


def _on_provider_change() -> None:
    """Synchronize base_url, default_model, and api_key when the user selects a different LLM Provider."""
    prov = st.session_state.get("llm_provider", DEFAULT_PROVIDER)
    if prov in PROVIDERS:
        p_info = PROVIDERS[prov]
        st.session_state["llm_base_url"] = p_info["base_url"]
        st.session_state["llm_model"] = p_info["default_model"]
        st.session_state["llm_custom_model"] = ""
        st.session_state["llm_api_key"] = os.getenv(p_info["default_api_key_env"], "")


def _render_model_settings() -> tuple[str, str, str, str]:
    provider_names = list(PROVIDERS.keys())

    # Initialize state defaults on first run if missing
    if "llm_provider" not in st.session_state or st.session_state["llm_provider"] not in PROVIDERS:
        st.session_state["llm_provider"] = DEFAULT_PROVIDER
        p_info = PROVIDERS[DEFAULT_PROVIDER]
        st.session_state["llm_base_url"] = p_info["base_url"]
        st.session_state["llm_model"] = p_info["default_model"]
        st.session_state["llm_custom_model"] = ""
        st.session_state["llm_api_key"] = os.getenv(p_info["default_api_key_env"], "")

    selected_provider = st.selectbox(
        "LLM Provider",
        options=provider_names,
        key="llm_provider",
        on_change=_on_provider_change,
    )
    p_info = PROVIDERS[selected_provider]

    api_key = st.text_input(
        f"{selected_provider} API key",
        key="llm_api_key",
        type="password",
        help=p_info["api_key_help"],
    )

    models_list = p_info["models"]
    current_model = st.session_state.get("llm_model")
    if current_model not in models_list:
        st.session_state["llm_model"] = p_info["default_model"]

    model = st.selectbox(
        "Model",
        options=models_list,
        key="llm_model",
    )
    custom_model = st.text_input(
        "Custom model ID",
        key="llm_custom_model",
        placeholder="e.g. custom-model-id",
        label_visibility="collapsed",
        help="Override the model selector above with any model ID.",
    )
    effective_model = custom_model.strip() if custom_model.strip() else model

    custom_base_url = st.text_input(
        "Base URL",
        key="llm_base_url",
        help="API base URL for the selected provider. Override if using a custom proxy/gateway.",
    )

    return selected_provider, custom_base_url, api_key, effective_model


def _render_advanced_tuning() -> _Tuning:
    with st.expander("Advanced tuning", icon=":material/tune:"):
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

        st.subheader(":material/settings_ethernet: MCP connection", divider=False)
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
            "Safe mode keywords (comma-separated)",
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
    st.subheader(":material/hub: MCP servers")
    if not st.session_state.mcp_config:
        st.warning("mcp_servers.json not found or empty.", icon=":material/warning:")
        return
    for name in st.session_state.mcp_config:
        st.badge(name, icon=":material/electrical_services:", color="violet")


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
    st.subheader(":material/lock: API authentication")
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
        submitted = st.form_submit_button("Login via MCP", icon=":material/key:")

    if submitted:
        if not username or not password:
            st.error("Username and password are required!")
        else:
            try:
                _handle_login(login_path, username, password, connect_timeout, call_timeout)
            except Exception as exc:
                st.error(f"❌ Error calling MCP tool: {exc}")


def _render_mcp_tools_status(connect_timeout: float) -> None:
    if st.button("Refresh MCP tools", icon=":material/refresh:"):
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
        st.error(f"Could not reach MCP server:\n{st.session_state.mcp_error}", icon=":material/error:")
        return

    if st.session_state.get("server_errors"):
        st.warning(
            f"{len(st.session_state.server_errors)} server(s) failed to connect:",
            icon=":material/warning:",
        )
        for server_name, error in st.session_state.server_errors.items():
            with st.expander(server_name, icon=":material/cancel:"):
                st.code(error)

    tool_count = len(st.session_state.mcp_tools)
    st.badge(
        f"Connected — {tool_count} tool{'s' if tool_count != 1 else ''} available",
        icon=":material/check_circle:",
        color="green",
    )
    for tool in st.session_state.mcp_tools:
        server_name = st.session_state.tool_to_server.get(tool["function"]["name"], "?")
        st.caption(f":material/build: {tool['function']['name']} — {server_name}")


def _on_new_chat_click() -> None:
    """Callback: start a brand-new conversation session."""
    new_id = generate_session_id()
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.current_session_id = new_id
    st.session_state.saved_session_select = new_id
    st.session_state.pop("pending_tool_call", None)
    st.session_state.pop("pending_args", None)
    st.session_state.pop("pending_tool_queue", None)
    st.session_state.pop("resume_llm", None)


def _on_delete_session_click(target_id: str) -> None:
    """Callback: delete a saved session by ID."""
    delete_session(target_id)
    if st.session_state.get("current_session_id") == target_id:
        new_id = generate_session_id()
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.current_session_id = new_id
        st.session_state.saved_session_select = new_id
    else:
        st.session_state.saved_session_select = st.session_state.get("current_session_id")


def _on_clear_chat_click() -> None:
    """Callback: clear the active conversation and start a fresh session."""
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
    st.subheader(":material/history: Chat history")

    with st.container(horizontal=True):
        st.button(
            "New chat",
            icon=":material/add:",
            on_click=_on_new_chat_click,
        )

        if st.session_state.messages and len(st.session_state.messages) > 1:
            # Auto-save current session before export
            current_id = st.session_state.get("current_session_id", generate_session_id())
            title = get_default_session_title(st.session_state.messages)
            save_session(current_id, title, st.session_state.messages)

            chat_json = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
            st.download_button(
                label="Export",
                icon=":material/download:",
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
            session_labels[current_id] = "New conversation (active)"
        default_index = session_ids.index(current_id) if current_id in session_ids else 0

        st.selectbox(
            "Saved sessions",
            options=session_ids,
            index=default_index,
            format_func=lambda sid: session_labels.get(sid, sid),
            key="saved_session_select",
            on_change=_on_session_select_change,
        )

        selected_id = st.session_state.get("saved_session_select")
        if selected_id:
            st.button(
                "Delete session",
                icon=":material/delete:",
                on_click=_on_delete_session_click,
                args=(selected_id,),
            )


def _render_clear_conversation_button() -> None:
    st.button(
        "Clear active chat",
        icon=":material/cleaning_services:",
        on_click=_on_clear_chat_click,
    )


def render_sidebar() -> SidebarSettings:
    """Render the full sidebar and return the settings the main app needs."""
    with st.sidebar:
        # 1. Chat history management & clear
        _render_chat_history_management()
        _render_clear_conversation_button()
        st.divider()

        # 2. Model settings & advanced tuning
        st.header(":material/settings: Settings")
        provider, base_url, api_key, model = _render_model_settings()
        tuning = _render_advanced_tuning()
        st.divider()

        # 3. API authentication & bearer token
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

        # 4. Security & safety
        safe_mode = st.checkbox(
            ":material/shield: Safe mode (confirm dangerous actions)",
            value=True,
            help=(
                "Ask for explicit confirmation before running a DELETE, PUT, "
                "or PATCH method, or any tool whose name matches a keyword "
                "from the Safe Mode keyword list above."
            ),
        )
        stream_response = st.checkbox(
            ":material/bolt: Stream response (typewriter effect)",
            value=True,
            help="Stream model response tokens in real-time as they are generated for faster response times.",
        )
        st.divider()

        # 5. MCP servers & tools status
        _render_mcp_server_list()
        _render_mcp_tools_status(tuning.connect_timeout)

    return SidebarSettings(
        provider=provider,
        base_url=base_url,
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
