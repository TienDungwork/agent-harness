"""Compile LangGraph StateGraph."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.domain.agents.core.runtime import _wrap_node
from src.domain.agents.nodes.memory import recall_node
from src.domain.agents.orchestrator.core import orchestrator_node, route_orchestrator
from src.domain.agents.orchestrator.synth import (
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
)
from src.domain.agents.nodes.pipeline import (
    answer_from_docs_node,
    render_chart_node,
    retrieve_docs_node,
    retrieve_schema_node,
)
from src.domain.agents.nodes.respond import respond_node
from src.domain.agents.nodes.rewrite_classify import (
    classify_node,
    respond_inline_node,
    rewrite_node,
)
from src.domain.agents.routing.intent import is_stat_event_domain
from src.domain.agents.state import AgentState
from src.infra.chart.render import should_render_chart
from src.shared.config import settings
from src.infra.memory.shortterm import get_checkpointer

_compiled = None


def _build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    from src.domain.agents.nodes.guardrails import (
        guardrail_input_node,
        guardrail_output_node,
    )

    graph = StateGraph(AgentState)
    graph.add_node("guardrail_input", _wrap_node("guardrail_input", guardrail_input_node))
    graph.add_node("guardrail_output", _wrap_node("guardrail_output", guardrail_output_node))
    graph.add_node("recall", _wrap_node("recall", recall_node))
    graph.add_node("rewrite", _wrap_node("rewrite", rewrite_node))
    graph.add_node("classify", _wrap_node("classify", classify_node))
    graph.add_node("respond_inline", _wrap_node("respond_inline", respond_inline_node))
    graph.add_node("orchestrator", _wrap_node("orchestrator", orchestrator_node))
    graph.add_node("orchestrator_collect", _wrap_node("orchestrator_collect", orchestrator_collect_step_node))
    graph.add_node("retrieve_schema", _wrap_node("retrieve_schema", retrieve_schema_node))
    from src.domain.agents.sql.generate import generate_sql_node
    from src.domain.agents.sql.validate import validate_sql_node, repair_sql_node
    from src.domain.agents.sql.execute import execute_sql_node
    graph.add_node("generate_sql", _wrap_node("generate_sql", generate_sql_node))
    graph.add_node("validate_sql", _wrap_node("validate_sql", validate_sql_node))
    graph.add_node("repair_sql", _wrap_node("repair_sql", repair_sql_node))
    graph.add_node("execute_sql", _wrap_node("execute_sql", execute_sql_node))
    graph.add_node("render_chart", _wrap_node("render_chart", render_chart_node))
    graph.add_node("respond", _wrap_node("respond", respond_node))
    
    graph.add_node("retrieve_docs", _wrap_node("retrieve_docs", retrieve_docs_node))
    graph.add_node("answer_from_docs", _wrap_node("answer_from_docs", answer_from_docs_node))
    
    # 1. Entry Guardrail: gom check input + redact PII vào guardrail_input
    graph.add_edge(START, "guardrail_input")
    graph.add_edge("guardrail_input", "recall")
    graph.add_edge("recall", "rewrite")
    graph.add_edge("rewrite", "classify")
    
    # 2. Sau classify: chào hỏi / clarify / out_of_scope rẽ respond_inline; còn lại truyền sang orchestrator điều phối
    def route_classify(state: AgentState) -> str:
        ans = (state.get("answer") or "").strip()
        intent = state.get("intent", "query_data")
        q = state.get("question", "")
        rewritten = state.get("rewritten")
        q_text = rewritten.text if rewritten else q

        if intent == "out_of_scope" and is_stat_event_domain(q_text):
            return "orchestrator"

        if (ans and intent in ("chat", "clarify")) or intent in ("chat", "out_of_scope"):
            return "respond_inline"
        return "orchestrator"

    graph.add_conditional_edges("classify", route_classify, {
        "respond_inline": "respond_inline",
        "orchestrator": "orchestrator",
    })
    graph.add_edge("respond_inline", "respond")
    
    # 3. Orchestrator: làm trung tâm điều phối rẽ sang các nhánh thực thi (đơn pass-through, đa ý multi)
    graph.add_conditional_edges("orchestrator", route_orchestrator, {
        "query_data": "retrieve_schema",
        "docs": "retrieve_docs",
        "out": "respond_inline",
        "respond": "respond",
    })
    
    def _after_validate(state: AgentState) -> str:
        val = state.get("sql_validation") or {}
        if val.get("ok"):
            return "execute_sql"
        repair_count = int(state.get("repair_count") or 0)
        if repair_count < settings.sql_repair_max:
            return "repair_sql"
        return "respond"

    def should_render_chart_edge(state: AgentState) -> str:
        rows = state.get("rows") or []
        if not rows:
            return "respond"
        q = state.get("question", "")
        rewritten = state.get("rewritten")
        q_text = rewritten.text if rewritten else q
        if state.get("chart_requested") or should_render_chart(q_text):
            return "render_chart"
        return "respond"

    def _after_execute(state: AgentState) -> str:
        if state.get("error") and int(state.get("repair_count") or 0) < settings.sql_repair_max:
            return "repair_sql"
        if state.get("orchestrator_multi_active"):
            return "orchestrator_collect"
        return should_render_chart_edge(state)

    def _after_docs(state: AgentState) -> str:
        if state.get("orchestrator_multi_active"):
            return "orchestrator_collect"
        return "respond"

    # Query Data branch (v7 text-to-SQL: retrieve_schema -> generate_sql -> validate_sql <-> repair_sql -> execute_sql -> render_chart/respond)
    graph.add_edge("retrieve_schema", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges("validate_sql", _after_validate, {
        "execute_sql": "execute_sql",
        "repair_sql": "repair_sql",
        "respond": "respond",
    })
    graph.add_edge("repair_sql", "validate_sql")
    graph.add_conditional_edges("execute_sql", _after_execute, {
        "repair_sql": "repair_sql",
        "render_chart": "render_chart",
        "respond": "respond",
        "orchestrator_collect": "orchestrator_collect",
    })
    graph.add_edge("render_chart", "respond")
    graph.add_edge("respond", "guardrail_output")
    graph.add_edge("guardrail_output", END)
    
    # Docs branch
    graph.add_edge("retrieve_docs", "answer_from_docs")
    graph.add_conditional_edges("answer_from_docs", _after_docs, {
        "orchestrator_collect": "orchestrator_collect",
        "respond": "respond",
    })

    graph.add_conditional_edges("orchestrator_collect", route_after_orchestrator_collect, {
        "orchestrator": "orchestrator",
        "respond": "respond",
    })

    return graph.compile(checkpointer=checkpointer)


def reset_graph() -> None:
    global _compiled
    _compiled = None


def _get_graph():
    global _compiled
    from unittest.mock import Mock

    import src.domain.agents.graph as graph_mod

    build = graph_mod._build_graph
    if isinstance(build, Mock):
        return build()
    if _compiled is None:
        _compiled = build()
    return _compiled

