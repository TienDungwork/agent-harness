"""Compile analytics subgraph (SQL + chart + repair). No run_agent here."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.domain.agents.analytics.nodes import after_execute, after_validate
from src.domain.agents.analytics.sql_agent.tools.execute import execute_sql_node
from src.domain.agents.analytics.sql_agent.tools.generate import generate_sql_node
from src.domain.agents.analytics.sql_agent.tools.schema import retrieve_schema_node
from src.domain.agents.analytics.sql_agent.tools.validate import repair_sql_node, validate_sql_node
from src.domain.agents.nodes.render_chart import render_chart_node
from src.domain.agents.state import AgentState


def build_analytics_graph():
    """Return compiled SQL/chart team graph (use as parent node ``analytics_team``)."""
    from src.domain.agents.graph import _wrap_node

    g = StateGraph(AgentState)
    g.add_node("retrieve_schema", _wrap_node("retrieve_schema", retrieve_schema_node))
    g.add_node("generate_sql", _wrap_node("generate_sql", generate_sql_node))
    g.add_node("validate_sql", _wrap_node("validate_sql", validate_sql_node))
    g.add_node("repair_sql", _wrap_node("repair_sql", repair_sql_node))
    g.add_node("execute_sql", _wrap_node("execute_sql", execute_sql_node))
    g.add_node("render_chart", _wrap_node("render_chart", render_chart_node))

    g.add_edge(START, "retrieve_schema")
    g.add_edge("retrieve_schema", "generate_sql")
    g.add_edge("generate_sql", "validate_sql")
    g.add_conditional_edges(
        "validate_sql",
        after_validate,
        {"execute_sql": "execute_sql", "repair_sql": "repair_sql", "done": END},
    )
    g.add_edge("repair_sql", "validate_sql")
    g.add_conditional_edges(
        "execute_sql",
        after_execute,
        {"repair_sql": "repair_sql", "render_chart": "render_chart", "done": END},
    )
    g.add_edge("render_chart", END)
    return g.compile()
