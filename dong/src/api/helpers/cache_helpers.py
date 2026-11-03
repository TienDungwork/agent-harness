"""TTL cache lookup cho HTTP handlers."""

from __future__ import annotations

import logging
from typing import Any

from src.infra.memory.ttl_cache import get_ttl_cached, make_cache_key

logger = logging.getLogger(__name__)

_FOLLOWUP_PREFIXES = ("vậy còn", "thế còn", "còn ", "thì sao", "thì như thế nào", "đối với")


def is_identity_query(text: str) -> bool:
    low = (text or "").lower()
    return any(
        k in low
        for k in (
            "tôi là ai", "toi la ai", "tên tôi", "ten toi", "tôi tên", "toi ten",
            "tôi phụ trách", "toi phu trach", "biết gì về tôi", "biet gi ve toi",
            "vai trò của tôi", "vai tro cua toi",
        )
    )


def is_followup_question(question: str, prev_messages: list) -> bool:
    if not prev_messages:
        return False
    q = (question or "").lower()
    return any(q.startswith(p) or f" {p}" in q for p in _FOLLOWUP_PREFIXES)


def lookup_ttl_cache(question: str) -> dict[str, Any] | None:
    if is_identity_query(question):
        return None
    try:
        return get_ttl_cached(make_cache_key(question))
    except Exception as exc:
        logger.warning("TTL cache lookup failed, degrading to cache miss: %s", exc)
        return None
