"""Extended registry that mixes remote MCP servers + local skill tools.

This wrapper around `mcp_agent.registry.load_registry` injects the
`local-skills` virtual server based on a `local_skills` block in config,
or auto-detected from the `skills/` directory.

Example mcp_server.json:

    {
      "local_skills": {
        "path": "skills",
        "python": "python3",
        "timeout_sec": 30
      },
      "mcpServers": {
        "fastapi": { ... }
      }
    }
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from mcp_agent.local_tools import LocalSkillServer, discover_skill_tools
from mcp_agent.registry import load_registry


def load_registry_with_local(
    path: str | Path,
    *,
    auto_local: bool = True,
) -> tuple[dict[str, Any], LocalSkillServer | None]:
    """Load mcp_server.json and optionally inject local skill server.

    Returns:
        (registry, local_server) — pass registry to `mcp_lifecycle`,
        and merge `local_server` tool calls into the dispatcher.
    """
    registry = load_registry(path)
    config_dir = Path(path).parent.resolve()

    local_cfg: dict[str, Any] = {}
    raw = Path(path).read_text(encoding="utf-8")
    import json
    try:
        raw_obj = json.loads(raw)
        local_cfg = raw_obj.get("local_skills", {}) or {}
    except Exception:
        local_cfg = {}

    local_server: LocalSkillServer | None = None
    if auto_local:
        skills_path_cfg = local_cfg.get("path", "skills")
        skills_path = (config_dir / skills_path_cfg).resolve()
        if skills_path.exists():
            local_server = LocalSkillServer(
                skills_dir=skills_path,
                python_path=local_cfg.get("python"),
                timeout_sec=float(local_cfg.get("timeout_sec", 30.0)),
            )
            # Pre-warm discovery
            tools = local_server._ensure_discovered()
            logger.info(
                "Local skills server ready: tools={}",
                [t["name"] for t in tools],
            )

    return registry, local_server


def merge_local_tools(
    remote_tools: list[dict[str, Any]],
    local_server: LocalSkillServer | None,
) -> list[dict[str, Any]]:
    """Append local skill tools to a list of MCP tools."""
    if local_server is None:
        return remote_tools
    local_tools = local_server._ensure_discovered()
    out = list(remote_tools)
    for t in local_tools:
        out.append({
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
            "_server": local_server.name,
        })
    return out