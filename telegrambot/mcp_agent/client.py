"""Async MCP client with real transport lifecycle (stdio & sse).

Manages real connections to MCP servers defined in `mcp_server.json`,
discovers real tools, and executes real tool calls.
"""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any
from loguru import logger


from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


class MCPClient:
    def __init__(self, registry: dict[str, Any]) -> None:
        self._registry = registry
        self._sessions: dict[str, dict[str, Any]] = {}
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
        spec = self._registry["servers"][name]
        stack = AsyncExitStack()

        # Build env with PATH including common binary directories
        env = os.environ.copy()
        custom_env = spec.get("env") or {}
        env.update(custom_env)
        bun_path = "/home/dell/.bun/bin"
        if bun_path not in env.get("PATH", ""):
            env["PATH"] = f"{bun_path}:{env.get('PATH', '')}"

        try:
            if "command" in spec:
                cmd = spec["command"]
                args = spec.get("args", [])
                params = StdioServerParameters(command=cmd, args=args, env=env)
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(stdio_client(params)),
                    timeout=5.0,
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=5.0)
            elif "url" in spec:
                url = spec["url"]
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(sse_client(url)),
                    timeout=3.0,
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(), timeout=3.0)
            else:
                raise ValueError(f"Server {name!r} has neither 'command' nor 'url'")

            self._sessions[name] = {
                "session": session,
                "stack": stack,
                "spec": spec,
                "connected": True,
            }
        except Exception:
            try:
                await stack.aclose()
            except Exception:
                pass
            raise

    async def list_tools(self) -> list[dict[str, Any]]:
        """List tools from all connected real MCP servers."""
        tools: list[dict[str, Any]] = []
        for name, sess_info in self._sessions.items():
            if not sess_info.get("connected"):
                continue
            session: ClientSession = sess_info["session"]
            try:
                result = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                for tool in result.tools:
                    schema = (
                        tool.inputSchema
                        if isinstance(tool.inputSchema, dict)
                        else tool.inputSchema.model_dump()
                        if hasattr(tool.inputSchema, "model_dump")
                        else {}
                    )
                    tools.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": schema,
                        "_server": name,
                    })
            except Exception as exc:
                logger.warning("Error listing tools from MCP server {!r}: {}", name, exc)
        return tools

    async def call_tool(
        self, server: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on a specific connected MCP server."""
        sess_info = self._sessions.get(server)
        if not sess_info or not sess_info.get("connected"):
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error: MCP server '{server}' is not connected.",
                }]
            }

        session: ClientSession = sess_info["session"]
        try:
            res = await asyncio.wait_for(
                session.call_tool(name, arguments), timeout=60.0
            )
            content_list = []
            for item in res.content:
                if hasattr(item, "text"):
                    content_list.append({"type": item.type, "text": item.text})
                elif hasattr(item, "model_dump"):
                    content_list.append(item.model_dump())
                else:
                    content_list.append({"type": "text", "text": str(item)})
            return {"content": content_list, "isError": getattr(res, "isError", False)}
        except Exception as exc:
            logger.error("Error executing tool {!r} on server {!r}: {}", name, server, exc)
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error executing tool {name}: {exc}",
                }]
            }

    async def aclose(self) -> None:
        """Shutdown all MCP server connections and subprocesses."""
        self._closed = True
        async with self._lock:
            for name, sess_info in list(self._sessions.items()):
                stack: AsyncExitStack | None = sess_info.get("stack")
                if stack:
                    try:
                        await stack.aclose()
                    except (Exception, asyncio.CancelledError):
                        pass
            self._sessions.clear()



@asynccontextmanager
async def mcp_lifecycle(registry: dict[str, Any]):
    client = MCPClient(registry)
    await client.start()
    try:
        yield client
    finally:
        await client.aclose()


