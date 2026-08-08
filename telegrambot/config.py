"""Application configuration loaded from environment variables.

All runtime configuration MUST go through this module. No string literals
for config values elsewhere in the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

LLMProviderName = Literal["minimax", "gemini", "ollama", "qwencloud", "openrouter"]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Centralized settings. Backed by `.env` (auto-loaded)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(..., description="BotFather token")
    telegram_allowed_chat_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="Empty = allow all. Otherwise only these chat_ids are served.",
    )

    # --- LLM provider ---
    llm_provider: LLMProviderName = Field(default="gemini")
    default_model: str = Field(default="gemini-3.1-flash-lite")

    minimax_api_key: str = Field(default="", description="MiniMax API key")
    minimax_base_url: str = Field(default="https://api.minimax.chat/v1")
    minimax_model: str = Field(default="MiniMax-M3:cloud")

    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta")
    gemini_model: str = Field(default="gemini-3.1-flash-lite")

    ollama_base_url: str = Field(default="http://localhost:11434/v1")
    ollama_model: str = Field(default="minimax-m3:cloud")

    dashscope_api_key: str = Field(default="", validation_alias="DASHSCOPE_API_KEY")
    # Update default URL ke endpoint internasional
    qwencloud_base_url: str = Field(default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    qwencloud_model: str = Field(default="qwen3.8-max")

    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_model: str = Field(default="openai/gpt-oss-20b:free")

    # --- LLM behavior ---
    max_input_chars: int = Field(default=4000, description="Max user input characters before truncation")
    max_context_turns: int = Field(default=20, description="Sliding window of conversation turns kept in memory")
    request_timeout_sec: float = Field(default=60.0, description="HTTP timeout for LLM API calls (seconds)")

    # --- Rate limiting ---
    outbound_semaphore: int = Field(default=30, description="Max concurrent outbound Telegram API calls")
    per_user_msg_per_minute: int = Field(default=20, description="Max messages per user per minute")

    # --- Media upload limits ---
    max_image_file_size_mb: int = Field(default=10, description="Max image upload size (MB)")
    max_image_dimension: int = Field(default=2048, description="Max image width/height before auto-resize (px)")
    max_pdf_file_size_mb: int = Field(default=20, description="Max PDF upload size (MB)")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Loguru log level")

    @field_validator("telegram_allowed_chat_ids", mode="before")
    @classmethod
    def _parse_chat_ids(cls, v: object) -> list[int]:
        """Accept comma-separated string, list, or None. Empty/missing → []."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [int(p) for p in (p.strip() for p in v.split(",")) if p]
        if isinstance(v, list):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse telegram_allowed_chat_ids: {v!r}")


# ---------------------------------------------------------------------------
# Cached accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]

