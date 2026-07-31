"""Chat history rendering, the Safe Mode confirmation UI, and the main
LLM ↔ tool-calling loop.
"""
from __future__ import annotations

import json
import streamlit as st
from openai import OpenAI

from config import GEMINI_BASE_URL
from history_manager import get_default_session_title, save_session
from sidebar import SidebarSettings
from tool_execution import (
    cancelled_tool_result,
    get_thought_signature,
    get_tool_call_id,
    get_tool_call_name,
    is_dangerous_tool_call,
    parse_tool_arguments,
    run_tool_call,
)


def _build_tool_id_map() -> dict[str, str]:
    """Build a mapping from tool_call_id → function_name in O(n) for the current session."""
    mapping: dict[str, str] = {}
    for m in st.session_state.messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                tc_id = tc.get("id", "")
                tc_name = tc.get("function", {}).get("name", "unknown_tool")
                if tc_id:
                    mapping[tc_id] = tc_name
    return mapping


def render_chat_history() -> None:
    """Render past messages, grouping assistant text + tool calls in one bubble."""
    # Pre-build a lookup from tool_call_id → function_name once per render pass
    tool_id_map = _build_tool_id_map()

    for msg in st.session_state.messages:
        role = msg.get("role")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        # ── User / plain-text assistant messages ──────────────────────────────
        if role == "user" and content:
            with st.chat_message("user"):
                st.markdown(content)

        elif role == "assistant":
            # Render text + tool-call expanders inside a single bubble
            if content or tool_calls:
                with st.chat_message("assistant"):
                    if content:
                        st.markdown(content)
                    if tool_calls:
                        for tc in tool_calls:
                            func_name = tc["function"]["name"]
                            with st.expander(
                                f"Tool called: `{func_name}`",
                                icon=":material/build:",
                            ):
                                st.code(tc["function"]["arguments"], language="json")

        # ── Tool results ──────────────────────────────────────────────────────
        elif role == "tool":
            tool_id = msg.get("tool_call_id", "")
            func_name = tool_id_map.get(tool_id, "unknown_tool")
            content_str = msg.get("content", "")

            is_error = False
            try:
                parsed_content = json.loads(content_str)
                if isinstance(parsed_content, dict) and (
                    "error" in parsed_content
                    or parsed_content.get("status_code", 200) >= 400
                ):
                    is_error = True
            except Exception:
                pass

            result_icon = ":material/cancel:" if is_error else ":material/check_circle:"
            status_text = "Failed" if is_error else "Success"
            with st.chat_message("assistant"):
                with st.expander(
                    f"Tool result: `{func_name}` — {status_text}",
                    icon=result_icon,
                ):
                    st.code(content_str, language="json")


