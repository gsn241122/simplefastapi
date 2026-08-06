"""Abstract LLM provider interface.

All providers MUST implement `LLMProvider`. Handlers MUST NOT branch on
provider name (per skill §9.2).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """OpenAI-style chat message."""

    role: str = Field(..., description="system | user | assistant | tool")
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolSpec(BaseModel):
    """OpenAI-style tool/function spec."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int | None = None


class ChatChunk(BaseModel):
    """Streaming or final chunk of assistant output."""

    delta: str = ""
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class LLMProvider(ABC):
    """Common interface for all LLM backends."""

    name: str

    @abstractmethod
    async def chat(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        """Stream chat completions. MUST be async-iterator even for non-streaming."""

    @abstractmethod
    async def aclose(self) -> None:
        """Release any held resources (HTTP clients, etc.)."""
