from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime

from fastapi import Request, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- In-memory rate limiter sederhana (per IP, per menit) ---
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _is_rate_limited(client_ip: str, limit: int = settings.RATE_LIMIT_PER_MINUTE) -> bool:
    """
    Cek apakah request dari client_ip melebihi rate limit.

    Args:
        client_ip: Alamat IP client.
        limit: Jumlah request maksimum per menit.

    Returns:
        True jika melebihi limit.
    """
    if limit <= 0:
        return False

    now = time.time()
    window_start = now - 60.0

    # Bersihkan request yang sudah kadaluarsa (> 1 menit)
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if ts > window_start
    ]
    _rate_limit_store[client_ip].append(now)

    return len(_rate_limit_store[client_ip]) > limit


class RequestMetadata:
    """Container untuk metadata request HTTP."""

    def __init__(self, request: Request) -> None:
        self.request = request
        self.client_ip = self._get_client_ip()
        self.user_agent: str = request.headers.get("user-agent", "Unknown")
        self.method: str = request.method
        self.path: str = request.url.path
        self.timestamp: datetime = datetime.utcnow()

    def _get_client_ip(self) -> str:
        """Ekstrak IP client dari request headers (mendukung proxy)."""
        forwarded = self.request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = self.request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        return self.request.client.host if self.request.client else "Unknown"


async def request_logger(request: Request, call_next):
    """
    Middleware untuk mencatat request/response dan menerapkan rate limiting.

    Args:
        request: Objek request FastAPI.
        call_next: Callable handler berikutnya di pipeline.

    Returns:
        Response dari handler berikutnya.
    """
    metadata = RequestMetadata(request)
    start_time = time.perf_counter()

    # Rate limiting (lewati endpoint docs dan health check)
    _SKIP_RATE_LIMIT_PATHS = {"/docs", "/redoc", "/openapi.json", "/health", "/"}
    if metadata.path not in _SKIP_RATE_LIMIT_PATHS:
        if _is_rate_limited(metadata.client_ip):
            logger.warning(
                "Rate limit exceeded | ip=%s path=%s",
                metadata.client_ip,
                metadata.path,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down.",
            )

    logger.info(
        "Incoming | method=%s path=%s ip=%s ua=%s",
        metadata.method,
        metadata.path,
        metadata.client_ip,
        metadata.user_agent,
    )

    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "Outgoing | method=%s path=%s status=%d duration_ms=%.2f",
        metadata.method,
        metadata.path,
        response.status_code,
        duration_ms,
    )

    # Tambahkan header timing ke response
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

    return response


async def get_request_metadata(request: Request) -> RequestMetadata:
    """
    Dependency untuk meng-inject metadata request ke endpoint.

    Args:
        request: Objek request FastAPI.

    Returns:
        RequestMetadata instance.
    """
    return RequestMetadata(request)


async def validate_api_key(request: Request) -> str | None:
    """
    Dependency untuk memvalidasi API key dari header X-API-Key.

    Args:
        request: Objek request FastAPI.

    Returns:
        API key yang valid, atau None jika endpoint dikecualikan.

    Raises:
        HTTPException: Jika API key tidak ada atau tidak valid.
    """
    # Lewati validasi untuk endpoint dokumentasi
    _EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/health", "/"}
    if request.url.path in _EXCLUDED_PATHS:
        return None

    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Sertakan header X-API-Key.",
        )

    # Validasi format & nilai API key
    if len(api_key) < 10 or api_key != settings.API_KEY:
        logger.warning("Invalid API key attempt from %s", request.client.host if request.client else "Unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key tidak valid.",
        )

    return api_key