def render_pending_confirmation(settings: SidebarSettings) -> None:
    """If tool calls in the queue require confirmation or execution, process
    them safely in order without missing any tool responses.
    """
    queue = st.session_state.get("pending_tool_queue")
    if not queue:
        return

    # Find the index of the next dangerous call in the queue
    next_idx = None
    for idx, (tc, args, is_danger) in enumerate(queue):
        if is_danger:
            next_idx = idx
            break

    tool_to_real_name = st.session_state.get("tool_to_real_name", {})

    if next_idx is None:
        # All remaining tool calls in the queue are safe to execute
        for tc, args, _ in queue:
            result = run_tool_call(
                tc,
                st.session_state.mcp_config,
                st.session_state.tool_to_server,
                tool_to_real_name,
                settings.bearer_token,
                settings.call_timeout,
            )
            st.session_state.messages.append(result)
        st.session_state.pending_tool_queue = None
        st.session_state.resume_llm = True
        st.rerun()

    tc, args, _ = queue[next_idx]
    tool_name = get_tool_call_name(tc)
    tool_id = get_tool_call_id(tc)

    st.warning("Dangerous action detected (Safe Mode is on)", icon=":material/security:")
    st.markdown(
        f"**Tool:** `{tool_name}`  \n"
        f"**Method:** `{args.get('method', 'N/A')}`  \n"
        f"**Path:** `{args.get('path', 'N/A')}`"
    )
    with st.expander("View payload details", icon=":material/search:"):
        st.json(args)

    with st.container(horizontal=True):
        if st.button("Execute", type="primary", icon=":material/check_circle:", key=f"btn_confirm_exec_{tool_id}"):
            # Execute all safe tools before this dangerous tool
            for safe_tc, safe_args, _ in queue[:next_idx]:
                st.session_state.messages.append(
                    run_tool_call(
                        safe_tc,
                        st.session_state.mcp_config,
                        st.session_state.tool_to_server,
                        tool_to_real_name,
                        settings.bearer_token,
                        settings.call_timeout,
                    )
                )
            # Execute this dangerous tool
            result = run_tool_call(
                tc,
                st.session_state.mcp_config,
                st.session_state.tool_to_server,
                tool_to_real_name,
                settings.bearer_token,
                settings.call_timeout,
            )
            st.session_state.messages.append(result)

            remaining = queue[next_idx + 1 :]
            st.session_state.pending_tool_queue = remaining if remaining else None
            if not remaining:
                st.session_state.resume_llm = True
            st.rerun()

        if st.button("Cancel", icon=":material/cancel:", key=f"btn_confirm_cancel_{tool_id}"):
            # Execute all safe tools before this dangerous tool
            for safe_tc, safe_args, _ in queue[:next_idx]:
                st.session_state.messages.append(
                    run_tool_call(
                        safe_tc,
                        st.session_state.mcp_config,
                        st.session_state.tool_to_server,
                        tool_to_real_name,
                        settings.bearer_token,
                        settings.call_timeout,
                    )
                )
            # Record cancelled result for this dangerous tool
            st.session_state.messages.append(cancelled_tool_result(tc))

            remaining = queue[next_idx + 1 :]
            st.session_state.pending_tool_queue = remaining if remaining else None
            if not remaining:
                st.session_state.resume_llm = True
            st.rerun()

    st.stop()


def _build_assistant_message(choice) -> dict:
    """Turn an OpenAI-style choice into a chat message dict, preserving the
    Gemini `thought_signature` on any tool calls.
    """
    import uuid

    assistant_msg = {"role": "assistant", "content": choice.content or ""}
    if not choice.tool_calls:
        return assistant_msg

    tool_call_dicts = []
    for tc in choice.tool_calls:
        tc_id = getattr(tc, "id", None) or f"call_{uuid.uuid4().hex[:8]}"
        tc_dict = {
            "id": tc_id,
            "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
        }
        thought_sig = get_thought_signature(tc)
        if thought_sig:
            tc_dict["extra_content"] = thought_sig
        tool_call_dicts.append(tc_dict)
    assistant_msg["tool_calls"] = tool_call_dicts
    return assistant_msg


def _stash_dangerous_call_if_any(
    choice, assistant_msg: dict, safe_mode: bool, dangerous_keywords: tuple[str, ...]
) -> bool:
    """Legacy helper maintained for compatibility."""
    if not choice.tool_calls:
        return False

    for tc in choice.tool_calls:
        args = parse_tool_arguments(tc)
        if is_dangerous_tool_call(tc, args, safe_mode, dangerous_keywords):
            st.session_state.pending_tool_call = tc
            st.session_state.pending_args = args
            st.session_state.messages.append(assistant_msg)
            return True
    return False


