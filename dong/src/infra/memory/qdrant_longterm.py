"""Long-term memory — Qdrant vector store (không fallback)."""

from __future__ import annotations

import logging
import time
import uuid
from functools import lru_cache
from typing import Any

from src.shared.config import settings

logger = logging.getLogger(__name__)


class LongTermMemoryError(RuntimeError):
    """Qdrant / embedding chưa sẵn sàng cho long-term memory."""


def _require_enabled() -> None:
    if not settings.long_term_memory_enabled:
        return
    if not settings.qdrant_configured:
        raise LongTermMemoryError("Long-term bật nhưng thiếu QDRANT_URL.")


def _embedding_api_key() -> str:
    for key in settings.api_keys:
        if key and key != "not-needed":
            return key
    if settings.llm_api_key and settings.llm_api_key.strip():
        return settings.llm_api_key.strip()
    raise LongTermMemoryError("Thiếu OpenAI API key cho embedding (OPENAI_API_KEYS / LLM_API_KEY).")


@lru_cache(maxsize=1)
def get_qdrant_client() -> Any:
    from qdrant_client import QdrantClient

    url = settings.qdrant_url.strip()
    api_key = (settings.qdrant_api_key or "").strip() or None
    try:
        client = QdrantClient(url=url, api_key=api_key, timeout=5.0, check_compatibility=False)
        client.get_collections()
        return client
    except Exception as exc:
        raise LongTermMemoryError(f"Không kết nối Qdrant tại {url}: {exc}") from exc


def _ensure_collection(client: Any) -> None:
    from qdrant_client.models import Distance, VectorParams

    name = settings.qdrant_collection
    dim = int(settings.embedding_dim)
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


def _embed_texts(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=_embedding_api_key())
    response = client.embeddings.create(model=settings.embedding_model, input=texts)
    return [item.embedding for item in response.data]


def save_to_long_term(user_id: str, fact: str, category: str = "general") -> None:
    if not settings.long_term_memory_enabled:
        return
    _require_enabled()
    uid = (user_id or "").strip()
    text = (fact or "").strip()
    if not uid or not text:
        return

    client = get_qdrant_client()
    _ensure_collection(client)
    vectors = _embed_texts([text])
    if not vectors or not vectors[0]:
        raise LongTermMemoryError("Embedding rỗng — không lưu được fact.")

    from qdrant_client.models import PointStruct

    client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vectors[0],
                payload={
                    "text": text,
                    "user_id": uid,
                    "category": (category or "general").strip(),
                    "ts": time.time(),
                },
            )
        ],
    )


def recall_long_term(user_id: str, query: str, k: int = 3) -> list[str]:
    if not settings.long_term_memory_enabled:
        return []
    _require_enabled()
    uid = (user_id or "").strip()
    if not uid:
        return []
    limit = max(int(k), 1)

    client = get_qdrant_client()
    col = settings.qdrant_collection
    if not client.collection_exists(col):
        return []

    q = (query or "").strip() or "user profile facts"
    vector = _embed_texts([q])[0]

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    response = client.query_points(
        collection_name=col,
        query=vector,
        query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=uid))]),
        limit=limit,
    )
    return [
        str(h.payload.get("text", ""))
        for h in response.points
        if h.payload and h.payload.get("text")
    ]


def clear_long_term(user_id: str | None = None) -> None:
    if not settings.long_term_memory_enabled:
        return
    _require_enabled()
    client = get_qdrant_client()
    col = settings.qdrant_collection
    if not client.collection_exists(col):
        return

    from qdrant_client.models import FieldCondition, Filter, MatchValue, FilterSelector

    if user_id and str(user_id).strip():
        uid = str(user_id).strip()
        client.delete(
            collection_name=col,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=uid))])
            ),
        )
    else:
        client.delete_collection(col)
        _ensure_collection(client)
