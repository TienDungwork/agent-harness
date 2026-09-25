"""Docs module v5 — adapter giữ tương thích graph v4 và re-export từ src.knowledge."""

from __future__ import annotations

from src.knowledge import answer_from_docs, retrieve_docs
from src.llm.schemas import DocsAnswer

__all__ = [
    "retrieve_docs",
    "answer_from_docs",
    "handle_docs_intent",
]


def handle_docs_intent(question: str) -> str:
    """Retrieve YAML cards + DocsAnswer; trả answer_vi cho graph v4."""
    cards = retrieve_docs(question)
    docs_ans: DocsAnswer = answer_from_docs(question, cards)
    return docs_ans.answer_vi
