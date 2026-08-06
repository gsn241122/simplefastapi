"""Per-user rate limit + per-chat allowlist (per skill \u00a73.4, \u00a74)."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque


class PerUserRateLimiter:
    """Sliding-window rate limiter (msg / minute per user_id)."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max_per_minute
        self._window: dict[int, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            q = self._window[user_id]
            cutoff = now - 60.0
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self._max:
                return False
            q.append(now)
            return True


def is_chat_allowed(chat_id: int, allowlist: list[int]) -> bool:
    """Empty allowlist means open to all."""
    return not allowlist or chat_id in allowlist
