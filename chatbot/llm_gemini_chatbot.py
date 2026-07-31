from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import traceback
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
# FIX: Model default diubah ke gemini-3.5-flash-lite sesuai permintaan
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
# FIX: Endpoint resmi Gemini API menggunakan :generateContent dengan versi v1beta
DEFAULT_GEMINI_ENDPOINT = os.getenv(
    "GEMINI_API_ENDPOINT",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
)


class GeminiLLM:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        use_api_key_in_query: bool = False,
        endpoint_template: str | None = None,
    ) -> None:
        """Small Gemini client helper."""
        self.api_key = api_key
        self.model = model
        self.use_api_key_in_query = use_api_key_in_query
        self.endpoint = (endpoint_template or DEFAULT_GEMINI_ENDPOINT).format(model=model)

    async def generate(
        self, prompt: str, temperature: float = 0.0, max_output_tokens: int = 512
    ) -> str:
        headers = {"Content-Type": "application/json"}
        params: dict[str, str] | None = None

        # FIX: Gemini API mewajibkan header 'x-goog-api-key' untuk API Key
        if self.use_api_key_in_query:
            params = {"key": self.api_key}
        else:
            headers["x-goog-api-key"] = self.api_key

        # FIX: Struktur payload sesuai standar resmi Gemini API generateContent
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }

        # FIX: Gunakan AsyncClient agar native dengan event loop trio (lebih cepat)
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                response = await client.post(
                    self.endpoint, json=payload, headers=headers, params=params
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as exc:
                resp = exc.response
                status = resp.status_code
                try:
                    body_text = resp.text
                except Exception:
                    body_text = "<unable to read response body>"

                # Fallback: coba versi API alternatif jika 404
                if status == 404:
                    alt_endpoint = None
                    if "/v1beta/" in self.endpoint:
                        alt_endpoint = self.endpoint.replace("/v1beta/", "/v1/")
                    elif "/v1/" in self.endpoint:
                        alt_endpoint = self.endpoint.replace("/v1/", "/v1beta/")

                    if alt_endpoint:
                        try:
                            retry_resp = await client.post(
                                alt_endpoint, json=payload, headers=headers, params=params
                            )
                            retry_resp.raise_for_status()
                            body = retry_resp.json()
                            text = self._extract_text(body)
                            if text is None:
                                raise RuntimeError(
                                    f"Unexpected Gemini response (fallback): {json.dumps(body, indent=2)}"
                                )
                            return text
                        except httpx.HTTPStatusError:
                            pass

                # Fallback ke query parameter jika header gagal
                if not self.use_api_key_in_query and status in (401, 403, 404):
                    try:
                        retry_resp = await client.post(
                            self.endpoint,
                            json=payload,
                            headers={"Content-Type": "application/json"},
                            params={"key": self.api_key},
                        )
                        retry_resp.raise_for_status()
                        body = retry_resp.json()
                        text = self._extract_text(body)
                        if text is None:
                            raise RuntimeError(
                                f"Unexpected Gemini response (query-key fallback): {json.dumps(body, indent=2)}"
                            )
                        return text
                    except httpx.HTTPStatusError:
                        pass

                raise RuntimeError(
                    f"Gemini request failed (status={status}). Response body:\n{body_text}\n"
                    "Pastikan GEMINI_API_KEY valid, model tersedia, dan endpoint benar."
                )

        text = self._extract_text(body)
        if text is None:
            raise RuntimeError(f"Unexpected Gemini response: {json.dumps(body, indent=2)}")
        return text

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        # FIX: Parsing response sesuai struktur resmi Gemini API
        if "candidates" in payload:
            candidates = payload["candidates"]
            if candidates and isinstance(candidates, list):
                candidate = candidates[0]
                if isinstance(candidate, dict):
                    content = candidate.get("content", {})
                    if isinstance(content, dict):
                        parts = content.get("parts", [])
                        if isinstance(parts, list):
                            chunks = [
                                part.get("text", "")
                                for part in parts
                                if isinstance(part, dict) and "text" in part
                            ]
                            return "".join(chunks).strip()

        if "response" in payload and isinstance(payload["response"], str):
            return payload["response"].strip()
        return None


class LLMMCPChatbot:
    def __init__(
        self,
        url: str = DEFAULT_MCP_URL,
        app_api_key: str | None = None,
        gemini_api_key: str | None = None,
        gemini_endpoint: str | None = None,
        gemini_model: str | None = None,
        gemini_use_key_query: bool = False,
    ) -> None:
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
            if self.gemini_api_key:
                print("Gemini API key provided via CLI; enabling LLM features.")
            else:
                print("Gemini API key loaded from environment; enabling LLM features.")
            model = self.gemini_model or DEFAULT_GEMINI_MODEL
            endpoint_template = self.gemini_endpoint or None
            self.llm = GeminiLLM(
                key,
                model=model,
                use_api_key_in_query=self.gemini_use_key_query,
                endpoint_template=endpoint_template,
            )
        else:
            print(
                "Warning: GEMINI_API_KEY is not set. Natural-language LLM features will be disabled."
            )

        async with streamablehttp_client(self.url) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
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
                # FIX: Wrap blocking input() agar tidak membekukan event loop Trio
                raw = (await anyio.to_thread.run_sync(input, "llm-gemini> ")).strip()
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
  ask  <question>        Ask Gemini to select and call an endpoint.
  login  <username> <password>   Authenticate and save bearer token.
  users [search]         List users using the /users/ endpoint.
  switch-model <model>   Switch the Gemini model used by the LLM client.
  list-models [url]      List available models from the Gemini models endpoint.
  api <METHOD> <PATH> [json]     Call raw endpoint using the wrapper.
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
            # FIX: Operasikan JSON secara eksplisit ke json_body, jangan unpack sebagai kwargs
            result = await self.call_api(
                method, path, json_body=data, headers=self._auth_header()
            )
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

        # FIX: generate() sekarang sudah async, langsung await tanpa to_thread
        try:
            response_text = await self.llm.generate(prompt)
        except Exception as exc:
            print(f"LLM request failed: {exc}")
            return

        inference = self._extract_json(response_text)
        if inference is None:
            print("Gemini did not return parseable JSON. Response:\n")
            print(response_text)
            return

        print("\n--- Gemini Inference ---")
        self.print_result(inference)
        print("------------------------")

        method = inference.get("method")
        path = inference.get("path")
        if not method or not path:
            print("Gemini response did not include a valid method/path.")
            return

        # FIX: Penyederhanaan logika penggabungan header
        auth_headers = self._auth_header() or {}
        llm_headers = inference.get("headers") or {}
        final_headers = (
            {**auth_headers, **llm_headers} if (auth_headers or llm_headers) else None
        )

        # Eksekusi API dengan penanganan error yang jelas
        try:
            print(f"Executing API call: {method} {path}...")
            result = await self.call_api(
                method,
                path,
                params=inference.get("params"),
                json_body=inference.get("json_body"),
                data=inference.get("data"),
                headers=final_headers,
            )
            print("\n--- API Execution Result ---")
            self.print_result(result)
            print("----------------------------")
        except Exception as exc:
            print(f"\n[ERROR] Failed to execute API call: {exc}")
            traceback.print_exc()

    def _build_prompt(self, question: str) -> str:
        lines = [
            "You are a backend assistant. Select the best REST API endpoint.",
            "Return EXACTLY one JSON object with keys: method, path, params, json_body, data, headers, explanation.",
            "CRITICAL: If user asks to 'filter' or 'search', check the 'Query params' and populate the 'params' dict.",
            "Return ONLY valid JSON. No markdown, no extra text.",
            "Available endpoints (Format: METHOD PATH [Query Params] : Summary):",
        ]

        # OPTIMASI: Buat representasi endpoint ringkas untuk menghemat token & latensi
        for endpoint in self.endpoints:
            param_hint = ""
            if endpoint.get("parameters"):
                query_params = [
                    p.get("name") for p in endpoint["parameters"] if p.get("in") == "query"
                ]
                if query_params:
                    param_hint = f" [Params: {', '.join(query_params)}]"

            summary = (endpoint.get("summary") or endpoint.get("description") or "")[:60]
            lines.append(f"- {endpoint['method']} {endpoint['path']}{param_hint} : {summary}")

        lines.append(f"\nUser request: {question}")
        return "\n".join(lines)

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
        self.gemini_model = model
        if self.llm is not None:
            self.llm.model = model
            template = self.gemini_endpoint or DEFAULT_GEMINI_ENDPOINT
            try:
                self.llm.endpoint = template.format(model=model)
                print(
                    f"Switched Gemini model to {model} and updated endpoint to {self.llm.endpoint}"
                )
            except Exception as exc:
                print(f"Switched Gemini model to {model}. Failed to update endpoint template: {exc}")
        else:
            print(f"Gemini model set to {model}; will be used when LLM is initialized.")

    async def list_models(self, url: str | None = None) -> None:
        if url is None:
            base_template = self.gemini_endpoint or DEFAULT_GEMINI_ENDPOINT
            if "/models/" in base_template and "{model}" in base_template:
                url = base_template.split("/models/")[0] + "/models"
            else:
                url = base_template.split("/generateContent")[0] + "models"

        headers = {"Content-Type": "application/json"}
        params = None

        # FIX: Gunakan 'x-goog-api-key' di semua cabang autentikasi
        if self.llm is not None and self.llm.use_api_key_in_query:
            params = {"key": self.llm.api_key}
        elif self.llm is not None and self.llm.api_key:
            headers["x-goog-api-key"] = self.llm.api_key
        elif self.gemini_api_key:
            headers["x-goog-api-key"] = self.gemini_api_key
        elif os.getenv("GEMINI_API_KEY"):
            headers["x-goog-api-key"] = os.getenv("GEMINI_API_KEY")

        print(f"Fetching models list from {url}...")
        try:
            # FIX: Gunakan AsyncClient native agar lebih cepat
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                try:
                    result = resp.json()
                except Exception:
                    result = resp.text
            print(json.dumps(result, indent=2) if isinstance(result, dict) else str(result))
        except Exception as exc:
            print(f"Failed to fetch models: {exc}")

    async def login(self, username: str, password: str) -> None:
        print(f"Logging in as {username}...")
        result = await self.call_api(
            "POST",
            "/auth/login",
            data={"username": username, "password": password},
        )
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

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert self.session
        result = await self.session.call_tool(name, arguments)
        return self._normalize_tool_result(result)

    def _normalize_tool_result(self, tool_result: Any) -> dict[str, Any]:
        """Extract a usable dict from an MCP CallToolResult.

        MCP Python SDK exposes results via `.content` (list of content blocks
        such as TextContent), NOT via `structuredContent`.
        """
        if getattr(tool_result, "isError", False):
            content_blocks = getattr(tool_result, "content", []) or []
            error_text = "Unknown error"
            if content_blocks:
                first = content_blocks[0]
                if hasattr(first, "text"):
                    error_text = first.text
                elif isinstance(first, dict):
                    error_text = first.get("text", error_text)
                else:
                    error_text = str(first)
            return {"error": True, "detail": error_text}

        content_blocks = getattr(tool_result, "content", []) or []
        if not content_blocks:
            structured = getattr(tool_result, "structuredContent", None)
            if isinstance(structured, dict):
                return structured
            return {}

        first = content_blocks[0]
        text_data: str | None = None
        if hasattr(first, "text"):
            text_data = first.text
        elif isinstance(first, dict):
            text_data = first.get("text")
        else:
            text_data = str(first)

        if not text_data:
            return {}

        try:
            parsed = json.loads(text_data)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"raw_text": text_data}

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
    # FIX: Hapus semua spasi tersembunyi di dalam string argument argparse
    parser = argparse.ArgumentParser(
        description="LLM-powered OpenAPI assistant for the SimpleFastAPI MCP wrapper."
    )
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL")
    parser.add_argument(
        "--app-api-key",
        default=os.getenv("SIMPLEFASTAPI_API_KEY"),
        help="Optional application API key to send as X-API-Key.",
    )
    parser.add_argument(
        "--gemini-api-key",
        default=os.getenv("GEMINI_API_KEY"),
        help="Optional Gemini API key (overrides GEMINI_API_KEY env).",
    )
    parser.add_argument(
        "--gemini-use-key-query",
        action="store_true",
        help="Send Gemini API key as query param (?key=...) on requests",
    )
    parser.add_argument(
        "--gemini-endpoint",
        default=os.getenv("GEMINI_API_ENDPOINT"),
        help="Optional Gemini endpoint template (use {model} placeholder).",
    )
    parser.add_argument(
        "--gemini-model",
        default=os.getenv("GEMINI_MODEL"),
        help="Optional Gemini model id (overrides GEMINI_MODEL env).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chatbot = LLMMCPChatbot(
        url=args.url,
        app_api_key=args.app_api_key,
        gemini_api_key=args.gemini_api_key,
        gemini_endpoint=args.gemini_endpoint,
        gemini_model=args.gemini_model,
        gemini_use_key_query=args.gemini_use_key_query,
    )
    anyio.run(chatbot.run, backend="trio")


if __name__ == "__main__":
    main()