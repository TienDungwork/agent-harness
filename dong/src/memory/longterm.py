"""Long-term memory store by user_id with PostgreSQL persistence and in-memory fallback.

Tương thích kiến trúc Memory & Context Engineering (v9):
- Bền vững hóa: Lưu trữ facts vào PostgreSQL (`user_memories`).
- Token Overlap Ranking: Xếp hạng facts liên quan nhất với truy vấn.
- Graceful Degradation: Tự động fallback sang in-memory khi không có DB.
- Zero Legacy Code: Loại bỏ hoàn toàn mã vector giả lập và thư viện ngoài không cần thiết.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from src.memory.db import get_memory_connection, is_postgres_configured

logger = logging.getLogger(__name__)

# In-memory fallback store: list of (user_id, fact, category, timestamp)
_FALLBACK_STORE: list[tuple[str, str, str, float]] = []
_LONG_TERM_STORE = _FALLBACK_STORE  # Backward compatibility reference


def _tokenize(text: str) -> set[str]:
    """Tách từ đơn giản và loại bỏ dấu câu cho việc tính keyword overlap."""
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    tokens = [w for w in cleaned.split() if w]
    long_tokens = {w for w in tokens if len(w) > 2}
    if long_tokens:
        return long_tokens
    mid_tokens = {w for w in tokens if len(w) > 1}
    if mid_tokens:
        return mid_tokens
    return set(tokens)


def save_to_long_term(user_id: str, fact: str, category: str = "general") -> None:
    """Lưu một fact dài hạn theo user_id vào PostgreSQL (fallback in-memory).

    Bỏ qua nếu user_id hoặc fact rỗng, strip fact trước khi lưu.
    Không bao giờ ném ngoại lệ ra caller.
    """
    try:
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            return
        if not fact or not isinstance(fact, str):
            return
        cleaned_fact = fact.strip()
        if not cleaned_fact:
            return

        uid = user_id.strip()
        cat = (category or "general").strip()

        # 1. Thử lưu vào PostgreSQL nếu cấu hình DB khả dụng
        if is_postgres_configured():
            try:
                with get_memory_connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO user_memories (user_id, fact, category, created_at, updated_at)
                            VALUES (%s, %s, %s, NOW(), NOW());
                            """,
                            (uid, cleaned_fact, cat),
                        )
                return
            except Exception as db_exc:
                logger.warning("save_to_long_term DB failed, falling back to in-memory: %s", db_exc)

        # 2. In-memory fallback store
        _LONG_TERM_STORE.append((uid, cleaned_fact, cat, time.time()))
    except Exception as exc:
        logger.warning("save_to_long_term failed: %s", exc)


def recall_long_term(user_id: str, query: str, k: int = 3) -> list[str]:
    """Truy xuất tối đa k memory liên quan nhất tới query, lọc CHỈ theo user_id.

    Xếp hạng dựa trên token overlap từ khóa.
    Không bao giờ ném ngoại lệ ra caller.
    """
    try:
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            return []
        if k <= 0:
            return []

        uid = user_id.strip()

        # 1. Thử đọc từ PostgreSQL nếu cấu hình DB khả dụng
        if is_postgres_configured():
            try:
                with get_memory_connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT fact, created_at
                            FROM user_memories
                            WHERE user_id = %s
                            ORDER BY created_at DESC;
                            """,
                            (uid,),
                        )
                        rows = cur.fetchall()
                        if rows:
                            query_words = _tokenize(query)
                            mine = [
                                (r[0], r[1].timestamp() if hasattr(r[1], "timestamp") else time.time())
                                for r in rows
                                if r and r[0]
                            ]
                            scored = sorted(
                                mine,
                                key=lambda item: len(query_words & _tokenize(item[0])),
                                reverse=True,
                            )
                            return [fact for fact, _ in scored[:k] if fact]
                        return []
            except Exception as db_exc:
                logger.warning("recall_long_term DB failed, falling back to in-memory: %s", db_exc)

        # 2. In-memory fallback store
        mine = []
        for item in _LONG_TERM_STORE:
            if item[0] == uid:
                fact = item[1]
                ts = item[3] if len(item) > 3 else (item[2] if len(item) > 2 else time.time())
                mine.append((fact, ts))

        if not mine:
            return []

        query_words = _tokenize(query)
        scored = sorted(
            reversed(mine),
            key=lambda item: len(query_words & _tokenize(item[0])),
            reverse=True,
        )
        return [fact for fact, _ in scored[:k] if fact]
    except Exception as exc:
        logger.warning("recall_long_term failed: %s", exc)
        return []


def clear_long_term(user_id: str | None = None) -> None:
    """Xóa bộ nhớ (dùng cho testing/reset). Nếu user_id=None, xóa toàn bộ."""
    global _LONG_TERM_STORE
    try:
        # 1. Luôn dọn dẹp in-memory fallback store
        if user_id is None:
            if hasattr(_LONG_TERM_STORE, "clear"):
                _LONG_TERM_STORE.clear()
            else:
                _LONG_TERM_STORE = []
        else:
            uid = user_id.strip()
            _LONG_TERM_STORE[:] = [item for item in _LONG_TERM_STORE if item[0] != uid]

        # 2. Thử xóa trên PostgreSQL nếu cấu hình DB khả dụng
        if is_postgres_configured():
            try:
                with get_memory_connection(autocommit=True) as conn:
                    with conn.cursor() as cur:
                        if user_id is None:
                            cur.execute("DELETE FROM user_memories;")
                        else:
                            cur.execute("DELETE FROM user_memories WHERE user_id = %s;", (user_id.strip(),))
            except Exception as db_exc:
                logger.warning("clear_long_term DB failed: %s", db_exc)
    except Exception as exc:
        logger.warning("clear_long_term failed: %s", exc)
        _LONG_TERM_STORE = []
