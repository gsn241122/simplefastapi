from fastapi import APIRouter, Depends
from app.core.responses import StandardJSONResponse
from app.core.database import get_db
from app.core.config import settings
from typing import Any, Dict, Optional
import pkgutil
import importlib
import asyncio
import inspect
import time
import logging

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["Summary"])

# Simple in-memory cache to avoid hitting DB on every request
_CACHE_TTL = 30  # seconds
_module_timeout = 2  # seconds per-module timeout
_summary_cache: Dict[str, Any] = {"timestamp": 0, "data": None}


def _get_redis_client() -> Optional["redis.Redis"]:
    """Create a short-lived Redis client if configured and available."""
    if redis is None or not settings.REDIS_ENABLE:
        return None
    try:
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Redis unavailable for summary aggregator: %s", exc)
        return None


async def _call_summary_callable(func, db, redis_client) -> Any:
    """Call either async or sync summary callable with timeout."""
    try:
        if inspect.iscoroutinefunction(func):
            return await asyncio.wait_for(func(db=db, redis=redis_client), timeout=_module_timeout)
        else:
            # run sync function in threadpool
            return await asyncio.wait_for(asyncio.to_thread(func, db, redis_client), timeout=_module_timeout)
    except asyncio.TimeoutError:
        return {"error": "timeout"}
    except Exception as exc:
        logger.exception("Error calling get_summary: %s", exc)
        return {"error": str(exc)}


@router.get("/", summary="Get summary overview")
async def get_summary(db=Depends(get_db)):
    """Discover modules under app.modules and call their get_summary(db, redis) if available.

    Returns combined per-module summaries and a light aggregation of numeric counts when present.
    """
    now = time.time()
    # Return cached if fresh
    if _summary_cache["data"] is not None and (now - _summary_cache["timestamp"] < _CACHE_TTL):
        return StandardJSONResponse.success(data=_summary_cache["data"], message="Summary retrieved (cached)")

    redis_client = _get_redis_client()

    modules_pkg = importlib.import_module("app.modules")
    found: Dict[str, Any] = {}

    tasks = []
    module_names = []

    # Discover immediate subpackages in app.modules
    for finder, name, ispkg in pkgutil.iter_modules(modules_pkg.__path__):
        # skip the summary module itself to avoid recursion
        if name == "summary":
            continue
        # try package-level get_summary first, then package.routes
        candidates = [f"app.modules.{name}", f"app.modules.{name}.routes"]
        summary_callable = None
        imported_module = None
        for mod_path in candidates:
            try:
                imported_module = importlib.import_module(mod_path)
            except Exception:
                imported_module = None
            if imported_module is not None and hasattr(imported_module, "get_summary"):
                summary_callable = getattr(imported_module, "get_summary")
                break
        if summary_callable is None:
            continue

        module_names.append(name)
        # create task to call callable later
        tasks.append(_call_summary_callable(summary_callable, db, redis_client))

    # Run all module calls concurrently
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Attach results to module name keys
    for name, res in zip(module_names, results):
        found[name] = res

    # Lightweight aggregation for any numeric 'counts' keys returned by modules
    aggregated_counts: Dict[str, int] = {}
    for mod_res in found.values():
        if isinstance(mod_res, dict):
            counts = mod_res.get("counts") or {}
            if isinstance(counts, dict):
                for k, v in counts.items():
                    try:
                        aggregated_counts[k] = aggregated_counts.get(k, 0) + int(v)
                    except Exception:
                        # ignore non-int convertible values
                        pass

    payload = {
        "generated_at": now,
        "modules": found,
        "aggregated_counts": aggregated_counts,
    }

    # update cache
    _summary_cache["timestamp"] = now
    _summary_cache["data"] = payload

    return StandardJSONResponse.success(data=payload, message="Summary retrieved")
