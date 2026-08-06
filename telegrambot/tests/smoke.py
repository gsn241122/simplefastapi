"""Smoke test: configuration + provider + MCP wiring without network.

Run: `python tests/smoke.py` from the `telegrambot/` directory.
Exits non-zero on any failure.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as `python tests/smoke.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _check(label: str, cond: bool, detail: str = "") -> None:
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {label} {detail}")
    if not cond:
        raise SystemExit(1)


async def main() -> None:
    # 1. MCP registry parser on empty file
    from mcp_agent.registry import load_registry

    reg = load_registry(Path(__file__).resolve().parent.parent / "mcp_server.json")
    _check("mcp registry loads", isinstance(reg, dict) and "servers" in reg)

    # 2. MCP client lifecycle starts/closes even with no servers
    from mcp_agent.client import mcp_lifecycle

    async with mcp_lifecycle(reg) as client:
        _check("mcp client starts", client is not None)
        tools = await client.list_tools()
        _check("mcp client lists tools", len(tools) > 0)

    # 3. Provider registry: build each provider with dummy values; do NOT call chat
    from config import Settings
    from llm.registry import build_provider

    base = Settings(
        telegram_bot_token="dummy",
        minimax_api_key="sk-test",
        gemini_api_key="sk-test",
    )
    for name in ("minimax", "gemini", "ollama"):
        p = build_provider(base, name=name)
        _check(f"provider builds: {name}", p.name == name)
        await p.aclose()

    # 4. State store dedupe + sliding window
    from bot.states import StateStore

    s = StateStore(max_turns=2)
    _check("state: first message not duplicate", not s.is_duplicate(1, 100))
    _check("state: same id duplicate", s.is_duplicate(1, 100))
    s.append_turn(1, "hi", "hello")
    s.append_turn(1, "how are you?", "fine")
    s.append_turn(1, "weather?", "sunny")
    # After 3 turns, max 2 turns * 2 = 4 messages kept; oldest dropped
    history = list(s.get(1).history)
    _check("state: sliding window keeps <= 4", len(history) <= 4, f"len={len(history)}")

    # 5. ChatMessage / ChatRequest round-trip
    from llm.base import ChatMessage, ChatRequest

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="halo")],
    )
    payload = [m.model_dump(exclude_none=True) for m in req.messages]
    _check("ChatRequest serializable", payload[0]["role"] == "user")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
