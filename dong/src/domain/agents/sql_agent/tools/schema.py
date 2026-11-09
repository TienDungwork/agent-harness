"""Schema retrieval node for SQL path."""

from __future__ import annotations

from src.domain.agents.vms.nodes.io import node_event
from src.domain.agents.vms.state import AgentState
from src.infra.db.catalog import build_schema_excerpt, select_relevant_tables
from src.infra.monitoring.tracing import current_span, trace_step


def retrieve_schema_node(state: AgentState) -> dict:
    from src.domain.agents.sql_agent.tools.batch import query_text_for_state

    q = state.get("question", "")
    intent = state.get("intent", "query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    q_text = query_text_for_state(state)

    with trace_step(current_span(), "select_tables", input={"question": q_text}, as_type="tool"):
        tables = select_relevant_tables(q_text, limit=4)
    with trace_step(current_span(), "build_schema_excerpt", input={"tables": tables}, as_type="tool") as sub:
        excerpt = build_schema_excerpt(tables)
        sub["output"] = {"selected_tables": tables, "schema_length": len(excerpt)}
    return {
        "schema_excerpt": excerpt,
        "selected_tables": tables,
        "events": [node_event(
            "retrieve_schema",
            input={"intent": intent, "question": q},
            output={"schema_excerpt": excerpt, "selected_tables": tables},
            meta={
                "user_id": user_id,
                "session_id": session_id,
                "schema_length": len(excerpt),
                "selected_tables": tables,
            },
        )],
    }
