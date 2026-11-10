"""Docs adapter — re-export corpus `agents.knowledge.retrieval` + handle_docs_intent."""
from __future__ import annotations

from src.domain.agents.knowledge.retrieval import answer_from_docs, retrieve_docs
from src.infra.llm.schemas import DocsAnswer

__all__ = [
    'retrieve_docs',
    'answer_from_docs',
    'handle_docs_intent',
]


def handle_docs_intent(question: str) -> str:
    """Retrieve YAML cards + DocsAnswer; trả answer_vi."""
    cards = retrieve_docs(question)
    docs_ans: DocsAnswer = answer_from_docs(question, cards)
    return docs_ans.answer_vi
