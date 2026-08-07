"""Provider registry: routes to the active LLM by name.

Provider switching is a single env var change (LLM_PROVIDER) per §9.6.
"""
from __future__ import annotations

from functools import lru_cache

from config import Settings, get_settings
from llm.base import LLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.minimax import MiniMaxProvider
from llm.providers.ollama import OllamaProvider
from llm.providers.qwencloud import QwenCloudProvider
from llm.providers.openrouter import OpenRouterProvider


def build_provider(settings: Settings, name: str | None = None) -> LLMProvider:
    """Construct the provider selected by `name` (or settings.llm_provider)."""
    chosen = (name or settings.llm_provider).lower()
    if chosen == "minimax":
        return MiniMaxProvider(
            api_key=settings.minimax_api_key,
            base_url=settings.minimax_base_url,
            model=settings.minimax_model,
            timeout_sec=settings.request_timeout_sec,
        )
    if chosen == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            model=settings.gemini_model,
            timeout_sec=settings.request_timeout_sec,
        )
    if chosen == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_sec=settings.request_timeout_sec,
        )
    if chosen == "qwencloud":
        return QwenCloudProvider(
            api_key=settings.dashscope_api_key,
            base_url=settings.qwencloud_base_url,
            model=settings.qwencloud_model,
            timeout_sec=settings.request_timeout_sec,
        )
    if chosen == "openrouter":
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_model,
            timeout_sec=settings.request_timeout_sec,
        )
    raise ValueError(f"Unknown LLM provider: {chosen!r}")


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Cached singleton provider (lazy-initialized)."""
    return build_provider(get_settings())
