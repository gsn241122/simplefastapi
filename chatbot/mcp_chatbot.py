from __future__ import annotations

import argparse
import json
import os
import shlex
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_MCP_URL = os.getenv("SIMPLEFASTAPI_MCP_URL", "http://127.0.0.1:8003/mcp")


class MCPChatbot:
    """A simple MCP-based chatbot client for the SimpleFastAPI wrapper."""

    def __init__(self, url: str = DEFAULT_MCP_URL) -> None:
        self.url = url
        self.session: ClientSession | None = None
        self.last_token: str | None = None

    async def run(self) -> None:
        async with streamablehttp_client(self.url) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                self.session = session
                await session.initialize()
                print(f"Connected to MCP server at {self.url}")
                await self.print_tools()
                await self.interactive_loop()

    async def print_tools(self) -> None:
        assert self.session
        tools = await self.session.list_tools()
        print("Available tools:")
        for tool in tools.tools:
            print(f" - {tool.name}")

    async def interactive_loop(self) -> None:
        print("\nType 'help' for commands, 'exit' to quit.")
        while True:
            try:
                raw = input("mcp-chatbot> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return

            if not raw:
                continue
            if raw.lower() in {"exit", "quit"}:
                print("Bye.")
                return
            if raw.lower() in {"help", "?"}:
                self.print_help()
                continue

            try:
                await self.handle_command(raw)
            except Exception as exc:
                print(f"Error: {exc}")

    def print_help(self) -> None:
        print(
            """
Supported commands:
  help                       Show this help message.
  health                     Call the wrapper health_check tool.
  routes                     Call the wrapper list_routes tool.
  login <user> <pass>        Login to /auth/login and store bearer token.
  users [search]             List users; optional case-insensitive search.
  api <METHOD> <PATH> [json] Call low-level /call_api tool.
  call <tool> [json]         Call a named MCP tool with JSON arguments.
  exit                       Quit the chatbot.

Example:
  login admin admin
  users admin
  api GET /users/ '{"params": {"search": "admin"}}'
"""
        )

    async def handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        if not parts:
            return

        command = parts[0].lower()
        if command == "health":
            result = await self.call_tool("health_check")
            self.print_result(result)
        elif command == "routes":
            result = await self.call_tool("list_routes")
            self.print_result(result)
        elif command == "login":
            if len(parts) != 3:
                print("Usage: login <username> <password>")
                return
            await self.login(parts[1], parts[2])
        elif command == "users":
            search = parts[1] if len(parts) > 1 else None
            await self.list_users(search)
        elif command == "api":
            if len(parts) < 3:
                print("Usage: api <METHOD> <PATH> [json]")
                return
            method = parts[1]
            path = parts[2]
            data = self._load_json_argument(parts[3]) if len(parts) > 3 else None
            result = await self.call_api(method, path, **(data or {}))
            self.print_result(result)
        elif command == "call":
            if len(parts) < 2:
                print("Usage: call <tool> [json]")
                return
            tool_name = parts[1]
            args = self._load_json_argument(parts[2]) if len(parts) > 2 else None
            result = await self.call_tool(tool_name, args)
            self.print_result(result)
        else:
            await self.handle_natural_language(raw)

    def _load_json_argument(self, raw: str) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}")
        raise ValueError("JSON argument must be an object")

    async def handle_natural_language(self, text: str) -> None:
        lowered = text.lower()
        if "health" in lowered or "status" in lowered:
            result = await self.call_tool("health_check")
            self.print_result(result)
            return
        if "routes" in lowered or "paths" in lowered or "endpoints" in lowered:
            result = await self.call_tool("list_routes")
            self.print_result(result)
            return
        if "login" in lowered and "admin" in lowered:
            print("Use `login <username> <password>` to authenticate.")
            return
        if "user" in lowered or "list users" in lowered:
            search = None
            if "admin" in lowered:
                search = "admin"
            await self.list_users(search)
            return
        print("Unknown command. Type 'help' for available options.")

    async def login(self, username: str, password: str) -> None:
        print(f"Logging in as {username}...")
        response = await self.call_api(
            "POST",
            "/auth/login",
            data={"username": username, "password": password},
        )
        self.print_result(response)
        body = response.get("body")
        if isinstance(body, dict) and body.get("success") and isinstance(body.get("data"), dict):
            token = body["data"].get("access_token")
            if token:
                self.last_token = token
                print("Saved bearer token for future API calls.")

    async def list_users(self, search: str | None = None) -> None:
        params = {"search": search} if search else None
        headers = self._auth_header()
        result = await self.call_api("GET", "/users/", params=params, headers=headers)
        self.print_result(result)

    async def call_api(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self.session
        payload = {
            "method": method,
            "path": path,
            "json_body": json_body,
            "params": params,
            "headers": headers,
            "data": data,
        }
        result = await self.session.call_tool("call_api", payload)
        return self._extract_structured(result)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.session
        result = await self.session.call_tool(name, arguments)
        return self._extract_structured(result)

    def _extract_structured(self, tool_result: Any) -> dict[str, Any]:
        if getattr(tool_result, "isError", False):
            return {
                "error": True,
                "detail": getattr(tool_result, "error", tool_result),
            }
        return getattr(tool_result, "structuredContent", {}) or {}

    def _auth_header(self) -> dict[str, str] | None:
        if self.last_token:
            return {"Authorization": f"Bearer {self.last_token}"}
        return None

    def print_result(self, result: dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple MCP chatbot client for SimpleFastAPI.")
    parser.add_argument(
        "--url",
        default=DEFAULT_MCP_URL,
        help="The MCP server URL for the SimpleFastAPI wrapper.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chatbot = MCPChatbot(url=args.url)
    anyio.run(chatbot.run, backend="trio")


if __name__ == "__main__":
    main()
