"""Shared OpenAI-API-compatible chat logic.

Used by all providers that expose an OpenAI-compatible endpoint
(MiniMax, Ollama; Gemini optionally). Keeps provider classes thin.
"""
from __future__ import annotations

from typing import AsyncIterator

import httpx

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

    payload: dict[str, object] = {
        "model": model,
        "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        "temperature": request.temperature,
        "stream": True,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.tools:
        payload["tools"] = [t.model_dump() for t in request.tools]

    async with client.stream(
        "POST", url, json=payload, headers=headers, timeout=timeout_sec
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                yield ChatChunk(finish_reason="stop")
                return
            try:
                import json

                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = (choice.get("delta") or {}).get("content") or ""
            finish = choice.get("finish_reason")
            tool_calls = (choice.get("delta") or {}).get("tool_calls") or []
            yield ChatChunk(delta=delta, finish_reason=finish, tool_calls=tool_calls)
