"""Chat history rendering, the Safe Mode confirmation UI, and the main
LLM ↔ tool-calling loop.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import streamlit as st
from openai import OpenAI

from config import (
    GEMINI_BASE_URL,
    MAX_TOOL_CALL_ID_HEX_LEN,
    REASONING_SYSTEM_PROMPT_HINT,
    TOOL_RESULT_TRUNCATE_CHARS,
    get_reasoning_extra_body,
)
from history_manager import get_default_session_title, save_session
from mcp_client import call_mcp_tool_by_name
from security import redact_secrets
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


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _cached_tool_id_map(messages_json: str) -> dict[str, str]:
    """Cached mapping tool_call_id → function_name, keyed by messages JSON."""
    try:
        messages = json.loads(messages_json)
    except json.JSONDecodeError:
        return {}
    mapping: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                tc_id = tc.get("id", "")
                tc_name = tc.get("function", {}).get("name", "unknown_tool")
                if tc_id:
                    mapping[tc_id] = tc_name
    return mapping


def _build_tool_id_map() -> dict[str, str]:
    try:
        messages_json = json.dumps(st.session_state.messages, default=str, sort_keys=True)
    except TypeError:
        messages_json = "[]"
    return _cached_tool_id_map(messages_json)


def _truncate_for_display(text: str, limit: int = TOOL_RESULT_TRUNCATE_CHARS) -> tuple[str, bool]:
    if len(text) > limit:
        return text[:limit] + "...", True
    return text, False


def _looks_like_error(parsed: Any) -> bool:
    if not isinstance(parsed, dict):
        return False
    if "error" in parsed:
        return True
    status = parsed.get("status_code")
    return isinstance(status, int) and status >= 400


def _redact_json_string_for_display(raw: str) -> str:
    """Best-effort: parse `raw` as JSON, redact secrets, re-serialize.

    Tool results are already redacted before they're stored (see
    tool_execution.run_tool_call), so this is a defense-in-depth second
    pass — it also catches the arguments a MODEL generated for a tool call,
    which are not touched by tool_execution.py since they're the input, not
    the output.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    return json.dumps(redact_secrets(parsed), ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Chat history rendering
# ──────────────────────────────────────────────────────────────────────────────
def render_chat_history() -> None:
    """Render past messages, grouping assistant text + tool calls in one bubble."""
    tool_id_map = _build_tool_id_map()

    for msg in st.session_state.messages:
        role = msg.get("role")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        # ── User messages ────────────────────────────────────────────────
        # NOTE: unsafe_allow_html is intentionally NOT used here. Streamlit's
        # default st.markdown already renders markdown formatting; the only
        # thing unsafe_allow_html additionally permits is raw <script>/<img
        # onerror=...> etc, which is a real XSS surface for text that
        # ultimately originates from a user, an LLM, or a third-party API
        # response (tool results). None of that is a trusted source.
        if role == "user" and content:
            with st.chat_message("user"):
                st.markdown(content)

        elif role == "assistant":
            reasoning = msg.get("reasoning")
            if content or tool_calls or reasoning:
                with st.chat_message("assistant"):
                    # Render the model's internal reasoning first (if any) in a
                    # collapsible block so it doesn't drown the actual answer.
                    # It's only ever populated when reasoning was enabled, so
                    # users who never toggle the option never see this.
                    if reasoning:
                        with st.expander(
                            f":material/psychology: Reasoning ({len(reasoning):,} chars)",
                            icon=":material/psychology:",
                            expanded=False,
                        ):
                            st.markdown(reasoning)
                    if content:
                        st.markdown(content)
                    if tool_calls:
                        for tc in tool_calls:
                            func_name = tc["function"]["name"]
                            with st.expander(f"Tool called: `{func_name}`", icon=":material/build:"):
                                st.code(
                                    _redact_json_string_for_display(tc["function"]["arguments"]),
                                    language="json",
                                )
                    if metrics := msg.get("metrics"):
                        st.caption(
                            f":material/timer: {metrics.get('total_time_s', 0):.2f}s "
                            f"(TTFT: {metrics.get('ttft_s', 0):.2f}s) • "
                            f"📊 {metrics.get('total_tokens', 0)} tokens "
                            f"({metrics.get('tokens_per_sec', 0):.1f} t/s)"
                        )

        # ── Tool results ────────────────────────────────────────────────
        elif role == "tool":
            tool_id = msg.get("tool_call_id", "")
            func_name = tool_id_map.get(tool_id, "unknown_tool")
            content_str = msg.get("content", "")  # already redacted at the source

            is_error = False
            parsed_content: Any = None
            try:
                parsed_content = json.loads(content_str)
                is_error = _looks_like_error(parsed_content)
            except Exception:
                pass

            display_content, is_truncated = _truncate_for_display(content_str)
            if is_truncated:
                try:
                    parsed_content = json.loads(display_content)
                except Exception:
                    parsed_content = None

            result_icon = ":material/cancel:" if is_error else ":material/check_circle:"
            status_text = "Failed" if is_error else "Success"
            exec_time = msg.get("execution_time_s")
            time_str = f" ({exec_time:.2f}s)" if exec_time else ""
            with st.chat_message("assistant"):
                expander_label = f"Tool result: `{func_name}` — {status_text}{time_str}"
                if is_truncated:
                    expander_label += " (truncated)"
                with st.expander(expander_label, icon=result_icon):
                    if parsed_content is not None and isinstance(parsed_content, (dict, list)):
                        st.json(parsed_content)
                    else:
                        st.code(
                            display_content,
                            language="json" if display_content.lstrip().startswith(("{", "[")) else "text",
                        )
                    if is_truncated:
                        st.caption(
                            f"⚠️ Output truncated to first {TOOL_RESULT_TRUNCATE_CHARS:,} characters. "
                            f"Full length: {len(content_str):,} chars."
                        )


# ──────────────────────────────────────────────────────────────────────────────
# Safe-mode confirmation
# ──────────────────────────────────────────────────────────────────────────────
def _run_safe_tools_before(queue: list[tuple], up_to_idx: int, settings: SidebarSettings) -> None:
    """Execute all safe (non-dangerous) tool calls before `up_to_idx`."""
    tool_to_real_name = st.session_state.get("tool_to_real_name", {})
    for safe_tc, safe_args, _ in queue[:up_to_idx]:
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


def _finalize_queue_after_dangerous(queue: list[tuple], consumed_idx: int, cancelled: bool, tc: Any) -> None:
    """Common cleanup after Execute or Cancel: pop consumed entry, decide resume."""
    remaining = queue[consumed_idx + 1 :]
    st.session_state.pending_tool_queue = remaining if remaining else None
    st.session_state.resume_llm = not remaining
    if cancelled:
        st.session_state.messages.append(cancelled_tool_result(tc))
    st.rerun()


def _run_all_remaining_safe(queue: list[tuple], settings: SidebarSettings) -> None:
    """Execute every entry in the queue as safe (no dangerous calls)."""
    tool_to_real_name = st.session_state.get("tool_to_real_name", {})
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
    st.session_state.pending_tool_queue = None
    st.session_state.resume_llm = True
    st.rerun()


def render_pending_confirmation(settings: SidebarSettings) -> None:
    """If tool calls in the queue require confirmation or execution, process
    them safely in order without missing any tool responses.
    """
    queue = st.session_state.get("pending_tool_queue")
    if not queue:
        return

    next_idx = next((i for i, (_, _, is_danger) in enumerate(queue) if is_danger), None)

    if next_idx is None:
        _run_all_remaining_safe(queue, settings)
        return  # unreachable; _run_all_remaining_safe calls st.rerun()

    tc, args, _ = queue[next_idx]
    tool_name = get_tool_call_name(tc)
    tool_id = get_tool_call_id(tc)

    warning_title = (
        "Tool execution preview (Dry-run mode is active)"
        if settings.dry_run_mode
        else "Dangerous action detected (Safe Mode is on)"
    )

    st.warning(warning_title, icon=":material/preview:" if settings.dry_run_mode else ":material/security:")
    st.markdown(
        f"**Tool:** `{tool_name}`  \n"
        f"**Method:** `{args.get('method', 'N/A')}`  \n"
        f"**Path:** `{args.get('path', 'N/A')}`"
    )
    with st.expander("View payload details", icon=":material/search:"):
        st.json(redact_secrets(args))

    with st.container(horizontal=True):
        if st.button("Execute", type="primary", icon=":material/check_circle:", key=f"btn_confirm_exec_{tool_id}"):
            _run_safe_tools_before(queue, next_idx, settings)
            tool_to_real_name = st.session_state.get("tool_to_real_name", {})
            result = run_tool_call(
                tc,
                st.session_state.mcp_config,
                st.session_state.tool_to_server,
                tool_to_real_name,
                settings.bearer_token,
                settings.call_timeout,
            )
            st.session_state.messages.append(result)
            _finalize_queue_after_dangerous(queue, next_idx, cancelled=False, tc=tc)

        if st.button("Cancel", icon=":material/cancel:", key=f"btn_confirm_cancel_{tool_id}"):
            _run_safe_tools_before(queue, next_idx, settings)
            _finalize_queue_after_dangerous(queue, next_idx, cancelled=True, tc=tc)

    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# LLM turn & tool-call building
# ──────────────────────────────────────────────────────────────────────────────
def _build_assistant_message(choice) -> dict:
    assistant_msg: dict = {"role": "assistant", "content": choice.content or ""}
    if not choice.tool_calls:
        return assistant_msg

    tool_call_dicts = []
    for tc in choice.tool_calls:
        tc_id = getattr(tc, "id", None) or f"call_{uuid.uuid4().hex[:MAX_TOOL_CALL_ID_HEX_LEN]}"
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


def _build_create_kwargs(settings: SidebarSettings, stream: bool, tools: list[dict] | None) -> dict:
    """Assemble the kwargs for `client.chat.completions.create`.

    When `settings.reasoning_enabled` is True, this function:
      1. Adds a provider-specific `extra_body` payload if the provider supports
         a native reasoning/thinking parameter (Ollama, Gemini, OpenAI o-series,
         Anthropic via proxy, Groq). The OpenAI Python SDK forwards `extra_body`
         verbatim to the upstream HTTP API.
      2. As a universal fallback (and for providers without a native param
         such as OpenRouter generic models), appends a short chain-of-thought
         hint to the system message. The original `st.session_state.messages`
         is NEVER mutated: we build a shallow copy and patch the copy.
    """
    kwargs: dict = dict(
        model=settings.model,
        messages=st.session_state.messages,
        tools=tools,
        tool_choice="auto" if tools else None,
        temperature=settings.temperature,
    )
    if settings.max_tokens:
        kwargs["max_tokens"] = settings.max_tokens
    if stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

    # ── Reasoning mode ─────────────────────────────────────────────────────
    if getattr(settings, "reasoning_enabled", False):
        provider = getattr(settings, "provider", "") or ""
        budget = getattr(settings, "reasoning_budget_tokens", None)
        effort = getattr(settings, "reasoning_effort", None)

        # 1) Native provider param via extra_body (Ollama/Gemini/OpenAI/etc.).
        extra_body = get_reasoning_extra_body(provider, settings.model, budget, effort)
        if extra_body:
            kwargs["extra_body"] = extra_body
        else:
            # 2) Fallback: nudge the model via system prompt. Mutate a copy,
            #    not session_state, so the on-disk chat history stays clean.
            messages = list(kwargs["messages"])
            for i, m in enumerate(messages):
                if m.get("role") == "system":
                    messages[i] = {**m, "content": (m.get("content") or "") + REASONING_SYSTEM_PROMPT_HINT}
                    break
            else:
                messages.insert(0, {"role": "system", "content": REASONING_SYSTEM_PROMPT_HINT.lstrip()})
            kwargs["messages"] = messages
    return kwargs


def _extract_reasoning_delta(delta: Any) -> str:
    """Pull a reasoning chunk out of a streaming delta, tolerating the
    different shapes providers actually emit:
      - Ollama:            delta.reasoning  (str)            [primary]
      - DeepSeek / Qwen:   delta.reasoning_content  (str)    [primary]
      - Anthropic:         delta.reasoning / delta.thinking (varies)
      - Gemini (extra):    delta.extra_content / model_extra
    Returns "" if nothing was found.
    """
    for attr in ("reasoning", "reasoning_content", "thinking", "thought"):
        val = getattr(delta, attr, None)
        if isinstance(val, str) and val:
            return val
    extra = getattr(delta, "model_extra", None)
    if isinstance(extra, dict):
        for key in ("reasoning", "reasoning_content", "thinking", "thought"):
            val = extra.get(key)
            if isinstance(val, str) and val:
                return val
    return ""


def _stream_response(client: OpenAI, settings: SidebarSettings, placeholder, tools: list[dict] | None):
    """Stream the response token by token. Returns (assistant_msg, raw_tool_calls, metrics).

    When `settings.reasoning_enabled` is on, any reasoning content the model
    streams (e.g. Ollama `delta.reasoning`) is captured into a separate field
    on the assistant message and rendered in a collapsible block by
    `render_chat_history` rather than dumped into the main answer.
    """
    t_start = time.perf_counter()
    ttft = None
    stream = client.chat.completions.create(**_build_create_kwargs(settings, stream=True, tools=tools))

    full_content = ""
    full_reasoning = ""
    tool_calls_builder: dict[int, dict] = {}
    usage_data = None

    for chunk in stream:
        if hasattr(chunk, "usage") and chunk.usage:
            usage_data = chunk.usage

        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        if delta.content or delta.tool_calls:
            if ttft is None:
                ttft = time.perf_counter() - t_start

        # Capture reasoning BEFORE the main content so the placeholder
        # never flashes the answer without its "thought" header.
        reasoning_chunk = _extract_reasoning_delta(delta) if getattr(settings, "reasoning_enabled", False) else ""
        if reasoning_chunk:
            full_reasoning += reasoning_chunk
            # Stream the tail of the reasoning in a small muted caption so the
            # user can see the model is thinking, not stuck.
            placeholder.caption(f":material/psychology: _thinking… {full_reasoning[-120:]}_")

        if delta.content and not delta.tool_calls:
            full_content += delta.content
            # Streamed text is our own accumulation of model output; no
            # unsafe_allow_html here either, same rationale as above.
            placeholder.markdown(full_content + "▌")

        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = getattr(tc_delta, "index", 0)
                if idx not in tool_calls_builder:
                    tool_calls_builder[idx] = {"id": "", "name": "", "arguments": "", "extra_content": None}
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

    total_time = time.perf_counter() - t_start
    if ttft is None:
        ttft = total_time

    placeholder.markdown(full_content if full_content else "")

    prompt_tokens = getattr(usage_data, "prompt_tokens", 0) if usage_data else 0
    completion_tokens = getattr(usage_data, "completion_tokens", 0) if usage_data else 0
    total_tokens = (
        getattr(usage_data, "total_tokens", 0) if usage_data else (prompt_tokens + completion_tokens)
    )
    tokens_per_sec = (completion_tokens / total_time) if total_time > 0 and completion_tokens > 0 else 0.0

    metrics = {
        "total_time_s": total_time,
        "ttft_s": ttft,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tokens_per_sec": tokens_per_sec,
    }

    assistant_msg: dict = {"role": "assistant", "content": full_content, "metrics": metrics}
    if full_reasoning:
        assistant_msg["reasoning"] = full_reasoning
    tool_calls_list = []
    for idx in sorted(tool_calls_builder.keys()):
        tc = tool_calls_builder[idx]
        tc_id = tc["id"] or f"call_{idx}_{uuid.uuid4().hex[:MAX_TOOL_CALL_ID_HEX_LEN - 2]}"
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
    return assistant_msg, tool_calls_list, metrics

def _non_stream_response(client: OpenAI, settings: SidebarSettings, placeholder, tools: list[dict] | None):
    """Non-streaming response. Returns (assistant_msg, raw_tool_calls, metrics, error).

    When reasoning is enabled, the non-stream path may also receive a
    `reasoning` / `reasoning_content` field on the assistant message. We
    surface that as a separate `reasoning` key on the stored message so the
    chat-history renderer can show it in a collapsible block.
    """
    t_start = time.perf_counter()
    response = client.chat.completions.create(**_build_create_kwargs(settings, stream=False, tools=tools))
    elapsed = time.perf_counter() - t_start

    choice = response.choices[0].message
    assistant_msg = _build_assistant_message(choice)
    raw_tool_calls = choice.tool_calls or []

    # Pull a reasoning field off the choice if the provider attached one.
    for attr in ("reasoning", "reasoning_content", "thinking", "thought"):
        val = getattr(choice, attr, None)
        if isinstance(val, str) and val:
            assistant_msg["reasoning"] = val
            break
    # Some providers use model_extra / extra_content.
    if "reasoning" not in assistant_msg:
        for src in (getattr(choice, "model_extra", None) or {}).items() if hasattr(choice, "model_extra") else []:
            if isinstance(src, tuple) and len(src) == 2 and src[0] in ("reasoning", "reasoning_content", "thinking") and isinstance(src[1], str):
                assistant_msg["reasoning"] = src[1]
                break

    prompt_tokens = completion_tokens = total_tokens = 0
    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        total_tokens = getattr(usage, "total_tokens", 0) or 0
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    tokens_per_sec = (completion_tokens / elapsed) if elapsed > 0 and completion_tokens > 0 else 0.0

    metrics = {
        "total_time_s": elapsed,
        "ttft_s": elapsed,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "tokens_per_sec": tokens_per_sec,
    }
    assistant_msg["metrics"] = metrics

    if total_tokens:
        placeholder.caption(
            f"📊 tokens: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total"
        )
    return assistant_msg, raw_tool_calls, metrics, None

def _filter_tools_with_thinking_tool(settings: SidebarSettings, all_tools: list[dict], placeholder) -> list[dict]:
    """Use the sequential-thinking tool to filter the tool list, if available.

    IMPORTANT: The sequential-thinking tool is an INTERNAL routing helper only.
    It must NEVER appear in the tools list sent to the LLM. If the LLM can see
    it, it will call it directly as a regular tool call, causing the chat turn
    to get stuck waiting for a tool result from a server that is only meant to
    be called pre-flight as a router — not mid-conversation.
    """
    thinker_tool_name = next(
        (
            tool["function"]["name"]
            for tool in all_tools
            if tool["function"]["name"].startswith("sequential-thinking__")
        ),
        None,
    )

    # Strip the thinker from the list that will eventually be handed to the LLM.
    # This must happen unconditionally — even on the fallback / error paths.
    tools_for_llm = [t for t in all_tools if t["function"]["name"] != thinker_tool_name]

    if not thinker_tool_name:
        return tools_for_llm

    last_user_message = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        None,
    )
    if not last_user_message:
        return tools_for_llm

    placeholder.markdown("_routing..._")

    try:
        tool_to_server = st.session_state.get("tool_to_server", {})
        # Build schemas only from non-thinker tools (thinker is already excluded)
        tool_schemas = [tool["function"] for tool in tools_for_llm]
        args = {"query": last_user_message, "tools": tool_schemas}

        result = call_mcp_tool_by_name(
            st.session_state.mcp_config,
            tool_to_server,
            thinker_tool_name,
            args,
            st.session_state.get("tool_to_real_name"),
            settings.connect_timeout,
            settings.call_timeout,
        )

        relevant_tool_names = []
        if isinstance(result, dict) and "relevant_tools" in result:
            relevant_tool_names = [tool["name"] for tool in result["relevant_tools"] if "name" in tool]
        elif isinstance(result, list):
            relevant_tool_names = result

        if not relevant_tool_names:
            return tools_for_llm

        filtered_tools = [tool for tool in tools_for_llm if tool["function"]["name"] in relevant_tool_names]

        if filtered_tools:
            st.toast(f"Router selected {len(filtered_tools)} tool(s).", icon=":material/route:")
            return filtered_tools

    except Exception as e:
        st.toast(f"Tool router failed: {e}", icon=":material/warning:")

    return tools_for_llm


