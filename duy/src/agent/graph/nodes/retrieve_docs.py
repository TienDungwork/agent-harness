from __future__ import annotations

import json

from agent.graph.state import AgentState
from agent.knowledge.retrieval import card_excerpt_for_llm, retrieve_docs


def retrieve_docs_node(state: AgentState) -> dict:
    question = state.get("question") or ""
    intent = state.get("intent") or ""
    prefer = None
    if intent == "how_to":
        prefer = "how_to"
    elif intent == "troubleshoot":
        prefer = "troubleshooting"
    elif intent == "concept":
        prefer = "concept"

    cards = retrieve_docs(question, limit=2, prefer_type=prefer)
    excerpts = [card_excerpt_for_llm(c) for c in cards]
    return {
        "relevant_docs": excerpts,
        "docs_excerpt": json.dumps(excerpts, ensure_ascii=False, indent=2)
        if excerpts
        else "Không tìm thấy card tài liệu phù hợp.",
        "error": "",
    }
