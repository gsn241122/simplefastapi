"""Sidebar UI: model settings, advanced tuning, MCP server status, login
form, and Safe Mode.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

import streamlit as st

from config import (
    DANGEROUS_NAME_KEYWORDS,
    DEFAULT_CALL_TIMEOUT_SECONDS,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_TOOL_ROUNDS,
    DEFAULT_REASONING_BUDGET_TOKENS,
    DEFAULT_REASONING_ENABLED,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_PROVIDER,
    DEFAULT_TEMPERATURE,
    MCP_CONFIG_PATH,
    PROVIDERS,
    REASONING_EFFORT_LEVELS,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_WARN_CHARS,
)
from history_manager import (
    delete_session,
    export_messages_to_markdown,
    export_messages_to_text,
    generate_session_id,
    get_default_session_title,
    list_saved_sessions,
    load_session,
    rename_session,
    save_session,
    search_saved_sessions,
)
from state import get_current_system_prompt, load_tool_prefs, save_tool_prefs
from mcp_client import call_mcp_tool_by_name, fetch_all_mcp_tools, load_mcp_config
from themes import render_theme_selector



# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class SidebarSettings:
    """Values collected from the sidebar that the main app needs."""

    provider: str
    base_url: str
    api_key: str
    model: str
    safe_mode: bool
    dry_run_mode: bool
    stream_response: bool
    bearer_token: str
    temperature: float
    max_tokens: int | None
    max_tool_rounds: int
    reasoning_enabled: bool
    reasoning_budget_tokens: int | None
    reasoning_effort: str | None
    connect_timeout: float
    call_timeout: float
    dangerous_keywords: tuple[str, ...]
    system_prompt: str


@dataclass
class _Tuning:
    temperature: float
    max_tokens: int | None
    max_tool_rounds: int
    reasoning_enabled: bool
    reasoning_budget_tokens: int | None
    reasoning_effort: str | None
    connect_timeout: float
    call_timeout: float
    dangerous_keywords: tuple[str, ...] = field(default_factory=tuple)
    system_prompt: str = SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────────────────────
# Callbacks
# ──────────────────────────────────────────────────────────────────────────────
def _on_provider_change() -> None:
    """Synchronize base_url, default_model, and api_key when the user selects a different LLM Provider."""
    prov = st.session_state.get("llm_provider", DEFAULT_PROVIDER)
    if prov in PROVIDERS:
        p_info = PROVIDERS[prov]
        st.session_state["llm_base_url"] = p_info["base_url"]
        st.session_state["llm_model"] = p_info["default_model"]
        st.session_state["llm_custom_model"] = ""
        st.session_state["llm_api_key"] = os.getenv(p_info["default_api_key_env"], "")


def _on_reset_tuning_click() -> None:
    """Restore Advanced tuning values to module-level defaults."""
    st.session_state["adv_temperature"] = DEFAULT_TEMPERATURE
    st.session_state["adv_limit_tokens"] = False
    st.session_state["adv_max_tokens"] = DEFAULT_MAX_OUTPUT_TOKENS
    st.session_state["adv_max_tool_rounds"] = DEFAULT_MAX_TOOL_ROUNDS
    st.session_state["adv_reasoning_enabled"] = DEFAULT_REASONING_ENABLED
    st.session_state["adv_reasoning_budget_enabled"] = DEFAULT_REASONING_BUDGET_TOKENS is not None
    st.session_state["adv_reasoning_budget_tokens"] = DEFAULT_REASONING_BUDGET_TOKENS or 8192
    st.session_state["adv_reasoning_effort"] = DEFAULT_REASONING_EFFORT
    st.session_state["adv_connect_timeout"] = DEFAULT_CONNECT_TIMEOUT_SECONDS
    st.session_state["adv_call_timeout"] = DEFAULT_CALL_TIMEOUT_SECONDS
    st.session_state["adv_dangerous_keywords"] = ", ".join(DANGEROUS_NAME_KEYWORDS)
    st.session_state["system_prompt"] = SYSTEM_PROMPT
    st.toast("Advanced tuning restored to defaults.", icon=":material/restart_alt:")


# ──────────────────────────────────────────────────────────────────────────────
# Model settings
# ──────────────────────────────────────────────────────────────────────────────
def _init_provider_defaults() -> None:
    """Initialize state defaults on first run if missing or stale."""
    if "llm_provider" not in st.session_state or st.session_state["llm_provider"] not in PROVIDERS:
        st.session_state["llm_provider"] = DEFAULT_PROVIDER
        p_info = PROVIDERS[DEFAULT_PROVIDER]
        st.session_state["llm_base_url"] = p_info["base_url"]
        st.session_state["llm_model"] = p_info["default_model"]
        st.session_state["llm_custom_model"] = ""
        st.session_state["llm_api_key"] = os.getenv(p_info["default_api_key_env"], "")


def _render_model_settings() -> tuple[str, str, str, str]:
    _init_provider_defaults()
    provider_names = list(PROVIDERS.keys())

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

    model = st.selectbox("Model", options=models_list, key="llm_model")
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


# ──────────────────────────────────────────────────────────────────────────────
# Advanced tuning
# ──────────────────────────────────────────────────────────────────────────────
def _render_advanced_tuning() -> _Tuning:
    with st.expander("Advanced tuning", icon=":material/tune:"):
        st.session_state.setdefault("adv_temperature", DEFAULT_TEMPERATURE)
        st.session_state.setdefault("adv_limit_tokens", False)
        st.session_state.setdefault("adv_max_tokens", DEFAULT_MAX_OUTPUT_TOKENS)
        st.session_state.setdefault("adv_max_tool_rounds", DEFAULT_MAX_TOOL_ROUNDS)
        st.session_state.setdefault("adv_reasoning_enabled", DEFAULT_REASONING_ENABLED)
        st.session_state.setdefault("adv_reasoning_budget_enabled", DEFAULT_REASONING_BUDGET_TOKENS is not None)
        st.session_state.setdefault("adv_reasoning_budget_tokens", DEFAULT_REASONING_BUDGET_TOKENS or 8192)
        st.session_state.setdefault("adv_reasoning_effort", DEFAULT_REASONING_EFFORT)
        st.session_state.setdefault("adv_connect_timeout", DEFAULT_CONNECT_TIMEOUT_SECONDS)
        st.session_state.setdefault("adv_call_timeout", DEFAULT_CALL_TIMEOUT_SECONDS)
        st.session_state.setdefault("adv_dangerous_keywords", ", ".join(DANGEROUS_NAME_KEYWORDS))

        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            step=0.05,
            key="adv_temperature",
            help="Higher = more creative/random, lower = more focused/deterministic.",
        )

        reasoning_enabled = st.checkbox("Enable Reasoning", key="adv_reasoning_enabled")

        # Reasoning sub-controls are only meaningful when reasoning is on, but
        # we render them regardless (and disable them when off) so the layout
        # is stable and the user can see what options exist.
        reasoning_effort: str | None = st.selectbox(
            "Reasoning effort",
            options=list(REASONING_EFFORT_LEVELS),
            key="adv_reasoning_effort",
            disabled=not reasoning_enabled,
            help=(
                "Used by OpenAI o-series, Groq reasoning models, and similar. "
                "Higher = more thorough (and slower / more expensive). "
                "Ignored by providers that don't accept a `reasoning_effort`."
            ),
        )
        reasoning_budget_enabled = st.checkbox(
            "Set reasoning token budget",
            key="adv_reasoning_budget_enabled",
            disabled=not reasoning_enabled,
            help=(
                "Cap how many tokens the model may spend on internal reasoning. "
                "Leave off to let the provider decide. Honored by Gemini "
                "`thinking_budget` and Anthropic `budget_tokens`."
            ),
        )
        reasoning_budget_tokens: int | None = (
            int(
                st.number_input(
                    "Reasoning budget (tokens)",
                    min_value=128,
                    max_value=32000,
                    step=128,
                    key="adv_reasoning_budget_tokens",
                    disabled=not reasoning_enabled or not reasoning_budget_enabled,
                )
            )
            if reasoning_budget_enabled
            else None
        )

        limit_tokens = st.checkbox("Limit max output tokens", key="adv_limit_tokens")
        max_tokens: int | None = None
        if limit_tokens:
            max_tokens = int(
                st.number_input(
                    "Max output tokens",
                    min_value=64,
                    max_value=32000,
                    step=64,
                    key="adv_max_tokens",
                )
            )

        max_tool_rounds = int(
            st.slider(
                "Max tool-call rounds",
                min_value=1,
                max_value=20,
                key="adv_max_tool_rounds",
                help="How many back-and-forth tool calls the assistant may make before giving up.",
            )
        )

        st.subheader(":material/settings_ethernet: MCP connection", divider=False)
        connect_timeout = float(
            st.number_input(
                "Connect timeout (s)",
                min_value=1.0,
                max_value=120.0,
                step=1.0,
                key="adv_connect_timeout",
                help="Max time to wait when opening a new MCP server connection (e.g. spawning a stdio subprocess).",
            )
        )
        call_timeout = float(
            st.number_input(
                "Tool-call timeout (s)",
                min_value=1.0,
                max_value=300.0,
                step=5.0,
                key="adv_call_timeout",
                help="Max time to wait for a single tool call to finish.",
            )
        )

        keywords_raw = st.text_input(
            "Safe mode keywords (comma-separated)",
            key="adv_dangerous_keywords",
            help=(
                "Tool names containing any of these words require confirmation when Safe "
                "Mode is on. Matched as whole words, not raw substrings. All POST/PUT/PATCH/"
                "DELETE `call_api` calls always require confirmation regardless of this list."
            ),
        )
        dangerous_keywords = tuple(k.strip().lower() for k in keywords_raw.split(",") if k.strip())

        st.subheader(":material/psychology: System instructions", divider=False)
        st.session_state.setdefault("system_prompt", SYSTEM_PROMPT)
        system_prompt = st.text_area(
            "System Prompt",
            key="system_prompt",
            height=120,
            help="Instruct the AI assistant on its persona, behavior, and constraints.",
        )
        if len(system_prompt) > SYSTEM_PROMPT_WARN_CHARS:
            st.caption(
                f":material/warning: This system prompt is {len(system_prompt):,} characters "
                f"long — every character is resent on every single LLM call, which adds "
                f"latency and cost. Consider trimming it."
            )

        st.button(
            "Reset to defaults",
            icon=":material/restart_alt:",
            on_click=_on_reset_tuning_click,
            help="Restore all advanced tuning values to their built-in defaults.",
        )

    return _Tuning(
        temperature=temperature,
        max_tokens=max_tokens,
        max_tool_rounds=max_tool_rounds,
        reasoning_enabled=reasoning_enabled,
        reasoning_budget_tokens=reasoning_budget_tokens,
        reasoning_effort=reasoning_effort,
        connect_timeout=connect_timeout,
        call_timeout=call_timeout,
        dangerous_keywords=dangerous_keywords or DANGEROUS_NAME_KEYWORDS,
        system_prompt=system_prompt.strip() or SYSTEM_PROMPT,
    )


# ──────────────────────────────────────────────────────────────────────────────
# MCP server list / tools
# ──────────────────────────────────────────────────────────────────────────────
def _render_mcp_server_list() -> None:
    st.subheader(":material/hub: MCP servers")
    cfg = st.session_state.get("mcp_config") or {}
    if not cfg:
        st.caption(
            f":material/info: No `mcp_servers.json` found at `{MCP_CONFIG_PATH}`.",
            help="Add a server configuration to mcp_servers.json to enable tools.",
        )
        return
    server_errors = st.session_state.get("server_errors") or {}
    cols = st.columns(min(len(cfg), 3))
    for i, name in enumerate(cfg):
        with cols[i % len(cols)]:
            if name in server_errors:
                st.badge(name, icon=":material/cancel:", color="red")
            else:
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
        tools, mapping, real_mapping, _ = fetch_all_mcp_tools(
            st.session_state.mcp_config, connect_timeout=connect_timeout
        )
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


def _handle_login(
    login_path: str, username: str, password: str, connect_timeout: float, call_timeout: float
) -> None:
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
        key="login_path",
        help="Login endpoint path, e.g. /auth/login, /token",
    )
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Login via MCP", icon=":material/key:")

    if submitted:
        if not username or not password:
            st.error("Username and password are required!")
        else:
            try:
                _handle_login(login_path, username, password, connect_timeout, call_timeout)
            except Exception as exc:
                st.error(f"❌ Error calling MCP tool: {exc}")

    st.caption(
        ":material/info: Prefer this form over asking the assistant to log in for you in "
        "chat — credentials typed directly into the chat box are stored in the visible, "
        "exportable conversation history."
    )


def _render_mcp_tools_status(connect_timeout: float) -> None:
    if st.button("Refresh MCP tools", icon=":material/refresh:", key="refresh_mcp_tools"):
        st.session_state.mcp_config = load_mcp_config(MCP_CONFIG_PATH)
        for k in ("mcp_tools", "tool_to_server", "tool_to_real_name", "server_errors", "mcp_error"):
            st.session_state.pop(k, None)
        st.toast("Refreshing MCP server tools...", icon=":material/refresh:")
        st.rerun()

    if "mcp_tools" not in st.session_state:
        try:
            tools, mapping, real_mapping, errors = fetch_all_mcp_tools(
                st.session_state.mcp_config, connect_timeout=connect_timeout
            )
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

        # Tool Management
    tool_count = len(st.session_state.mcp_tools)
    disabled_tools = st.session_state.setdefault("disabled_tools", set())
    active_count = tool_count - len([t for t in st.session_state.mcp_tools if t["function"]["name"] in disabled_tools])
    
    st.badge(
        f"Connected — {active_count}/{tool_count} tools active",
        icon=":material/check_circle:",
        color="green",
    )

    with st.expander("🛠️ Tool Management", icon=":material/build:"):
        search_query = st.text_input("Search tools...", key="tool_search_input", placeholder="Filter by name...", label_visibility="collapsed")
        
        # Group tools by server
        tools_by_server = {}
        for tool in st.session_state.mcp_tools:
            func_name = tool["function"]["name"]
            # Filter by search query
            if search_query and search_query.lower() not in func_name.lower():
                continue
            server_name = st.session_state.tool_to_server.get(func_name, "unknown")
            tools_by_server.setdefault(server_name, []).append(tool)

        for server_name, tools in tools_by_server.items():
            with st.expander(f"📦 {server_name}"):
                col1, col2 = st.columns(2)
                if col1.button("Enable All", key=f"enable_{server_name}", use_container_width=True):
                    for t in tools:
                        name = t["function"]["name"]
                        disabled_tools.discard(name)
                        st.session_state[f"tool_toggle_{name}"] = True
                    save_tool_prefs(disabled_tools)
                    st.rerun()
                if col2.button("Disable All", key=f"disable_{server_name}", use_container_width=True):
                    for t in tools:
                        name = t["function"]["name"]
                        disabled_tools.add(name)
                        st.session_state[f"tool_toggle_{name}"] = False
                    save_tool_prefs(disabled_tools)
                    st.rerun()
                
                for tool in tools:
                    func_name = tool["function"]["name"]
                    desc = tool["function"].get("description", "No description")
                    is_enabled = func_name not in disabled_tools
                    if st.checkbox(func_name, value=is_enabled, key=f"tool_toggle_{func_name}", help=desc):
                        if func_name in disabled_tools:
                            disabled_tools.discard(func_name)
                            save_tool_prefs(disabled_tools)
                    else:
                        if func_name not in disabled_tools:
                            disabled_tools.add(func_name)
                            save_tool_prefs(disabled_tools)


# ──────────────────────────────────────────────────────────────────────────────
# Chat history / clear callbacks
# ──────────────────────────────────────────────────────────────────────────────
def _reset_active_conversation(new_id: str) -> None:
    # Single source of truth: ask `state.get_current_system_prompt` so the
    # same helper that `init_session_state` uses is the only place that
    # knows how to resolve the system prompt. Keeps behaviour identical
    # between a fresh boot and a "New chat" click.
    st.session_state.messages = [{"role": "system", "content": get_current_system_prompt()}]
    st.session_state.current_session_id = new_id
    st.session_state.saved_session_select = new_id
    for k in ("pending_tool_call", "pending_args", "pending_tool_queue", "resume_llm"):
        st.session_state.pop(k, None)


def _on_new_chat_click() -> None:
    _reset_active_conversation(generate_session_id())
    st.toast("New conversation started!", icon=":material/add_comment:")
    # st.rerun()


def _on_delete_session_click(target_id: str) -> None:
    delete_session(target_id)
    if st.session_state.get("current_session_id") == target_id:
        _reset_active_conversation(generate_session_id())
    else:
        st.session_state.saved_session_select = st.session_state.get("current_session_id")
    st.toast("Session deleted.", icon=":material/delete:")


def _on_clear_chat_click() -> None:
    _reset_active_conversation(generate_session_id())
    st.toast("Active chat cleared.", icon=":material/cleaning_services:")


def _on_session_select_change() -> None:
    selected_id = st.session_state.get("saved_session_select")
    current_id = st.session_state.get("current_session_id")
    if selected_id and selected_id != current_id:
        loaded_msgs = load_session(selected_id)
        st.session_state.messages = loaded_msgs or [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.current_session_id = selected_id
        for k in ("pending_tool_call", "pending_args", "pending_tool_queue", "resume_llm"):
            st.session_state.pop(k, None)
        st.toast(f"Loaded session: {selected_id[:8]}...", icon=":material/history:")


def _render_chat_history_management() -> None:
    st.subheader(":material/history: Chat history")

    with st.container(horizontal=True):
        st.button("New chat", icon=":material/add:", on_click=_on_new_chat_click, key="btn_new_chat")

        if st.session_state.messages and len(st.session_state.messages) > 1:
            current_id = st.session_state.get("current_session_id")
            if current_id:
                export_format = st.selectbox(
                    "Export format",
                    options=["Markdown (.md)", "JSON (.json)", "Text (.txt)"],
                    label_visibility="collapsed",
                    key="export_format_select",
                )

                if "Markdown" in export_format:
                    data = export_messages_to_markdown(st.session_state.messages)
                    filename, mime = f"{current_id}.md", "text/markdown"
                elif "Text" in export_format:
                    data = export_messages_to_text(st.session_state.messages)
                    filename, mime = f"{current_id}.txt", "text/plain"
                else:
                    data = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
                    filename, mime = f"{current_id}.json", "application/json"

                st.download_button(
                    label="Export",
                    icon=":material/download:",
                    data=data,
                    file_name=filename,
                    mime=mime,
                    key="btn_export_chat",
                    help="Tool results are already redacted before they enter the "
                    "conversation, so exports are safe to share.",
                )

    col_search, col_sort = st.columns([3, 2])
    with col_search:
        search_query = st.text_input(
            "Search history",
            placeholder="Search past chats...",
            label_visibility="collapsed",
            key="session_search_query",
        )
    with col_sort:
        sort_by_label = st.selectbox(
            "Sort saved sessions",
            options=["Newest", "Oldest", "Title"],
            label_visibility="collapsed",
            key="session_sort_by",
            help="Sort order for saved chat sessions",
        )
        sort_by_map = {"Newest": "newest", "Oldest": "oldest", "Title": "title"}
        sort_by_val = sort_by_map.get(sort_by_label, "newest")

    if search_query and search_query.strip():
        saved_sessions = search_saved_sessions(search_query, sort_by=sort_by_val)
        st.caption(
            f":material/search: Found {len(saved_sessions)} matching session{'s' if len(saved_sessions) != 1 else ''}"
            if saved_sessions
            else f":material/search_off: No sessions match '{search_query.strip()}'"
        )
    else:
        saved_sessions = list_saved_sessions(sort_by=sort_by_val)

    current_id = st.session_state.get("current_session_id")
    if not (saved_sessions or current_id):
        return

    session_ids, session_labels = _build_saved_session_selection(saved_sessions)

    if current_id:
        if current_id not in session_ids:
            # Current session is new and not in the saved list yet.
            # Generate a temporary label.
            current_messages = st.session_state.get("messages", [])
            if len(current_messages) > 1:
                session_labels[current_id] = get_default_session_title(current_messages)
            else:
                session_labels[current_id] = "New conversation (active)"
            session_ids.insert(0, current_id)
        else:
            # Current session is already in the saved list.
            # Just move its ID to the top for display purposes.
            session_ids.remove(current_id)
            session_ids.insert(0, current_id)

    if session_ids:
        st.selectbox(
            "Saved sessions",
            options=session_ids,
            index=session_ids.index(current_id) if current_id in session_ids else 0,
            format_func=lambda sid: session_labels.get(sid, sid),
            key="saved_session_select",
            on_change=_on_session_select_change,
        )

        selected_id = st.session_state.get("saved_session_select")
        if selected_id:
            with st.container(horizontal=True):
                with st.popover("Rename", icon=":material/edit:"):
                    st.caption(f"Rename session `{selected_id[:12]}`")
                    new_title = st.text_input(
                        "New title",
                        placeholder="Enter new conversation title...",
                        key=f"rename_input_{selected_id}",
                    )
                    if st.button("Save title", type="primary", key=f"btn_save_title_{selected_id}"):
                        if new_title.strip():
                            if rename_session(selected_id, new_title.strip()):
                                st.toast("Session title updated!", icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.error("Failed to rename session.")

                st.button(
                    "Delete session",
                    icon=":material/delete:",
                    on_click=_on_delete_session_click,
                    args=(selected_id,),
                    key="btn_delete_session",
                )


def _render_clear_conversation_button() -> None:
    st.button(
        "Clear active chat",
        icon=":material/cleaning_services:",
        on_click=_on_clear_chat_click,
        key="btn_clear_chat",
    )


def _render_debug_panel() -> None:
    st.divider()
    st.header(":material/bug_report: Debug & Audit Log")
    st.caption(
        ":material/shield: Secrets (tokens, passwords, headers) are redacted before "
        "entering this log — see `security.redact_secrets`."
    )
    enable_debug = st.checkbox(
        "Enable audit logging",
        value=st.session_state.get("enable_debug_panel", False),
        key="enable_debug_panel",
        help="Record and inspect tool executions and system events in real-time.",
    )
    if enable_debug:
        logs = st.session_state.get("audit_logs", [])
        st.caption(f"Total logged events: {len(logs)}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear logs", key="btn_clear_audit_logs"):
                st.session_state.audit_logs = []
                st.rerun()
        with col2:
            if logs and st.button("Export JSON", key="btn_export_audit_logs"):
                log_json = json.dumps(logs, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=log_json,
                    file_name="audit_logs.json",
                    mime="application/json",
                    key="download_audit_json",
                )

        if logs:
            with st.expander("Recent Audit Events", expanded=False):
                for i, entry in enumerate(logs[:20]):
                    st.text(f"[{entry['timestamp']}] {entry['type']}")
                    st.json(entry["data"])
                    if i < len(logs[:20]) - 1:
                        st.divider()


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────
def render_sidebar() -> SidebarSettings:
    """Render the full sidebar and return the settings the main app needs."""
    with st.sidebar:
        _render_chat_history_management()
        _render_clear_conversation_button()
        st.divider()

        # ── Theme picker ───────────────────────────────────────────────────────────
        st.header(":material/palette: Appearance")
        render_theme_selector()
        st.divider()

        st.header(":material/settings: Settings")
        provider, base_url, api_key, model = _render_model_settings()
        tuning = _render_advanced_tuning()
        st.divider()

        _render_login_form(tuning.connect_timeout, tuning.call_timeout)

        bearer_token = st.text_input(
            "Bearer token for the target API",
            key="api_bearer_token",
            type="password",
            help=(
                "Automatically added as an 'Authorization: Bearer <token>' header on every "
                "`call_api` call, overriding any Authorization header the model itself "
                "tries to supply. Filled in automatically after a successful login."
            ),
        )
        st.divider()

        safe_mode = st.checkbox(
            ":material/shield: Safe mode (confirm dangerous actions)",
            value=True,
            key="safe_mode",
            help=(
                "Ask for explicit confirmation before running a POST, DELETE, PUT, or PATCH "
                "`call_api` call, or any tool whose name matches a keyword from the Safe "
                "Mode keyword list above."
            ),
        )
        dry_run_mode = st.checkbox(
            ":material/preview: Dry-run mode (preview all tool calls)",
            value=False,
            key="dry_run_mode",
            help="When enabled, EVERY tool call (including read/GET actions) requires manual confirmation before execution.",
        )
        stream_response = st.checkbox(
            ":material/bolt: Stream response (typewriter effect)",
            value=True,
            key="stream_response",
            help="Stream model response tokens in real-time as they are generated for faster response times.",
        )
        st.divider()

        _render_mcp_server_list()
        _render_mcp_tools_status(tuning.connect_timeout)

        _render_debug_panel()

    return SidebarSettings(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        safe_mode=safe_mode,
        dry_run_mode=dry_run_mode,
        stream_response=stream_response,
        bearer_token=bearer_token,
        temperature=tuning.temperature,
        max_tokens=tuning.max_tokens,
        max_tool_rounds=tuning.max_tool_rounds,
        reasoning_enabled=tuning.reasoning_enabled,
        reasoning_budget_tokens=tuning.reasoning_budget_tokens,
        reasoning_effort=tuning.reasoning_effort,
        connect_timeout=tuning.connect_timeout,
        call_timeout=tuning.call_timeout,
        dangerous_keywords=tuning.dangerous_keywords,
        system_prompt=tuning.system_prompt,
    )
