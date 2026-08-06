"""Application configuration loaded from environment variables.

All runtime configuration MUST go through this module. No string literals
for config values elsewhere in the codebase (per skill §3.4).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


LLMProviderName = Literal["minimax", "gemini", "ollama"]


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

    # --- LLM provider switching (§9.6: 1 env var) ---
    llm_provider: LLMProviderName = Field(default="gemini")

    # Provider-specific (any may be empty if not in use)
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1"
    minimax_model: str = "MiniMax-M3:cloud"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-3.1-flash-lite"

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "minimax-m3:cloud"

    # --- LLM behavior ---
    max_input_chars: int = 4000
    max_context_turns: int = 10
    request_timeout_sec: float = 60.0

    # --- Rate limit (§3.4) ---
    outbound_semaphore: int = 30
    per_user_msg_per_minute: int = 20

    # --- Logging ---
    log_level: str = "INFO"

    @field_validator("telegram_allowed_chat_ids", mode="before")
    @classmethod
    def _parse_chat_ids(cls, v: object) -> list[int]:
        """Accept comma-separated string, list, or None. Empty/missing -> []."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        if isinstance(v, list):
            return [int(x) for x in v]
        raise ValueError(f"Cannot parse telegram_allowed_chat_ids: {v!r}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()  # type: ignore[call-arg]
