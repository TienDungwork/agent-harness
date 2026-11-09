"""Knowledge team state."""

from __future__ import annotations

from typing import Any, TypedDict

from src.infra.llm.schemas import RewrittenQuestion


class KnowledgeTeamState(TypedDict, total=False):
    question: str
    rewritten: RewrittenQuestion
    intent: str
    user_id: str
    session_id: str
    answer: str
    docs_answer: dict
    orchestrator_multi_active: bool
    events: list[dict]
    result: Any
