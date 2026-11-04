"""Logic dùng chung cho chat / ask / stream — cache TTL và payload."""

from __future__ import annotations

import logging
from typing import Any

from src.api.helpers.cache_helpers import is_identity_query
from src.infra.memory.ttl_cache import make_cache_key, set_ttl_cached
from src.shared.config import settings

logger = logging.getLogger(__name__)


def build_cache_data_from_output(out: Any) -> dict[str, Any]:
    query = getattr(out, "query", None)
    return {
        "question": out.question,
        "answer": out.answer,
        "tool": getattr(query, "tool", "") if query else "",
        "columns": getattr(query, "columns", []) if query else [],
        "rows": getattr(query, "rows", []) if query else [],
        "row_count": getattr(query, "row_count", 0) if query else 0,
        "agent_detail": out.detail,
    }


def store_turn_cache(
    question: str,
    cache_q: str,
    route: str,
    cache_data: dict[str, Any],
    *,
    skip: bool = False,
) -> None:
    if skip:
        return
    if is_identity_query(question) or is_identity_query(cache_q):
        return
    ttl = settings.memory_ttl_seconds
    try:
        set_ttl_cached(make_cache_key(question, route=route), cache_data, ttl=ttl)
        if cache_q and cache_q != question:
            set_ttl_cached(make_cache_key(cache_q, route=route), cache_data, ttl=ttl)
    except Exception as exc:
        logger.warning("Failed to store TTL cache: %s", exc)
