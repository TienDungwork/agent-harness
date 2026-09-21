from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.config.settings import get_settings
from agent.graph.nodes.answer_from_docs import answer_from_docs
from agent.graph.nodes.answer_from_web import answer_from_web
from agent.graph.nodes.classify_intent import classify_intent
from agent.graph.nodes.execute_sql import execute_sql
from agent.graph.nodes.generate_sql import generate_sql
from agent.graph.nodes.repair_sql import repair_sql
from agent.graph.nodes.render_chart import render_chart
from agent.graph.nodes.respond import respond
from agent.graph.nodes.respond_without_sql import respond_without_sql
from agent.graph.nodes.retrieve_docs import retrieve_docs_node
from agent.graph.nodes.retrieve_schema import retrieve_schema
from agent.graph.nodes.web_search import web_search_node
from agent.graph.nodes.validate_sql import validate_sql_node
from agent.graph.state import AgentState
from agent.llm.profiles import resolve_profile
from agent.llm.runtime import reset_llm_profile, set_llm_profile

_DOCS_INTENTS = frozenset({"how_to", "troubleshoot", "concept"})
_WEB_INTENTS = frozenset({"web_search"})


def _after_intent(state: AgentState) -> str:
    intent = state.get("intent") or ""
    if intent == "query_db":
        return "retrieve_schema"
    if intent in _DOCS_INTENTS:
        return "retrieve_docs"
    if intent in _WEB_INTENTS:
        return "web_search"
    if (state.get("answer") or "").strip():
        return "done"
    return "respond_without_sql"


def _after_validate(state: AgentState) -> str:
    validation = state.get("sql_validation") or {}
    if validation.get("ok"):
        return "execute_sql"
    if int(state.get("repair_count") or 0) < get_settings().sql_repair_max:
        return "repair_sql"
    return "respond"


def _after_execute(state: AgentState) -> str:
    if state.get("error") and int(state.get("repair_count") or 0) < get_settings().sql_repair_max:
        return "repair_sql"
    return "render_chart"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("retrieve_schema", retrieve_schema)
    g.add_node("generate_sql", generate_sql)
    g.add_node("validate_sql", validate_sql_node)
    g.add_node("repair_sql", repair_sql)
    g.add_node("execute_sql", execute_sql)
    g.add_node("render_chart", render_chart)
    g.add_node("respond", respond)
    g.add_node("respond_without_sql", respond_without_sql)
    g.add_node("retrieve_docs", retrieve_docs_node)
    g.add_node("answer_from_docs", answer_from_docs)
    g.add_node("web_search", web_search_node)
    g.add_node("answer_from_web", answer_from_web)

    g.add_edge(START, "classify_intent")
    g.add_conditional_edges(
        "classify_intent",
        _after_intent,
        {
            "retrieve_schema": "retrieve_schema",
            "retrieve_docs": "retrieve_docs",
            "web_search": "web_search",
            "respond_without_sql": "respond_without_sql",
            "done": END,
        },
    )
    g.add_edge("retrieve_docs", "answer_from_docs")
    g.add_edge("answer_from_docs", END)
    g.add_edge("web_search", "answer_from_web")
    g.add_edge("answer_from_web", END)
    g.add_edge("retrieve_schema", "generate_sql")
    g.add_edge("generate_sql", "validate_sql")
    g.add_conditional_edges(
        "validate_sql",
        _after_validate,
        {"execute_sql": "execute_sql", "repair_sql": "repair_sql", "respond": "respond"},
    )
    g.add_edge("repair_sql", "validate_sql")
    g.add_conditional_edges(
        "execute_sql",
        _after_execute,
        {"repair_sql": "repair_sql", "render_chart": "render_chart"},
    )
    g.add_edge("render_chart", "respond")
    g.add_edge("respond", END)
    g.add_edge("respond_without_sql", END)
    return g.compile()


_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = build_graph()
    return _APP


def reset_app() -> None:
    global _APP
    _APP = None


def ask(question: str, *, model_id: str | None = None) -> AgentState:
    profile = resolve_profile(model_id)
    token = set_llm_profile(profile)
    try:
        return get_app().invoke(
            {
                "question": question,
                "repair_count": 0,
                "llm_model_id": profile.id,
                "llm_model_label": profile.label,
            }
        )
    finally:
        reset_llm_profile(token)


