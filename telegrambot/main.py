"""Entrypoint: boot bot, wire MCP lifecycle, handle signals gracefully."""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from bot.app import build_application
from config import get_settings
from mcp.client import mcp_lifecycle
from mcp.registry import load_registry


async def _run() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    registry = load_registry(Path(__file__).parent / "mcp_server.json")
    async with mcp_lifecycle(registry) as mcp_client:
        logger.info("MCP lifecycle active. servers={}", mcp_client.server_names or "<none>")

        app = build_application(settings)
        # Stash MCP for future tool wiring
        app.bot_data["mcp_client"] = mcp_client

        # Graceful shutdown on SIGINT/SIGTERM
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _stop() -> None:
            logger.info("Shutdown signal received.")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop)
            except NotImplementedError:
                # Windows fallback
                signal.signal(sig, lambda *_: _stop())

        async with app:
            await app.start()
            await app.updater.start_polling()  # type: ignore[union-attr]
            logger.info("Bot is running. Press Ctrl+C to stop.")
            await stop_event.wait()
            await app.updater.stop_polling()  # type: ignore[union-attr]
            await app.stop()


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
