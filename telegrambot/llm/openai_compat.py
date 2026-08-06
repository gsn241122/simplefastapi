"""Shared OpenAI-API-compatible chat logic.

Used by all providers that expose an OpenAI-compatible endpoint
(MiniMax, Ollama; Gemini optionally). Keeps provider classes thin.
"""
from __future__ import annotations

from typing import AsyncIterator

import asyncio
import json

import httpx
from loguru import logger

from .base import ChatChunk, ChatRequest


async def stream_chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    request: ChatRequest,
    timeout_sec: float,
    client: httpx.AsyncClient,
) -> AsyncIterator[ChatChunk]:
    """Stream chat completions from an OpenAI-compatible endpoint.

    Yields ChatChunk. Treats network/HTTP errors as the caller's concern:
    they should be caught at the provider boundary, not swallowed.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = [m.model_dump(exclude_none=True) for m in request.messages]
    for msg in messages:
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function")
            if not fn:
                continue
            args = fn.get("arguments")
            if isinstance(args, dict):
                fn["arguments"] = json.dumps(args)
            elif not args:
                # DashScope's code model rejects missing/empty arguments;
                # it requires valid JSON even for no-arg tool calls.
                fn["arguments"] = "{}"

    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": request.temperature,
        "stream": True,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.tools:
        payload["tools"] = []
        for t in request.tools:
            tool_data = t.model_dump()
            # Ensure parameters structure is valid for DashScope/OpenAI-compat
            if not tool_data.get("parameters"):
                tool_data["parameters"] = {"type": "object", "properties": {}}
            payload["tools"].append({"type": "function", "function": tool_data})

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with client.stream(
                "POST", url, json=payload, headers=headers, timeout=timeout_sec
            ) as resp:
                if resp.status_code in (500, 502, 503, 504, 429) and attempt < max_retries - 1:
                    err_body = await resp.aread()
                    logger.warning(
                        "LLM API returned HTTP {}, retrying ({}/{})...",
                        resp.status_code,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue

                if resp.status_code >= 400:
                    err_body = await resp.aread()
                    logger.error("HTTP {} error from LLM provider: {}", resp.status_code, err_body.decode("utf-8", errors="replace"))
                    resp.raise_for_status()

                # Tool-call deltas arrive fragmented across many SSE chunks
                # (id/name in one chunk, arguments dribbled in piece by
                # piece in the following ones), keyed by "index". We must
                # accumulate them and only emit a complete, merged tool
                # call once the stream tells us it's done — never forward
                # a raw fragment as if it were a full tool call.
                #
                # Some providers (Gemini) attach extra provider-specific
                # fields to tool-call parts — e.g. "thought_signature" —
                # that MUST be echoed back verbatim on later turns or the
                # provider rejects the request. We don't hardcode these
                # field names; we just preserve any key we don't
                # recognize, both at the tool-call level and inside
                # "function", so this stays correct for other providers'
                # quirks too.
                _KNOWN_TC_KEYS = {"index", "id", "type", "function"}
                _KNOWN_FN_KEYS = {"name", "arguments"}

                tool_call_acc: dict[int, dict[str, object]] = {}

                def _finalized_tool_calls() -> list[dict[str, object]]:
                    result = []
                    for idx in sorted(tool_call_acc):
                        entry = tool_call_acc[idx]
                        args = entry["arguments"] or "{}"
                        try:
                            json.loads(args)
                        except json.JSONDecodeError:
                            # Fragments never resolved into valid JSON;
                            # don't ship a broken tool call upstream.
                            logger.warning(
                                "Dropping malformed tool call (index {}): "
                                "unparseable arguments {!r}", idx, args,
                            )
                            continue
                        tc_out: dict[str, object] = {
                            "id": entry["id"],
                            "type": "function",
                            "function": {
                                "name": entry["name"],
                                "arguments": args,
                                **entry["extra_fn"],  # type: ignore[dict-item]
                            },
                        }
                        tc_out.update(entry["extra"])  # type: ignore[arg-type]
                        result.append(tc_out)
                    return result

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        finals = _finalized_tool_calls()
                        yield ChatChunk(
                            finish_reason="tool_calls" if finals else "stop",
                            tool_calls=finals,
                        )
                        return
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta_obj = choice.get("delta") or {}
                    delta = delta_obj.get("content") or ""
                    finish = choice.get("finish_reason")
                    tool_call_fragments = delta_obj.get("tool_calls") or []

                    for frag in tool_call_fragments:
                        idx = frag.get("index", 0)
                        entry = tool_call_acc.setdefault(
                            idx,
                            {
                                "id": None,
                                "name": None,
                                "arguments": "",
                                "extra": {},
                                "extra_fn": {},
                            },
                        )
                        if frag.get("id"):
                            entry["id"] = frag["id"]
                        fn = frag.get("function") or {}
                        if fn.get("name"):
                            entry["name"] = fn["name"]
                        frag_args = fn.get("arguments")
                        if isinstance(frag_args, dict):
                            entry["arguments"] += json.dumps(frag_args)
                        elif frag_args:
                            entry["arguments"] += frag_args
                        # Preserve any provider-specific extra fields
                        # (e.g. Gemini's thought_signature) verbatim.
                        for k, v in frag.items():
                            if k not in _KNOWN_TC_KEYS and v is not None:
                                entry["extra"][k] = v  # type: ignore[index]
                        for k, v in fn.items():
                            if k not in _KNOWN_FN_KEYS and v is not None:
                                entry["extra_fn"][k] = v  # type: ignore[index]

                    if delta:
                        yield ChatChunk(delta=delta, finish_reason=None)

                    if finish:
                        finals = _finalized_tool_calls()
                        yield ChatChunk(finish_reason=finish, tool_calls=finals)
                        return
                return
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            if attempt < max_retries - 1:
                logger.warning(
                    "Network error calling LLM provider: {}, retrying ({}/{})...",
                    exc,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(1.5 * (attempt + 1))
            else:
                raise