def _events_from_states(
    *,
    question: str,
    profile_id: str,
    profile_label: str,
    states: list[AgentState],
):
    last: AgentState | None = None
    saw_intent = False
    saw_query_status = False
    saw_docs_status = False
    saw_web_status = False
    saw_web_sources = False
    saw_chart_status = False
    saw_answer = False

    for state in states:
        last = state
        intent = state.get("intent")
        if intent and not saw_intent:
            saw_intent = True
            yield {
                "type": "intent",
                "intent": intent,
                "intent_reason": state.get("intent_reason") or "",
            }
            if intent == "query_db":
                yield {"type": "status", "message": "Đang lấy schema và sinh SQL…"}
            elif intent in _DOCS_INTENTS:
                yield {"type": "status", "message": "Đang tìm hướng dẫn trong tài liệu VMS…"}
            elif intent in _WEB_INTENTS:
                yield {"type": "status", "message": "Đang tìm trên web (SearXNG)…"}
            answer0 = (state.get("answer") or "").strip()
            if answer0:
                saw_answer = True
                yield {"type": "answer", "text": answer0}

        if intent == "query_db" and state.get("sql") and not saw_query_status:
            saw_query_status = True
            yield {"type": "status", "message": "Đang chạy truy vấn…"}

        if intent == "query_db" and (state.get("chart_png_base64") or "").strip() and not saw_chart_status:
            saw_chart_status = True
            yield {"type": "status", "message": "Đã vẽ biểu đồ từ kết quả truy vấn…"}
            yield {
                "type": "chart",
                "chart_png_base64": state.get("chart_png_base64"),
                "chart_meta": state.get("chart_meta"),
            }

        if intent in _DOCS_INTENTS and state.get("relevant_docs") is not None and not saw_docs_status:
            saw_docs_status = True
            n = len(state.get("relevant_docs") or [])
            yield {
                "type": "status",
                "message": f"Đã chọn {n} card tài liệu — đang soạn câu trả lời…",
            }

        if intent in _WEB_INTENTS and state.get("web_results") is not None and not saw_web_status:
            saw_web_status = True
            n = len(state.get("web_results") or [])
            yield {
                "type": "status",
                "message": f"Đã có {n} kết quả web — đang soạn câu trả lời…",
            }

        sources = state.get("web_sources") or []
        if intent in _WEB_INTENTS and sources and not saw_web_sources:
            saw_web_sources = True
            yield {"type": "web_sources", "sources": sources}

        answer = (state.get("answer") or "").strip()
        if answer and not saw_answer:
            saw_answer = True
            yield {"type": "answer", "text": answer}

    if last is None:
        yield {"type": "error", "message": "Không có kết quả"}
        return

    qr = last.get("query_result") or {}
    sql = (last.get("sql") or "").strip() or None
    chart = (last.get("chart_png_base64") or "").strip() or None
    yield {
        "type": "done",
        "result": {
            "question": last.get("question") or question,
            "answer": last.get("answer") or "",
            "intent": last.get("intent"),
            "intent_reason": last.get("intent_reason"),
            "sql": sql,
            "database": qr.get("database"),
            "row_count": qr.get("row_count"),
            "error": last.get("error") or None,
            "doc_card_id": last.get("doc_card_id") or None,
            "doc_card_title": last.get("doc_card_title") or None,
            "chart_png_base64": chart,
            "chart_meta": last.get("chart_meta") or None,
            "web_sources": last.get("web_sources") or [],
            "llm_model_id": last.get("llm_model_id") or profile_id,
            "llm_model_label": last.get("llm_model_label") or profile_label,
        },
    }


def ask_events(question: str, *, model_id: str | None = None):
    """SSE events. Graph chạy xong trong một Context rồi mới yield — tránh lỗi ContextVar."""
    profile = resolve_profile(model_id)
    yield {"type": "status", "message": f"Đang dùng {profile.label}…"}
    yield {
        "type": "model",
        "model_id": profile.id,
        "model_label": profile.label,
    }
    yield {"type": "status", "message": "Đang hiểu ý câu hỏi…"}

    token = set_llm_profile(profile)
    try:
        states = list(
            get_app().stream(
                {
                    "question": question,
                    "repair_count": 0,
                    "llm_model_id": profile.id,
                    "llm_model_label": profile.label,
                },
                stream_mode="values",
            )
        )
    finally:
        reset_llm_profile(token)

    yield from _events_from_states(
        question=question,
        profile_id=profile.id,
        profile_label=profile.label,
        states=states,
    )
