"""MCP tools \u2192 OpenAI tool schema adapter.

Per skill \u00a79.3, handlers MUST go through this module and never call MCP
protocol directly.
"""
from __future__ import annotations

from typing import Any

from llm.base import ToolSpec


def mcp_tools_to_openai(tools: list[dict[str, Any]]) -> list[ToolSpec]:
    """Convert a list of MCP tool descriptors to OpenAI ToolSpec.

    MCP shape (loose): `{ "name": ..., "description": ..., "inputSchema": {...} }`.
    We map `inputSchema` \u2192 `parameters`.
    """
    out: list[ToolSpec] = []
    for raw in tools:
        name = raw.get("name")
        if not name:
            continue
        params = raw.get("inputSchema") or raw.get("parameters") or {}
        out.append(
            ToolSpec(
                name=name,
                description=raw.get("description", ""),
                parameters=params if isinstance(params, dict) else {},
            )
        )
    return out
