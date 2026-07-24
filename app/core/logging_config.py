from __future__ import annotations

import logging
import logging.config
from typing import Any

from app.core.config import settings


def setup_logging() -> None:
    """
    Konfigurasi structured logging untuk aplikasi.

    Format log menggunakan key=value agar mudah di-parse oleh
    sistem monitoring seperti Loki, Datadog, atau ELK stack.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": (
                    "%(asctime)s level=%(levelname)s "
                    "logger=%(name)s %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
            "simple": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured" if settings.is_production else "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
        "loggers": {
            # Kurangi verbosity library eksternal
            "uvicorn": {"level": "WARNING"},
            "uvicorn.error": {"level": "ERROR"},
            "sqlalchemy.engine": {
                "level": "DEBUG" if settings.DEBUG else "WARNING",
                "propagate": True,
            },
        },
    }

    logging.config.dictConfig(logging_config)
