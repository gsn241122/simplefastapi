"""MiniMax LLM provider (OpenAI-compatible)."""
from __future__ import annotations

from typing import AsyncIterator

import httpx

from llm.base import ChatChunk, ChatRequest, LLMProvider
from llm.openai_compat import stream_chat_completions


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_sec: float,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for openrouter provider")
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout = timeout_sec
        self._client = httpx.AsyncClient()

    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        async for chunk in stream_chat_completions(
            base_url=self._base_url,
            api_key=self._api_key,
            model=self._model,
            request=request,
            timeout_sec=self._timeout,
            client=self._client,
        ):
            yield chunk

    async def aclose(self) -> None:
        await self._client.aclose()
