from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import textwrap
from typing import Any

# Load .env if present so os.getenv can see values stored there (convenience for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv is optional; if not installed, environment variables must be exported normally
    pass

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DEFAULT_MCP_URL = os.getenv("SIMPLEFASTAPI_MCP_URL", "http://127.0.0.1:8003/mcp")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
DEFAULT_GEMINI_ENDPOINT = os.getenv(
    "GEMINI_API_ENDPOINT",
    "https://generativelanguage.googleapis.com/v1beta2/models/{model}:generate",
)


class GeminiLLM:
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, use_api_key_in_query: bool = False, endpoint_template: str | None = None) -> None:
        """Small Gemini client helper.

        Args:
            api_key: API key or OAuth2 access token (semantics depend on your setup).
            model: model id string to use in endpoint template.
            use_api_key_in_query: if True, send the api_key as a query parameter `?key=...` instead of Authorization header.
            endpoint_template: optional endpoint template to override DEFAULT_GEMINI_ENDPOINT.
        """
        self.api_key = api_key
        self.model = model
        self.use_api_key_in_query = use_api_key_in_query
        self.endpoint = (endpoint_template or DEFAULT_GEMINI_ENDPOINT).format(model=model)

    def generate(self, prompt: str, temperature: float = 0.0, max_output_tokens: int = 512) -> str:
        headers = {"Content-Type": "application/json"}
        params: dict[str, str] | None = None

        # Prefer Authorization bearer token unless configured to send key in query
        if self.use_api_key_in_query:
            params = {"key": self.api_key}
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "prompt": {"text": prompt},
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }

        # Attempt primary endpoint, and fallback heuristics on 404
        with httpx.Client(timeout=60) as client:
            try:
                response = client.post(self.endpoint, json=payload, headers=headers, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Show response body for debugging (but never print API key)
                resp = exc.response
                status = resp.status_code
                body_text = None
                try:
                    body_text = resp.text
                except Exception:
                    body_text = "<unable to read response body>"

                # If 404, try v1 path fallback (some projects expose v1 instead of v1beta2)
                if status == 404:
                    alt_endpoint = None
                    if "/v1beta2/" in self.endpoint:
                        alt_endpoint = self.endpoint.replace("/v1beta2/", "/v1/")
                    elif "/v1/" in self.endpoint:
                        alt_endpoint = self.endpoint.replace("/v1/", "/v1beta2/")

                    if alt_endpoint:
                        try:
                            # Do not print the key; indicate retry attempt
                            # Retry using the same auth mode (query/header)
                            retry_resp = client.post(alt_endpoint, json=payload, headers=headers, params=params)
                            retry_resp.raise_for_status()
                            body = retry_resp.json()
                            text = self._extract_text(body)
                            if text is None:
                                raise RuntimeError(f"Unexpected Gemini response (fallback): {json.dumps(body, indent=2)}")
                            return text
                        except httpx.HTTPStatusError:
                            # Fall through to raise a helpful message below
                            pass

                # If configured to use query param and we attempted header, try query fallback
                if not self.use_api_key_in_query and status in (401, 403, 404):
                    try:
                        retry_resp = client.post(self.endpoint, json=payload, headers={"Content-Type": "application/json"}, params={"key": self.api_key})
                        retry_resp.raise_for_status()
                        body = retry_resp.json()
                        text = self._extract_text(body)
                        if text is None:
                            raise RuntimeError(f"Unexpected Gemini response (query-key fallback): {json.dumps(body, indent=2)}")
                        return text
                    except httpx.HTTPStatusError:
                        pass

                # No successful fallback — raise a clearer error including status and body (no key)
                raise RuntimeError(
                    f"Gemini request failed (status={status}). Response body:\n{body_text}\nSee API access, model availability, and authentication method."
                )

            body = response.json()

        text = self._extract_text(body)
        if text is None:
            raise RuntimeError(f"Unexpected Gemini response: {json.dumps(body, indent=2)}")
        return text

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        if "candidates" in payload:
            candidates = payload["candidates"]
            if candidates and isinstance(candidates, list):
                candidate = candidates[0]
                if isinstance(candidate, dict):
                    if "content" in candidate and isinstance(candidate["content"], list):
                        chunks = [item.get("text", "") for item in candidate["content"] if isinstance(item, dict)]
                        return "".join(chunks).strip()
                    if "text" in candidate:
                        return str(candidate["text"]).strip()
                    if "output" in candidate:
                        return str(candidate["output"]).strip()
        if "outputs" in payload:
            outputs = payload["outputs"]
            if outputs and isinstance(outputs, list):
                output = outputs[0]
                if isinstance(output, dict):
                    if "content" in output and isinstance(output["content"], list):
                        chunks = [item.get("text", "") for item in output["content"] if isinstance(item, dict)]
                        return "".join(chunks).strip()
                    if "text" in output:
                        return str(output["text"]).strip()
        if "response" in payload and isinstance(payload["response"], str):
            return payload["response"].strip()
        return None


class LLMMCPChatbot:
    def __init__(self, url: str = DEFAULT_MCP_URL, app_api_key: str | None = None, gemini_api_key: str | None = None, gemini_endpoint: str | None = None, gemini_model: str | None = None, gemini_use_key_query: bool = False) -> None:
        self.url = url
        self.session: ClientSession | None = None
        self.app_api_key = app_api_key
        self.gemini_api_key = gemini_api_key
        self.gemini_endpoint = gemini_endpoint
        self.gemini_model = gemini_model
        self.gemini_use_key_query = gemini_use_key_query
        self.last_token: str | None = None
        self.openapi: dict[str, Any] | None = None
        self.endpoints: list[dict[str, Any]] = []
        self.llm: GeminiLLM | None = None

    async def run(self) -> None:
        key = self.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if key:
            # do not print the key value; only indicate the source for debug clarity
            if self.gemini_api_key:
                print("Gemini API key provided via CLI; enabling LLM features.")
            else:
                print("Gemini API key loaded from environment; enabling LLM features.")
            model = self.gemini_model or DEFAULT_GEMINI_MODEL
            endpoint_template = self.gemini_endpoint or None
            self.llm = GeminiLLM(key, model=model, use_api_key_in_query=self.gemini_use_key_query, endpoint_template=endpoint_template)
        else:
            print("Warning: GEMINI_API_KEY is not set. Natural-language LLM features will be disabled.")

        async with streamablehttp_client(self.url) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                self.session = session
                await session.initialize()
                print(f"Connected to MCP server at {self.url}")
                await self.load_openapi_schema()
                self.print_intro()
                await self.interactive_loop()

    async def load_openapi_schema(self) -> None:
        response = await self.call_api("GET", "/openapi.json")
        body = response.get("body")
        if not isinstance(body, dict):
            raise RuntimeError("Unable to load OpenAPI schema from /openapi.json")
        self.openapi = body
        self.endpoints = self._extract_endpoints(body)

    def _extract_endpoints(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, info in methods.items():
                if not isinstance(info, dict):
                    continue
                endpoints.append(
                    {
                        "path": path,
                        "method": method.upper(),
                        "summary": info.get("summary", ""),
                        "description": info.get("description", ""),
                        "parameters": info.get("parameters", []),
                        "requestBody": info.get("requestBody"),
                    }
                )
        return endpoints

    def print_intro(self) -> None:
        print("OpenAPI endpoints loaded from wrapped app.")
        print(f"Discovered {len(self.endpoints)} endpoints.")
        print("Type 'help' for commands. Use `ask <question>` to let Gemini choose an endpoint.")

    async def interactive_loop(self) -> None:
        while True:
            try:
                raw = input("llm-gemini> ").strip()
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
  help                   Show this help message.
  openapi                Show loaded OpenAPI endpoints.
  ask <question>         Ask Gemini to select and call an endpoint.
  login <username> <password>   Authenticate and save bearer token.
  users [search]         List users using the /users/ endpoint.
  switch-model <model>    Switch the Gemini model used by the LLM client.
  list-models [url]       List available models from the Gemini models endpoint (optional URL).
  api <METHOD> <PATH> [json]    Call raw endpoint using the wrapper.
  exit                   Quit.
"""
        )

    async def handle_command(self, raw: str) -> None:
        parts = shlex.split(raw)
        if not parts:
            return
        command = parts[0].lower()
        if command == "openapi":
            self.print_endpoints()
        elif command == "ask":
            if len(parts) < 2:
                print("Usage: ask <question>")
                return
            question = " ".join(parts[1:])
            await self.ask(question)
        elif command == "login":
            if len(parts) != 3:
                print("Usage: login <username> <password>")
                return
            await self.login(parts[1], parts[2])
        elif command == "users":
            search = parts[1] if len(parts) == 2 else None
            await self.list_users(search)
        elif command == "switch-model":
            if len(parts) != 2:
                print("Usage: switch-model <model>")
                return
            await self.switch_model(parts[1])
        elif command == "list-models":
            url = parts[1] if len(parts) == 2 else None
            await self.list_models(url)
        elif command == "api":
            if len(parts) < 3:
                print("Usage: api <METHOD> <PATH> [json]")
                return
            method, path = parts[1].upper(), parts[2]
            data = self._load_json_argument(parts[3]) if len(parts) > 3 else None
            result = await self.call_api(method, path, **(data or {}))
            self.print_result(result)
        else:
            await self.ask(raw)
    def print_endpoints(self) -> None:
        print("OpenAPI endpoints:")
        for endpoint in self.endpoints:
            line = f"{endpoint['method']} {endpoint['path']} - {endpoint['summary']}"
            print(line)

    async def ask(self, question: str) -> None:
        if self.llm is None:
            print("GEMINI_API_KEY is not configured. Use `login` or `api` commands instead.")
            return
        prompt = self._build_prompt(question)
        print("Sending question to Gemini...")
        response_text = self.llm.generate(prompt)
        inference = self._extract_json(response_text)
        if inference is None:
            print("Gemini did not return parseable JSON. Response:\n")
            print(response_text)
            return
        self.print_result(inference)
        method = inference.get("method")
        path = inference.get("path")
        if not method or not path:
            print("Gemini response did not include a valid method/path.")
            return
        result = await self.call_api(
            method,
            path,
            params=inference.get("params"),
            json_body=inference.get("json_body"),
            data=inference.get("data"),
            headers={**(self._auth_header() or {}), **(inference.get("headers") or {})} if self._auth_header() or inference.get("headers") else inference.get("headers"),
        )
        self.print_result(result)

    def _build_prompt(self, question: str) -> str:
        lines = [
            "You are a backend assistant with access to a REST API described by OpenAPI.",
            "Select the best endpoint and return exactly one JSON object with the following keys:",
            "  method, path, params, json_body, data, headers, explanation",
            "Only return JSON, do not include markdown or extra text.",
            "Use the path exactly as listed, substituting path parameters when needed.",
            "If the request requires authentication, include the Authorization header if you have a token configured.",
            "If the request has no parameters or body, use null for those fields.",
            "Available endpoints:",
        ]
        for endpoint in self.endpoints:
            lines.append(f"- {endpoint['method']} {endpoint['path']} : {endpoint['summary']}")
        lines.append("\nUser request:")
        lines.append(question)
        prompt = "\n".join(lines)
        return textwrap.dedent(prompt)

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

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            cleaned = self._cleanup_json(text)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return None

    def _cleanup_json(self, text: str) -> str:
        json_text = re.sub(r"^.*?\{", "{", text, flags=re.DOTALL)
        json_text = re.sub(r"\}\s*$", "}", json_text, flags=re.DOTALL)
        return json_text

    async def switch_model(self, model: str) -> None:
        """Switch the model used by the Gemini LLM. Updates endpoint if an endpoint template is set."""
        self.gemini_model = model
        if self.llm is not None:
            self.llm.model = model
            # recompute endpoint from template if available
            template = self.gemini_endpoint or DEFAULT_GEMINI_ENDPOINT
            try:
                self.llm.endpoint = (template).format(model=model)
                print(f"Switched Gemini model to {model} and updated endpoint to {self.llm.endpoint}")
            except Exception as exc:
                print(f"Switched Gemini model to {model}. Failed to update endpoint template: {exc}")
        else:
            print(f"Gemini model set to {model}; will be used when LLM is initialized.")

    async def list_models(self, url: str | None = None) -> None:
        """List models from the Gemini models endpoint. If url is None, construct from endpoint template or default."""
        # Determine URL
        if url is None:
            base_template = self.gemini_endpoint or DEFAULT_GEMINI_ENDPOINT
            if '/models/' in base_template and '{model}' in base_template:
                url = base_template.split('/models/')[0] + '/models'
                # if template contains version segment like v1 or v1beta2, keep it
            else:
                url = base_template.split('/generate')[0] + 'models'
        # Prepare auth
        headers = {"Content-Type": "application/json"}
        params = None
        if self.llm is not None and self.llm.use_api_key_in_query:
            params = {"key": self.llm.api_key}
        elif self.llm is not None and self.llm.api_key:
            headers["Authorization"] = f"Bearer {self.llm.api_key}"
        elif self.gemini_api_key:
            # not yet initialized llm but have key via CLI
            headers["Authorization"] = f"Bearer {self.gemini_api_key}"
        elif os.getenv('GEMINI_API_KEY'):
            headers["Authorization"] = f"Bearer {os.getenv('GEMINI_API_KEY')}"
        print(f"Fetching models list from {url}...")
        try:
            # run blocking httpx in thread to avoid blocking event loop
            import anyio
            def _fetch():
                import httpx
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    try:
                        return resp.json()
                    except Exception:
                        return resp.text
            result = await anyio.to_thread.run_sync(_fetch)
            print(json.dumps(result, indent=2) if isinstance(result, dict) else str(result))
        except Exception as exc:
            print(f"Failed to fetch models: {exc}")

    async def login(self, username: str, password: str) -> None:
        print(f"Logging in as {username}...")
        result = await self.call_api("POST", "/auth/login", data={"username": username, "password": password})
        self.print_result(result)
        body = result.get("body")
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
        return self._normalize_tool_result(result)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.session
        result = await self.session.call_tool(name, arguments)
        return self._normalize_tool_result(result)

    def _normalize_tool_result(self, tool_result: Any) -> dict[str, Any]:
        if getattr(tool_result, "isError", False):
            return {"error": True, "detail": getattr(tool_result, "error", tool_result)}
        return getattr(tool_result, "structuredContent", {}) or {}

    def _auth_header(self) -> dict[str, str] | None:
        headers: dict[str, str] = {}
        if self.last_token:
            headers["Authorization"] = f"Bearer {self.last_token}"
        if self.app_api_key:
            headers["X-API-Key"] = self.app_api_key
        return headers or None

    def print_result(self, result: dict[str, Any]) -> None:
        print(json.dumps(result, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-powered OpenAPI assistant for the SimpleFastAPI MCP wrapper.")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL")
    parser.add_argument("--app-api-key", default=os.getenv("SIMPLEFASTAPI_API_KEY"), help="Optional application API key to send as X-API-Key.")
    parser.add_argument("--gemini-api-key", default=os.getenv("GEMINI_API_KEY"), help="Optional Gemini API key (overrides GEMINI_API_KEY env).")
    parser.add_argument("--gemini-use-key-query", action="store_true", help="Send Gemini API key as query param (?key=...) on requests")
    parser.add_argument("--gemini-endpoint", default=os.getenv("GEMINI_API_ENDPOINT"), help="Optional Gemini endpoint template (use {model} placeholder).")
    parser.add_argument("--gemini-model", default=os.getenv("GEMINI_MODEL"), help="Optional Gemini model id (overrides GEMINI_MODEL env).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chatbot = LLMMCPChatbot(url=args.url, app_api_key=args.app_api_key, gemini_api_key=args.gemini_api_key, gemini_use_key_query=args.gemini_use_key_query)
    anyio.run(chatbot.run, backend="trio")


if __name__ == "__main__":
    main()