def run_chat_turn(settings: SidebarSettings) -> None:
    """Send the conversation to Gemini and resolve any tool calls it makes,
    looping up to `settings.max_tool_rounds` times before giving up.
    """
    api_key = settings.api_key or "dummy-key"
    base_url = getattr(settings, "base_url", None) or GEMINI_BASE_URL

    if not settings.api_key and "Ollama" not in getattr(settings, "provider", ""):
        st.error(f"Please enter your {getattr(settings, 'provider', 'LLM')} API key in the sidebar.")
        st.stop()

    client = OpenAI(api_key=api_key, base_url=base_url)
    tools = st.session_state.get("mcp_tools") or None
    tool_to_real_name = st.session_state.get("tool_to_real_name", {})

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("_thinking..._")

        for _ in range(settings.max_tool_rounds):
            create_kwargs = dict(
                model=settings.model,
                messages=st.session_state.messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                temperature=settings.temperature,
            )
            if settings.max_tokens:
                create_kwargs["max_tokens"] = settings.max_tokens

            if settings.stream_response:
                create_kwargs["stream"] = True
                stream = client.chat.completions.create(**create_kwargs)

                full_content = ""
                tool_calls_builder: dict[int, dict] = {}

                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        full_content += delta.content
                        placeholder.markdown(full_content + "▌")

                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = getattr(tc_delta, "index", 0)
                            if idx not in tool_calls_builder:
                                tool_calls_builder[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                    "extra_content": None,
                                }
                            if tc_delta.id:
                                tool_calls_builder[idx]["id"] += tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_builder[idx]["name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    tool_calls_builder[idx]["arguments"] += tc_delta.function.arguments
                            thought_sig = get_thought_signature(tc_delta)
                            if thought_sig:
                                tool_calls_builder[idx]["extra_content"] = thought_sig

                import uuid

                placeholder.markdown(full_content if full_content else "")

                assistant_msg = {"role": "assistant", "content": full_content}
                tool_calls_list = []
                for idx in sorted(tool_calls_builder.keys()):
                    tc = tool_calls_builder[idx]
                    tc_id = tc["id"] or f"call_{idx}_{uuid.uuid4().hex[:6]}"
                    tc_dict = {
                        "id": tc_id,
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    if tc["extra_content"]:
                        tc_dict["extra_content"] = tc["extra_content"]
                    tool_calls_list.append(tc_dict)

                if tool_calls_list:
                    assistant_msg["tool_calls"] = tool_calls_list

                raw_tool_calls = tool_calls_list
            else:
                response = client.chat.completions.create(**create_kwargs)
                choice = response.choices[0].message
                assistant_msg = _build_assistant_message(choice)
                raw_tool_calls = choice.tool_calls or []

            st.session_state.messages.append(assistant_msg)

            if not raw_tool_calls:
                return

            tool_names = [
                tc["function"]["name"] if isinstance(tc, dict) else tc.function.name
                for tc in raw_tool_calls
            ]
            placeholder.markdown("_calling tool(s): " + ", ".join(tool_names) + "..._")

            queue = []
            has_dangerous = False
            for tc in raw_tool_calls:
                args = parse_tool_arguments(tc)
                is_danger = is_dangerous_tool_call(tc, args, settings.safe_mode, settings.dangerous_keywords)
                queue.append((tc, args, is_danger))
                if is_danger:
                    has_dangerous = True

            if has_dangerous:
                st.session_state.pending_tool_queue = queue
                st.rerun()

            for tc, args, _ in queue:
                st.session_state.messages.append(
                    run_tool_call(
                        tc,
                        st.session_state.mcp_config,
                        st.session_state.tool_to_server,
                        tool_to_real_name,
                        settings.bearer_token,
                        settings.call_timeout,
                    )
                )

        placeholder.markdown("_Stopped after multiple tool calls without a final answer._")


def _auto_save_current_session() -> None:
    """Save active session messages to disk immediately after user/LLM interactions."""
    current_id = st.session_state.get("current_session_id")
    messages = st.session_state.get("messages") or []
    if current_id and len(messages) > 1:
        title = get_default_session_title(messages)
        save_session(current_id, title, messages)


# Suggestion chips shown on an empty conversation
_SUGGESTIONS: dict[str, str] = {
    ":blue[:material/api:] List API endpoints": "List all available API endpoints",
    ":green[:material/folder:] Show project files": "Show the project file structure",
    ":orange[:material/terminal:] Run a bash command": "Run `ls -la` in the current directory",
    ":violet[:material/commit:] Show recent commits": "Show the last 5 git commits",
}


def handle_chat_input(settings: SidebarSettings) -> None:
    """Read new chat input (or resume after a Safe Mode confirmation) and
    run one LLM turn if there's anything to send.
    """
    # Show suggestion chips when the conversation is empty
    visible_messages = [
        m for m in st.session_state.messages if m.get("role") != "system"
    ]
    if not visible_messages:
        selected = st.pills(
            "Try asking:",
            list(_SUGGESTIONS.keys()),
            label_visibility="collapsed",
        )
        if selected:
            prompt = _SUGGESTIONS[selected]
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_chat_turn(settings)
            _auto_save_current_session()
            st.rerun()

    user_input = st.chat_input(
        "Ask something about the API, files, bash, or git...",
        submit_mode="disable",
    )

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
    elif st.session_state.resume_llm:
        st.session_state.resume_llm = False
    else:
        return

    run_chat_turn(settings)
    _auto_save_current_session()
    st.rerun()