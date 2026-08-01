"""Persistent connection pool for MCP servers.

Without this, a naive `asyncio.run()`-per-call setup opens a brand-new
connection -- and for stdio servers, a brand-new subprocess -- for *every
single tool call*, and connects to every server one at a time on startup.

This module keeps one background thread with a long-lived event loop where
each server's session is opened once (lazily, on first use) and reused for
the lifetime of the process. Both `mcp.ClientSession` (stdio servers) and
`fastmcp.Client` (HTTP/SSE servers) expose the same async `list_tools()` /
`call_tool()` methods, so both are handled uniformly here.
"""
from __future__ import annotations

import asyncio
import atexit
import sys
import threading
from contextlib import AsyncExitStack
from typing import Any

from config import DEFAULT_CALL_TIMEOUT_SECONDS, DEFAULT_CONNECT_TIMEOUT_SECONDS


class _ServerConnection:
    """One open MCP session plus the exit stack that owns its resources."""

    def __init__(self, session: Any, exit_stack: AsyncExitStack) -> None:
        self.session = session
        self.exit_stack = exit_stack


class MCPConnectionPool:
    """Owns a dedicated background event loop and a persistent session per
    configured MCP server, reused across tool calls and across Streamlit
    reruns for the lifetime of the process.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="mcp-pool", daemon=True)
        self._thread.start()
        self._connections: dict[str, _ServerConnection] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        atexit.register(self.close)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro, timeout: float) -> Any:
        """Schedule a coroutine on the pool's own loop and block the calling
        (Streamlit) thread until it finishes or the timeout elapses.
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # -- connection lifecycle (runs on the pool's loop) ------------------------

    def _lock_for(self, server_name: str) -> asyncio.Lock:
        # Safe without extra locking: dict access here never yields to the
        # event loop, so no other coroutine can interleave between the
        # membership check and the assignment.
        if server_name not in self._locks:
            self._locks[server_name] = asyncio.Lock()
        return self._locks[server_name]

    async def _open_connection(
        self, server_name: str, server_config: dict, connect_timeout: float
    ) -> _ServerConnection:
        stack = AsyncExitStack()
        try:
            if "command" in server_config:
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client

                params = StdioServerParameters(
                    command=server_config["command"],
                    args=server_config.get("args", []),
                    env=server_config.get("env"),
                )
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(stdio_client(params)), timeout=connect_timeout
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=connect_timeout)
            elif "url" in server_config:
                from fastmcp import Client

                session = await asyncio.wait_for(
                    stack.enter_async_context(Client(server_config["url"])), timeout=connect_timeout
                )
            else:
                raise ValueError("Server config must contain 'url' or 'command'")
        except Exception:
            await stack.aclose()
            raise

        return _ServerConnection(session=session, exit_stack=stack)

    async def _get_connection(
        self, server_name: str, server_config: dict, connect_timeout: float
    ) -> _ServerConnection:
        async with self._lock_for(server_name):
            conn = self._connections.get(server_name)
            if conn is not None:
                return conn
            print(f"[MCP] Opening persistent connection to '{server_name}'...", file=sys.stderr)
            conn = await self._open_connection(server_name, server_config, connect_timeout)
            self._connections[server_name] = conn
            print(f"[MCP] Connected to '{server_name}'", file=sys.stderr)
            return conn

    async def _drop_connection(self, server_name: str) -> None:
        conn = self._connections.pop(server_name, None)
        if conn is not None:
            try:
                await conn.exit_stack.aclose()
            except Exception:
                pass

    # -- public sync API, safe to call from the Streamlit thread --------------

    def list_tools_many(
        self, config: dict[str, dict], connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    ) -> dict[str, tuple[list | None, str | None]]:
        """Connect to every server in `config` concurrently (reusing any
        already-open connections) and list their tools.

        Returns {server_name: (tools, None)} on success or
        {server_name: (None, error_message)} on failure, per server.
        """

        async def _one(name: str, cfg: dict) -> tuple[str, tuple[list | None, str | None]]:
            try:
                conn = await self._get_connection(name, cfg, connect_timeout)
                result = await conn.session.list_tools()
                # mcp.ClientSession.list_tools() -> ListToolsResult with
                # `.tools`; fastmcp.Client.list_tools() -> a bare list.
                tools = getattr(result, "tools", result)
                return name, (tools, None)
            except Exception as e:
                await self._drop_connection(name)
                # Return a tuple (None, error_message) even if list_tools() itself returns a non-tuple
                return name, (None, f"{type(e).__name__}: {e}")

        async def _run_all() -> dict:
            pairs = await asyncio.gather(*(_one(name, cfg) for name, cfg in config.items()))
            return dict(pairs)

        return self._run_coro(_run_all(), timeout=connect_timeout + 10)

    def call_tool(
        self,
        server_name: str,
        server_config: dict,
        tool_name: str,
        arguments: dict[str, Any],
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        call_timeout: float = DEFAULT_CALL_TIMEOUT_SECONDS,
    ) -> Any:
        """Call a tool using the server's persistent connection (opening it
        first if this is the first call to that server).
        """

        async def _run():
            conn = await self._get_connection(server_name, server_config, connect_timeout)
            return await asyncio.wait_for(conn.session.call_tool(tool_name, arguments), timeout=call_timeout)

        try:
            return self._run_coro(_run(), timeout=connect_timeout + call_timeout + 5)
        except Exception:
            # Drop a possibly-broken connection so the next call reconnects
            # cleanly instead of repeatedly failing against a dead session.
            self._run_coro(self._drop_connection(server_name), timeout=5)
            raise

    def close(self) -> None:
        """Close every open connection. Registered with `atexit`."""
        if not hasattr(self, "_loop") or self._loop.is_closed():
            return

        async def _close_all() -> None:
            for name in list(self._connections):
                await self._drop_connection(name)

        try:
            self._run_coro(_close_all(), timeout=5)
        except Exception:
            pass