def run_chat_turn(settings: SidebarSettings) -> None:
    """Send the conversation to the LLM and resolve any tool calls it makes,
    looping up to `settings.max_tool_rounds` times before giving up.
    """
    api_key = settings.api_key or "dummy-key"
    base_url = getattr(settings, "base_url", None) or GEMINI_BASE_URL

    if not settings.api_key and "Ollama" not in getattr(settings, "provider", ""):
        st.error(
            f":material/key_off: Please enter your {getattr(settings, 'provider', 'LLM')} API key in the sidebar."
        )
        st.stop()

    client = OpenAI(api_key=api_key, base_url=base_url)
    tool_to_real_name = st.session_state.get("tool_to_real_name", {})

    with st.chat_message("assistant"):
        placeholder = st.empty()

        all_tools = st.session_state.get("mcp_tools") or []
        disabled_tools = st.session_state.get("disabled_tools") or set()
        active_tools = [
            t for t in all_tools
            if t.get("function", {}).get("name") not in disabled_tools
        ]
        relevant_tools = _filter_tools_with_thinking_tool(settings, active_tools, placeholder)

        placeholder.markdown("_thinking..._")

        for _ in range(settings.max_tool_rounds):
            turn_start = time.perf_counter()
            try:
                if settings.stream_response:
                    assistant_msg, raw_tool_calls, _ = _stream_response(client, settings, placeholder, relevant_tools)
                else:
                    assistant_msg, raw_tool_calls, _, error = _non_stream_response(
                        client, settings, placeholder, relevant_tools
                    )
                    if error:
                        raise error
            except Exception as exc:
                placeholder.empty()
                st.error(f"**LLM API Error:** {exc}", icon=":material/error:")
                st.toast(f"LLM Call Failed: {exc}", icon=":material/warning:")
                return

            st.session_state.messages.append(assistant_msg)

            # Auto-save immediately after appending, so a Safe Mode
            # confirmation rerun mid-turn can't lose data.
            current_id = st.session_state.get("current_session_id")
            messages = st.session_state.get("messages") or []
            if current_id and len(messages) > 1:
                title = get_default_session_title(messages)
                save_session(current_id, title, messages)
                st.session_state.pop("saved_session_select", None)

            if not raw_tool_calls:
                elapsed = time.perf_counter() - turn_start
                st.caption(f":material/timer: {elapsed:.2f}s")
                return

            tool_names = [
                tc["function"]["name"] if isinstance(tc, dict) else tc.function.name for tc in raw_tool_calls
            ]
            placeholder.markdown("_calling tool(s): " + ", ".join(tool_names) + "..._")

            queue = []
            has_dangerous = False
            for tc in raw_tool_calls:
                args = parse_tool_arguments(tc)
                is_danger = is_dangerous_tool_call(
                    tc, args, settings.safe_mode, settings.dangerous_keywords, settings.dry_run_mode
                )
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


# ──────────────────────────────────────────────────────────────────────────────
# Suggestion chips & chat input
# ──────────────────────────────────────────────────────────────────────────────
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
    visible_messages = [m for m in st.session_state.messages if m.get("role") != "system" and m.get("content")]
    if not visible_messages:
        selected = st.pills("Try asking:", list(_SUGGESTIONS.keys()), label_visibility="collapsed")
        if selected:
            prompt = _SUGGESTIONS[selected]
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_chat_turn(settings)
            st.rerun()
            return

    # Default submit_mode keeps the send button always visible/clickable
    # (with "disable" the button greys out when the textarea is empty, which
    # is harder to discover on a fresh page).
    user_input = st.chat_input(
        "Ask something about the API, files, bash, or git...",
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
    st.rerun()
