"""Entrypoint: boot bot, wire MCP lifecycle, handle signals gracefully."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from bot.app import build_application
from config import get_settings
from mcp_agent.client import mcp_lifecycle
from mcp_agent.registry import load_registry

_LOCK_FILE = Path(__file__).parent / ".telegrambot.lock"


def _acquire_lock() -> bool:
    """Pastikan hanya satu instansi bot berjalan. Return False jika sudah ada."""
    if _LOCK_FILE.exists():
        try:
            pid = int(_LOCK_FILE.read_text().strip())
            os.kill(pid, 0)  # cek apakah proses masih hidup
            logger.error(
                "Bot sudah berjalan dengan PID {}. Hentikan instansi lain dulu.", pid
            )
            return False
        except (ProcessLookupError, ValueError):
            # Proses sudah mati, hapus lock lama
            _release_lock()
        except OSError as err:
            logger.warning("Gagal menguji status PID lock: {}", err)
            _release_lock()

    try:
        # Atomic lock file creation untuk mencegah race condition
        fd = os.open(_LOCK_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return True
    except FileExistsError:
        logger.error(
            "Race condition terdeteksi: lockfile {} baru saja dibuat oleh instansi lain.",
            _LOCK_FILE,
        )
        return False
    except OSError as err:
        logger.error("Gagal menulis lockfile {}: {}", _LOCK_FILE, err)
        return False


def _release_lock() -> None:
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except OSError as err:
        logger.warning("Gagal menghapus lockfile {}: {}", _LOCK_FILE, err)


def _asyncio_exception_handler(
    loop: asyncio.AbstractEventLoop, context: dict[str, Any]
) -> None:
    """Log unhandled exception dari background tasks asyncio."""
    exception = context.get("exception")
    msg = context.get("message", "Unhandled asyncio exception")
    if exception:
        logger.error("Unhandled async exception: {} | Exception: {}", msg, exception)
    else:
        logger.error("Unhandled async exception: {}", msg)


async def _run() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    pid = os.getpid()
    logger.info("Starting bot entrypoint. PID={} lockfile={}", pid, _LOCK_FILE)

    mcp_config_path = Path(__file__).parent / "mcp_server.json"
    if not mcp_config_path.exists():
        logger.critical("File konfigurasi MCP tidak ditemukan di: {}", mcp_config_path)
        sys.exit(1)

    registry = load_registry(mcp_config_path)
    async with mcp_lifecycle(registry) as mcp_client:
        logger.info("MCP lifecycle active. servers={}", mcp_client.server_names or "<none>")

        app = build_application(settings)
        # Stash MCP for future tool wiring
        app.bot_data["mcp_client"] = mcp_client

        # Setup exception handler & graceful shutdown on SIGINT/SIGTERM
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_asyncio_exception_handler)

        stop_event = asyncio.Event()

        def _stop() -> None:
            logger.info("Shutdown signal received.")
            stop_event.set()

        registered_signals: list[signal.Signals] = []
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop)
                registered_signals.append(sig)
            except NotImplementedError:
                # Windows fallback
                signal.signal(sig, lambda *_: _stop())

        try:
            async with app:
                await app.start()
                if app.updater:
                    await app.updater.start_polling()
                logger.info("Bot is running. Press Ctrl+C to stop.")
                await stop_event.wait()
                if app.updater and app.updater.running:
                    await app.updater.stop()
                await app.stop()
        finally:
            for sig in registered_signals:
                try:
                    loop.remove_signal_handler(sig)
                except Exception:
                    pass


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


