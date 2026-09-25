"""TTL Cache for responses — 300s memory cache before graph execution."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_ttl_cache: dict[str, dict[str, Any]] = {}
_cache = _ttl_cache
_ttl_lock = threading.Lock()


def _is_cache_enabled() -> bool:
    from src.config import settings

    if hasattr(settings, "ttl_cache_enabled"):
        return bool(settings.ttl_cache_enabled)
    return bool(getattr(settings, "cache_enabled", True))


def _get_ttl_seconds() -> int:
    from src.config import settings

    return int(getattr(settings, "memory_ttl_seconds", 300))


def make_cache_key(question: str, route: str = "") -> str:
    """Generate SHA-256 cache key from normalized question and optional route.

    Question is stripped and lowercased. When route is provided, it is also
    normalized and combined into the key representation.
    """
    norm_q = (question or "").strip().lower()
    q_hash = hashlib.sha256(norm_q.encode("utf-8")).hexdigest()
    norm_route = (str(route) if route else "").strip().lower()
    if norm_route:
        r_hash = hashlib.sha256(norm_route.encode("utf-8")).hexdigest()[:16]
        return f"{q_hash}:{r_hash}"
    return q_hash


def get_ttl_cached(key: str) -> dict | None:
    """Retrieve cached payload if valid and within TTL duration.

    Respects settings.memory_ttl_seconds (default 300) and settings.cache_enabled / ttl_cache_enabled.
    Supports exact key match or question prefix match when route was omitted.
    On unexpected errors (lock error, corrupted entry, bad data shape), returns None (miss).
    """
    try:
        if not _is_cache_enabled():
            return None
        if _get_ttl_seconds() <= 0:
            return None

        now = time.time()
        with _ttl_lock:
            # 1. Exact match
            entry = _ttl_cache.get(key)
            if entry is not None:
                if isinstance(entry, dict) and now < entry.get("expire_at", 0):
                    return entry.get("data")
                _ttl_cache.pop(key, None)
                return None

            # 2. Prefix lookup if key is question-only (no route delimiter ':')
            if ":" not in key:
                prefix = f"{key}:"
                for k, entry in list(_ttl_cache.items()):
                    if k.startswith(prefix):
                        if isinstance(entry, dict) and now < entry.get("expire_at", 0):
                            return entry.get("data")
                        _ttl_cache.pop(k, None)

        return None
    except Exception as exc:
        logger.warning("get_ttl_cached error, degrading to cache miss: %s", exc)
        return None


def set_ttl_cached(key: str, data: dict, ttl: int | None = None) -> None:
    """Store data dictionary in TTL cache with expiration time."""
    try:
        if not _is_cache_enabled():
            return
        if ttl is None:
            ttl = _get_ttl_seconds()
        if ttl <= 0:
            return

        expire_at = time.time() + ttl
        with _ttl_lock:
            _ttl_cache[key] = {
                "data": data,
                "expire_at": expire_at,
            }
    except Exception as exc:
        logger.warning("set_ttl_cached error, degrading silently: %s", exc)


def clear_ttl_cache() -> None:
    """Clear all entries in TTL cache (primarily for testing)."""
    with _ttl_lock:
        _ttl_cache.clear()
