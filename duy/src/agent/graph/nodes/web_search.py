from __future__ import annotations

from agent.graph.state import AgentState
from agent.services.searxng_service import format_web_excerpt, search_web


def web_search_node(state: AgentState) -> dict:
    question = (state.get("question") or "").strip()
    if not question:
        return {
            "web_results": [],
            "web_excerpt": "",
            "error": "Câu hỏi trống.",
        }

    try:
        payload = search_web(question)
    except Exception as exc:
        return {
            "web_results": [],
            "web_excerpt": "",
            "error": str(exc),
        }

    results = payload.get("results") or []
    return {
        "web_results": results,
        "web_excerpt": format_web_excerpt(results),
        "error": "",
    }
