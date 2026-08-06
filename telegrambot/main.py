"""Entrypoint: boot bot, wire MCP lifecycle, handle signals gracefully."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

from loguru import logger

from bot.app import build_application
from config import get_settings
from mcp_agent.client import mcp_lifecycle
from mcp_agent.registry import load_registry

_LOCK_FILE = Path("/tmp/telegrambot.lock")


def _acquire_lock() -> bool:
    """Pastikan hanya satu instansi bot berjalan. Return False jika sudah ada."""
    if _LOCK_FILE.exists():
        pid = _LOCK_FILE.read_text().strip()
        try:
            os.kill(int(pid), 0)  # cek apakah proses masih hidup
            logger.error(
                "Bot sudah berjalan dengan PID {}. Hentikan instansi lain dulu.", pid
            )
            return False
        except (ProcessLookupError, ValueError):
            # Proses sudah mati, hapus lock lama
            _LOCK_FILE.unlink(missing_ok=True)

    _LOCK_FILE.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    _LOCK_FILE.unlink(missing_ok=True)


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
            await app.updater.stop()  # type: ignore[union-attr]
            await app.stop()


def main() -> None:
    if not _acquire_lock():
        sys.exit(1)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
