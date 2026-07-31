"""Chat history rendering, the Safe Mode confirmation UI, and the main
LLM ↔ tool-calling loop.
"""
from __future__ import annotations

import streamlit as st
from openai import OpenAI

from config import GEMINI_BASE_URL
from sidebar import SidebarSettings
from tool_execution import (
    cancelled_tool_result,
    get_thought_signature,
    is_dangerous_tool_call,
    parse_tool_arguments,
    run_tool_call,
)


def render_chat_history() -> None:
    """Render every past user/assistant message in the conversation."""
    for msg in st.session_state.messages:
        if msg["role"] in ("user", "assistant") and msg.get("content"):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])


def render_pending_confirmation(settings: SidebarSettings) -> None:
    """If a dangerous tool call is awaiting confirmation, render the Safe
    Mode prompt and halt the script here until the user responds.
    """
    if not st.session_state.get("pending_tool_call"):
        return

    st.warning("⚠️ Dangerous action detected (Safe Mode is on)")
    tool_call = st.session_state.pending_tool_call
    args = st.session_state.pending_args
    st.markdown(
        f"**Tool:** `{tool_call.function.name}`  \n"
        f"**Method:** `{args.get('method', 'N/A')}`  \n"
        f"**Path:** `{args.get('path', 'N/A')}`"
    )
    with st.expander("🔍 View payload details"):
        st.json(args)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, execute", type="primary", key="btn_confirm_exec"):
            result = run_tool_call(
                tool_call,
                st.session_state.mcp_config,
                st.session_state.tool_to_server,
                settings.bearer_token,
                settings.call_timeout,
            )
            st.session_state.messages.append(result)
            st.session_state.pending_tool_call = None
            st.session_state.pending_args = None
            st.session_state.resume_llm = True
            st.rerun()
    with col2:
        if st.button("❌ Cancel", key="btn_confirm_cancel"):
            st.session_state.messages.append(cancelled_tool_result(tool_call))
            st.session_state.pending_tool_call = None
            st.session_state.pending_args = None
            st.session_state.resume_llm = True
            st.rerun()

    st.stop()


def _build_assistant_message(choice) -> dict:
    """Turn an OpenAI-style choice into a chat message dict, preserving the
    Gemini `thought_signature` on any tool calls.
    """
    assistant_msg = {"role": "assistant", "content": choice.content or ""}
    if not choice.tool_calls:
        return assistant_msg

    tool_call_dicts = []
    for tc in choice.tool_calls:
        tc_dict = {
            "id": tc.id,
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
    """If any requested tool call needs confirmation, save it to
    `session_state` for `render_pending_confirmation` to pick up.

    Returns True if the caller should stop and rerun to show that UI.
    """
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
    if not settings.api_key:
        st.error("Please enter your Gemini API key in the sidebar.")
        st.stop()

    client = OpenAI(api_key=settings.api_key, base_url=GEMINI_BASE_URL)
    tools = st.session_state.get("mcp_tools") or None

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

            response = client.chat.completions.create(**create_kwargs)
            choice = response.choices[0].message
            assistant_msg = _build_assistant_message(choice)

            if _stash_dangerous_call_if_any(choice, assistant_msg, settings.safe_mode, settings.dangerous_keywords):
                st.rerun()

            st.session_state.messages.append(assistant_msg)

            if not choice.tool_calls:
                placeholder.markdown(choice.content or "")
                return

            placeholder.markdown(
                "_calling tool(s): "
                + ", ".join(tc.function.name for tc in choice.tool_calls)
                + "..._"
            )

            for tc in choice.tool_calls:
                st.session_state.messages.append(
                    run_tool_call(
                        tc,
                        st.session_state.mcp_config,
                        st.session_state.tool_to_server,
                        settings.bearer_token,
                        settings.call_timeout,
                    )
                )

        placeholder.markdown("_Stopped after multiple tool calls without a final answer._")


def handle_chat_input(settings: SidebarSettings) -> None:
    """Read new chat input (or resume after a Safe Mode confirmation) and
    run one LLM turn if there's anything to send.
    """
    user_input = st.chat_input("Ask something about the API, files, bash, or git...")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
    elif st.session_state.resume_llm:
        st.session_state.resume_llm = False
    else:
        return

    run_chat_turn(settings)