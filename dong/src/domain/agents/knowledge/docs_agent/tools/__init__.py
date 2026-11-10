"""Docs/camera tools — thin adapters; corpus ở `src.domain.agents.knowledge.retrieval`."""
from src.domain.agents.knowledge.docs_agent.tools.docs import (
    answer_from_docs,
    handle_docs_intent,
    retrieve_docs,
)

__all__ = [
    'retrieve_docs',
    'answer_from_docs',
    'handle_docs_intent',
]
