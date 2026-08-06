"""Unified tool dispatcher: routes calls to remote MCP servers OR local skills.

This wraps `mcp_agent.client.MCPClient` so callers (handlers) don't need to
know whether a tool is remote or local.

Usage in handler:

    from mcp_agent.dispatcher import UnifiedTools

    async def process_prompt(...):
        tools = UnifiedTools(mcp_client, local_server)
        all_tools = await tools.list_all()           # MCP + local
        # ... when LLM returns a tool call:
        result = await tools.call(name, arguments)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from mcp_agent.client import MCPClient
from mcp_agent.local_tools import LocalSkillServer


class UnifiedTools:
    """Single facade for remote MCP tools + local skill tools."""

    def __init__(
        self,
        mcp_client: MCPClient | None,
        local_server: LocalSkillServer | None,
    ) -> None:
        self.mcp_client = mcp_client
        self.local_server = local_server
        self._local_tools_index: dict[str, dict[str, Any]] = {}

    async def list_all(self) -> list[dict[str, Any]]:
        """Return combined list of remote + local tools."""
        out: list[dict[str, Any]] = []

        # Remote MCP tools
        if self.mcp_client is not None:
            try:
                out.extend(await self.mcp_client.list_tools())
            except Exception as exc:
                logger.warning("Failed to list MCP tools: {}", exc)

        # Local skill tools
        if self.local_server is not None:
            local_tools = self.local_server._ensure_discovered()
            self._local_tools_index = {t["name"]: t for t in local_tools}
            for t in local_tools:
                out.append({
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["inputSchema"],
                    "_server": self.local_server.name,
                })

        return out

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call to either remote or local server."""
        # Try local first if it owns this tool
        if name in self._local_tools_index:
            assert self.local_server is not None
            logger.info("Calling local skill tool: {}", name)
            return await self.local_server.call_tool(name, arguments or {})

        # Fall back to MCP remote (find server via index)
        if self.mcp_client is None:
            return _err(f"No MCP client available for tool {name!r}")

        # Rebuild index if empty (lazy)
        if not hasattr(self, "_remote_tools_index") or not self._remote_tools_index:
            self._remote_tools_index = {
                t["name"]: t.get("_server", "?")
                for t in await self.mcp_client.list_tools()
            }

        server = self._remote_tools_index.get(name)
        if server is None:
            return _err(
                f"Tool {name!r} not found. Available: "
                f"{sorted(list(self._local_tools_index) + list(self._remote_tools_index))[:10]}..."
            )
        return await self.mcp_client.call_tool(server, name, arguments or {})


def _err(msg: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": msg}],
        "isError": True,
    }