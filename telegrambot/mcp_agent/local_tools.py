"""Local tools bridge: expose local skills/ as MCP-style tools.

This module allows local Python scripts under `skills/` to be registered
as MCP-compatible tools without spinning up an external MCP server process.

How it works:
  1. `discover_skill_tools()` scans `skills/*/skill.md` for tool definitions.
  2. Each script becomes a tool that can be invoked like a normal MCP tool.
  3. Output (JSON) is forwarded back to the LLM via the standard MCP protocol.

This integrates with the existing `mcp_agent/tool_adapter.py` to provide
OpenAI-compatible tool specs.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger


class LocalSkillServer:
    """In-process MCP-style server for local skills/ directory.

    Conforms to the interface expected by `mcp_agent.client.MCPClient`:
      - list_tools() -> list[dict]
      - call_tool(name, arguments) -> dict
    """

    def __init__(
        self,
        skills_dir: Path | str,
        *,
        python_path: str | None = None,
        timeout_sec: float = 30.0,
    ) -> None:
        self.skills_dir = Path(skills_dir).resolve()
        self.python_path = python_path or sys_executable()
        self.timeout_sec = timeout_sec
        self.name = "local-skills"
        self._tools_cache: list[dict[str, Any]] | None = None

    def _ensure_discovered(self) -> list[dict[str, Any]]:
        """Discover and cache all skill tools."""
        if self._tools_cache is not None:
            return self._tools_cache
        self._tools_cache = discover_skill_tools(self.skills_dir)
        logger.info(
            "Discovered {} local skill(s) in {}",
            len(self._tools_cache),
            self.skills_dir,
        )
        return self._tools_cache

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP-compatible tool descriptors."""
        tools = self._ensure_discovered()
        # Match shape of MCP client.list_tools() output
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
                "_server": self.name,
            }
            for t in tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a local skill script and return its JSON output."""
        tools = self._ensure_discovered()
        tool = next((t for t in tools if t["name"] == name), None)
        if tool is None:
            return _tool_error(f"Unknown local skill tool: {name!r}")

        script_path = Path(tool["_script_path"])
        if not script_path.exists():
            return _tool_error(f"Skill script missing: {script_path}")

        # Run script with arguments (as CLI args).
        # Using create_subprocess_exec with list arguments is inherently
        # safer than shell=True, as it avoids shell interpretation of
        # special characters in arguments.
        try:
            args_list = []
            for k, v in (arguments or {}).items():
                if isinstance(v, bool):
                    args_list.append(f"--{k}" if v else f"--no-{k}")
                elif isinstance(v, (list, tuple)):
                    for item in v:
                        args_list.extend([f"--{k}", str(item)])
                else:
                    args_list.extend([f"--{k}", str(v)])

            proc = await asyncio.create_subprocess_exec(
                self.python_path,
                str(script_path),
                *args_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=script_path.parent,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_sec
            )
        except asyncio.TimeoutError:
            return _tool_error(f"Skill {name!r} timed out after {self.timeout_sec}s")
        except Exception as exc:  # noqa: BLE001
            return _tool_error(f"Failed to execute skill {name!r}: {exc}")

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip() or "Unknown error"
            return _tool_error(f"Skill {name!r} failed (exit {proc.returncode}): {err}")

        raw = stdout.decode(errors="replace").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Some skills return plain text — wrap it
            data = {"raw": raw}

        return {
            "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
            "isError": False,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sys_executable() -> str:
    """Get the current Python executable path."""
    import sys
    return sys.executable


def _tool_error(msg: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": msg}],
        "isError": True,
    }


# ---------------------------------------------------------------------------
# Skill discovery
# ---------------------------------------------------------------------------

_TOOL_BLOCK_RE = re.compile(
    r"##\s+Tool(?:\s+Definition)?[:\s].*?(?=\n##\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_NAME_RE = re.compile(r"[-_]")  # for safe tool names


def _slugify(name: str) -> str:
    """Normalize a tool name to snake_case / lowercase."""
    s = name.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]", "", s)
    return s or "unnamed_tool"


def discover_skill_tools(skills_dir: Path | str) -> list[dict[str, Any]]:
    """Scan `skills/<skill_name>/` and return tool descriptors.

    Convention:
      skills/<skill_name>/
        ├── skill.md       # documentation + tool definition
        └── <script>.py    # entry point script

    The tool's `name` defaults to `<skill_name>`. Description is read from
    the first non-heading line of `skill.md`.
    """
    skills_dir = Path(skills_dir).resolve()
    if not skills_dir.exists():
        logger.warning("Skills directory not found: {}", skills_dir)
        return []

    tools: list[dict[str, Any]] = []

    for skill_folder in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        skill_name = skill_folder.name
        skill_md = skill_folder / "skill.md"

        # Find the entry script: prefer .py with same name as folder
        script_candidates = [
            skill_folder / f"{skill_name}.py",
            skill_folder / "main.py",
            skill_folder / "run.py",
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)

        # Fallback: any first .py file
        if script_path is None:
            py_files = list(skill_folder.glob("*.py"))
            if py_files:
                script_path = py_files[0]

        if script_path is None:
            logger.debug("No script found for skill: {}", skill_name)
            continue

        # Read description from skill.md (first paragraph after title)
        description = _read_skill_description(skill_md, fallback=skill_name)

        # Build OpenAI-compatible inputSchema (no required args by default)
        input_schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": True,  # allow flexible args
        }

        tools.append({
            "name": _slugify(skill_name),
            "description": description,
            "inputSchema": input_schema,
            "_script_path": str(script_path),
            "_skill_name": skill_name,
        })

    return tools


def _read_skill_description(skill_md: Path, fallback: str) -> str:
    """Extract a short description from skill.md."""
    if not skill_md.exists():
        return fallback
    try:
        text = skill_md.read_text(encoding="utf-8")
    except Exception:
        return fallback

    # Skip title (first H1), grab first non-empty paragraph
    lines = text.splitlines()
    desc_lines: list[str] = []
    past_title = False
    for line in lines:
        stripped = line.strip()
        if not past_title:
            if stripped.startswith("#"):
                past_title = True
                continue
            if stripped:
                past_title = True
        if past_title and stripped and not stripped.startswith("#"):
            desc_lines.append(stripped)
        elif desc_lines:
            # Stop at second heading or empty line after content
            if stripped.startswith("#"):
                break
            if not stripped:
                break
    return " ".join(desc_lines).strip() or fallback