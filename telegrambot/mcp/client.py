"""Async MCP client with reconnect/backoff lifecycle (per skill §3.4).

This is a scaffold: the transport layer is pluggable. When `mcp_server.json`
is empty (the default), the client starts in an idle state and `list_tools`
returns []. To wire a real transport, implement `_connect_one`.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from loguru import logger


class MCPClient:
    def __init__(self, registry: dict[str, Any]) -> None:
        self._registry = registry
        self._sessions: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def server_names(self) -> list[str]:
        return list(self._registry.get("servers", {}).keys())

    async def start(self) -> None:
        """Connect to all configured servers (fail-fast per server, log on failure)."""
        for name in self.server_names:
            try:
                await self._connect_one(name)
                logger.info("MCP server connected: {}", name)
            except Exception as exc:  # noqa: BLE001 - log & continue
                logger.warning("MCP server {!r} connect failed: {}", name, exc)

    async def _connect_one(self, name: str) -> None:
        """Override/subclass to add a real transport (stdio/websocket/http)."""
        spec = self._registry["servers"][name]
        # Placeholder session marker; replace with real session in subclass.
        self._sessions[name] = {"spec": spec, "connected": True}

    async def reconnect(self, name: str) -> None:
        """Reconnect a single server with exp backoff (1,2,4,8, cap 30s)."""
        delay = 1.0
        while not self._closed:
            try:
                await self._connect_one(name)
                logger.info("MCP server reconnected: {}", name)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("MCP reconnect {!r} failed: {}; retry in {}s",
                               name, exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools from all connected servers. Empty when no servers."""
        tools: list[dict[str, Any]] = []
        for name, session in self._sessions.items():
            if not session.get("connected"):
                continue
            # Subclass should populate session["tools"] from a real `tools/list` call.
            for tool in session.get("tools", []):
                tool = dict(tool)
                tool["_server"] = name
                tools.append(tool)
        return tools

    async def call_tool(
        self, server: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool. Default impl raises; override in subclass."""
        raise NotImplementedError(
            "MCPClient.call_tool must be implemented by a real transport subclass"
        )

    async def aclose(self) -> None:
        self._closed = True
        async with self._lock:
            for name in list(self._sessions):
                try:
                    sess = self._sessions.pop(name)
                    closer = sess.get("aclose")
                    if closer is not None:
                        await closer()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("MCP close {!r} error: {}", name, exc)


@asynccontextmanager
async def mcp_lifecycle(registry: dict[str, Any]) -> AsyncIterator[MCPClient]:
    """Context manager that wires startup + shutdown."""
    client = MCPClient(registry)
    await client.start()
    try:
        yield client
    finally:
        await client.aclose()
