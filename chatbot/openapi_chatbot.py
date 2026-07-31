from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_MCP_URL = os.getenv("SIMPLEFASTAPI_MCP_URL", "http://127.0.0.1:8003/mcp")


class OpenAPIChatbot:
    """A simple OpenAPI-driven chatbot client for the SimpleFastAPI MCP wrapper."""

    def __init__(self, url: str = DEFAULT_MCP_URL, app_api_key: str | None = None) -> None:
        self.url = url
        self.app_api_key = app_api_key
        self.session: ClientSession | None = None
        self.last_token: str | None = None
        self.openapi: dict[str, Any] | None = None
        self.endpoint_index: list[dict[str, Any]] = []

    async def run(self) -> None:
        async with streamablehttp_client(self.url) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                self.session = session
                await session.initialize()
                print(f"Connected to MCP server at {self.url}")
                print("Loading OpenAPI schema from the wrapped app...")
                await self.load_openapi_schema()
                self.print_summary()
                await self.interactive_loop()

    async def load_openapi_schema(self) -> None:
        result = await self.call_api("GET", "/openapi.json")
        if not result or not isinstance(result.get("body"), dict):
            raise RuntimeError("Failed to load OpenAPI schema from /openapi.json")
        self.openapi = result["body"]
        self.endpoint_index = self._build_endpoint_index(self.openapi)

    def _build_endpoint_index(self, openapi: dict[str, Any]) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        paths = openapi.get("paths", {})
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, spec in methods.items():
                if not isinstance(spec, dict):
                    continue
                summary = spec.get("summary") or spec.get("description") or ""
                operation_id = spec.get("operationId") or f"{method}_{path}"
                endpoints.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "summary": summary,
                        "operation_id": operation_id,
                        "parameters": spec.get("parameters", []),
                        "request_body": spec.get("requestBody"),
                    }
                )
        return endpoints

    def print_summary(self) -> None:
        print("OpenAPI endpoints loaded.")
        print(f"Discovered {len(self.endpoint_index)} endpoints.")
        if self.app_api_key:
            print("Using X-API-Key authentication from environment or CLI.")
        print("Type 'help' for commands.")

    async def interactive_loop(self) -> None:
        while True:
            try:
                raw = input("openapi-chatbot> ").strip()
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

            await self.handle_command(raw)

    def print_help(self) -> None:
        print(
            """
Supported commands:
  help                       Show this help message.
  openapi                    Show loaded OpenAPI paths.
  ask <question>             Choose an endpoint from OpenAPI and call it.
  login <user> <pass>        Login to /auth/login and store bearer token.
  users [search]             List users using /users/.
  api <METHOD> <PATH> [json] Call low-level /call_api tool.
  call <tool> [json]         Call a named MCP tool with JSON arguments.
  exit                       Quit.

Examples:
  ask show admin users
  api GET /users/ '{"params": {"search": "admin"}}'
"""
        )

    async def handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        if not parts:
            return
        command = parts[0].lower()
        if command == "openapi":
            self.print_openapi()
        elif command == "ask":
            if len(parts) < 2:
                print("Usage: ask <question>")
                return
            question = " ".join(parts[1:])
            await self.ask_question(question)
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
            args = self._load_json_argument(parts[3]) if len(parts) > 3 else {}
            result = await self.call_api(method, path, **args)
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
            await self.ask_question(raw)

    def print_openapi(self) -> None:
        if not self.endpoint_index:
            print("No OpenAPI endpoints loaded.")
            return
        print("OpenAPI endpoints:")
        for endpoint in self.endpoint_index:
            summary = endpoint.get("summary", "")
            print(f" - {endpoint['method']} {endpoint['path']} {summary}")

    async def ask_question(self, question: str) -> None:
        endpoint = self._match_endpoint(question)
        if endpoint is None:
            print("No matching endpoint found. Use 'openapi' to inspect available paths.")
            return
        print(f"Matched endpoint: {endpoint['method']} {endpoint['path']}")
        params = {}
        json_body = None
        if endpoint["method"] == "GET":
            params = self._extract_search_params(question)
        elif endpoint["method"] in {"POST", "PUT", "PATCH"} and endpoint["path"].startswith("/auth/login"):
            username_match = re.search(r"username\s*[:=]?\s*(\w+)", question, re.IGNORECASE)
            password_match = re.search(r"password\s*[:=]?\s*(\w+)", question, re.IGNORECASE)
            if username_match and password_match:
                json_body = {
                    "username": username_match.group(1),
                    "password": password_match.group(1),
                }
            else:
                print("Please provide username and password in the question or use `login <user> <pass>`.")
                return
        request_kwargs = {
            "params": params or None,
            "headers": self._auth_header(),
        }
        if endpoint["path"] in {"/auth/login", "/auth/login-swagger"}:
            request_kwargs["data"] = json_body or {}
            request_kwargs["json_body"] = None
        else:
            request_kwargs["json_body"] = json_body
        response = await self.call_api(
            endpoint["method"],
            endpoint["path"],
            **request_kwargs,
        )
        self.print_result(response)

    def _match_endpoint(self, text: str) -> dict[str, Any] | None:
        if not self.endpoint_index:
            return None
        normalized = text.lower()
        candidates = []
        for endpoint in self.endpoint_index:
            score = 0
            path_text = f"{endpoint['method']} {endpoint['path']}".lower()
            summary_text = endpoint["summary"].lower()
            for token in re.findall(r"\w+", normalized):
                if token in path_text:
                    score += 3
                if token in summary_text:
                    score += 1
            if "user" in normalized or "users" in normalized:
                if endpoint["path"].startswith("/users"):
                    score += 2
            if score > 0:
                candidates.append((score, endpoint))
        if not candidates:
            return None
        sort_tokens = re.findall(r"\w+", text.lower())
        prefer_get = any(token in {"show", "list", "view", "get", "find"} for token in sort_tokens)
        def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, str]:
            score, endpoint = item
            bonus = 0
            if prefer_get and endpoint["method"] == "GET":
                bonus += 5
            if endpoint["method"] in {"POST", "PUT", "PATCH", "DELETE"} and prefer_get:
                bonus -= 5
            return (-score - bonus, 0 if endpoint["method"] == "GET" else 1, endpoint["path"])
        candidates.sort(key=sort_key)
        return candidates[0][1]

    def _extract_search_params(self, question: str) -> dict[str, str] | None:
        match = re.search(r"search(?: for)?\s+([\w@.\-]+)", question, re.IGNORECASE)
        if match:
            return {"search": match.group(1)}
        return {}

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
        result = await self.call_api(
            "GET",
            "/users/",
            params={"search": search} if search else None,
            headers=self._auth_header(),
        )
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
            return {"error": True, "detail": getattr(tool_result, "error", tool_result)}
        return getattr(tool_result, "structuredContent", {}) or {}

    def _auth_header(self) -> dict[str, str] | None:
        if self.last_token:
            return {"Authorization": f"Bearer {self.last_token}"}
        return None

    def _load_json_argument(self, raw: str) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}")
        raise ValueError("JSON argument must be a JSON object")

    def print_result(self, result: dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenAPI-driven chatbot client for SimpleFastAPI MCP wrapper.")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="The MCP server URL for the SimpleFastAPI wrapper.")
    parser.add_argument("--app-api-key", default=os.getenv("SIMPLEFASTAPI_API_KEY"), help="Optional API key to send as X-API-Key.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chatbot = OpenAPIChatbot(url=args.url, app_api_key=args.app_api_key)
    anyio.run(chatbot.run, backend="trio")


if __name__ == "__main__":
    main()
