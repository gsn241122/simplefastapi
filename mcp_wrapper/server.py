from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from fastmcp import FastMCP

from app.main import app as fastapi_app

mcp = FastMCP("SimpleFastAPI MCP Wrapper")
client = TestClient(fastapi_app)


def _format_response(response: Any) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        body = response.text

    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }


@mcp.tool
def health_check() -> dict[str, Any]:
    """Return the application health status by calling the FastAPI health endpoint."""
    response = client.get("/health")
    return _format_response(response)


@mcp.tool
def list_routes() -> list[dict[str, Any]]:
    """List public FastAPI routes available in the wrapped application."""
    routes: list[dict[str, Any]] = []
    for route in fastapi_app.routes:
        if getattr(route, "include_in_schema", True) is False:
            continue
        if route.path.startswith("/docs") or route.path.startswith("/redoc"):
            continue

        routes.append({
            "path": route.path,
            "methods": sorted(route.methods or []),
            "name": route.name,
            "summary": getattr(route, "summary", ""),
        })

    return routes


@mcp.tool
def call_api(
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the wrapped FastAPI application through a generic request tool."""
    response = client.request(
        method.upper(),
        path,
        json=json_body,
        params=params,
        headers=headers,
        data=data,
    )
    return _format_response(response)


if __name__ == "__main__":
    port = int(os.getenv("FASTMCP_PORT", os.getenv("MCP_PORT", "8003")))
    mcp.run(transport="http", port=port)
