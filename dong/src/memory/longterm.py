"""Long-term memory store by user_id (in-memory MVP, optional Qdrant)."""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

# In-memory store: list of (user_id, fact, timestamp)
_LONG_TERM_STORE: list[tuple[str, str, float]] = []


def _use_qdrant() -> bool:
    """Kiểm tra có cấu hình QDRANT_URL và thư viện qdrant-client hay không."""
    qdrant_url = os.environ.get("QDRANT_URL", "").strip()
    if not qdrant_url:
        return False
    try:
        import qdrant_client  # noqa: F401
        return True
    except ImportError:
        return False


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


def save_to_long_term(user_id: str, fact: str) -> None:
    """Lưu một fact dài hạn theo user_id vào memory store.

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

        if _use_qdrant():
            try:
                import uuid
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, PointStruct, VectorParams

                url = os.environ.get("QDRANT_URL", "").strip()
                client = QdrantClient(location=":memory:") if url == ":memory:" else QdrantClient(url=url)
                collection_name = os.environ.get("AGENT_MEMORY_COLLECTION", "user_memory")
                if not client.collection_exists(collection_name):
                    client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=1, distance=Distance.COSINE),
                    )
                client.upsert(
                    collection_name=collection_name,
                    points=[
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=[0.0],
                            payload={"text": cleaned_fact, "user_id": uid, "ts": time.time()},
                        )
                    ],
                )
                return
            except Exception:
                pass  # Fallback to in-memory on error

        _LONG_TERM_STORE.append((uid, cleaned_fact, time.time()))
    except Exception as exc:
        logger.warning("save_to_long_term failed: %s", exc)


def recall_long_term(user_id: str, query: str, k: int = 3) -> list[str]:
    """Truy xuất tối đa k memory liên quan nhất tới query, lọc CHỈ theo user_id.

    Không bao giờ ném ngoại lệ ra caller.
    """
    try:
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            return []
        if k <= 0:
            return []

        uid = user_id.strip()

        if _use_qdrant():
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import FieldCondition, Filter, MatchValue

                url = os.environ.get("QDRANT_URL", "").strip()
                client = QdrantClient(location=":memory:") if url == ":memory:" else QdrantClient(url=url)
                collection_name = os.environ.get("AGENT_MEMORY_COLLECTION", "user_memory")
                if client.collection_exists(collection_name):
                    points, _ = client.scroll(
                        collection_name=collection_name,
                        scroll_filter=Filter(
                            must=[FieldCondition(key="user_id", match=MatchValue(value=uid))]
                        ),
                        limit=100,
                    )
                    mine = [(p.payload.get("text", ""), p.payload.get("ts", 0.0)) for p in points if p.payload]
                    if mine:
                        query_words = _tokenize(query)
                        scored = sorted(
                            reversed(mine),
                            key=lambda item: len(query_words & _tokenize(item[0])),
                            reverse=True,
                        )
                        return [fact for fact, _ in scored[:k] if fact]
            except Exception:
                pass  # Fallback to in-memory on error

        mine = [(fact, ts) for u, fact, ts in _LONG_TERM_STORE if u == uid]
        if not mine:
            return []

        query_words = _tokenize(query)

        scored = sorted(
            reversed(mine),
            key=lambda item: len(query_words & _tokenize(item[0])),
            reverse=True,
        )
        return [fact for fact, _ in scored[:k]]
    except Exception as exc:
        logger.warning("recall_long_term failed: %s", exc)
        return []


def clear_long_term(user_id: str | None = None) -> None:
    """Xóa bộ nhớ (dùng cho testing/reset). Nếu user_id=None, xóa toàn bộ."""
    global _LONG_TERM_STORE
    if user_id is None:
        _LONG_TERM_STORE.clear()
    else:
        uid = user_id.strip()
        _LONG_TERM_STORE[:] = [item for item in _LONG_TERM_STORE if item[0] != uid]
