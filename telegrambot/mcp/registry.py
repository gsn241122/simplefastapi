"""Parser for `mcp_server.json`.

Schema is intentionally minimal: `{ "servers": { <name>: <spec> } }`.
Each spec is opaque to the parser and forwarded to the client.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_registry(path: str | Path) -> dict[str, Any]:
    """Load MCP server registry. Returns empty mapping on missing/empty file."""
    p = Path(path)
    if not p.exists():
        return {"servers": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"mcp_server.json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("mcp_server.json root must be an object")
    servers = data.get("servers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcp_server.json `servers` must be an object")
    return data
