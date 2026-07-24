from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_engine_kwargs() -> dict:
    """Bangun kwargs engine berdasarkan database backend."""
    kwargs: dict = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite membutuhkan check_same_thread=False untuk penggunaan multi-thread
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.DATABASE_URL, **_build_engine_kwargs())

# Aktifkan WAL mode untuk SQLite agar performa lebih baik
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class untuk semua SQLAlchemy model."""
    pass


def get_db() -> Generator:
    """
    Dependency FastAPI untuk mendapatkan sesi database.

    Yields:
        Session: SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Cek koneksi ke database, digunakan oleh health-check endpoint.

    Returns:
        True jika database bisa dijangkau, False jika tidak.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database connection check failed: %s", exc)
        return False
