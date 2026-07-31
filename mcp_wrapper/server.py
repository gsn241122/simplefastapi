from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from fastapi.routing import APIRoute
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


def _collect_routes(router: Any, prefix: str = "") -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    router_routes = getattr(router, "routes", None)
    if not router_routes:
        return routes

    for route in router_routes:
        if isinstance(route, APIRoute):
            if getattr(route, "include_in_schema", True) is False:
                continue
            full_path = prefix + route.path
            if full_path.startswith("/docs") or full_path.startswith("/redoc") or full_path.startswith("/openapi.json"):
                continue

            routes.append({
                "path": full_path,
                "methods": sorted(route.methods or []),
                "name": route.name,
                "summary": getattr(route, "summary", ""),
            })
        elif hasattr(route, "routes"):
            p = getattr(route, "path", getattr(route, "prefix", ""))
            routes.extend(_collect_routes(route, prefix + p))
        elif hasattr(route, "app") and hasattr(route.app, "routes"):
            routes.extend(_collect_routes(route.app, prefix))
        elif hasattr(route, "original_router"):
            routes.extend(_collect_routes(route.original_router, prefix))

    return routes


@mcp.tool
def list_routes() -> list[dict[str, Any]]:
    """List public FastAPI routes available in the wrapped application."""
    return _collect_routes(fastapi_app)


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
