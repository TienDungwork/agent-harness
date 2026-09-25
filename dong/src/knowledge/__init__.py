"""Knowledge module cho tài liệu VMS (YAML task cards theo phong cách duy)."""

from __future__ import annotations

from src.knowledge.answer import answer_from_docs
from src.knowledge.loader import (
    clear_docs_cache,
    docs_root,
    load_index,
    load_published_cards,
)
from src.knowledge.retrieval import card_excerpt_for_llm, retrieve_docs

__all__ = [
    "clear_docs_cache",
    "docs_root",
    "load_index",
    "load_published_cards",
    "card_excerpt_for_llm",
    "retrieve_docs",
    "answer_from_docs",
]
