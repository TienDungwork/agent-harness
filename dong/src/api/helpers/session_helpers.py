"""Ghi lượt hỏi–đáp vào session store + trace SQL từ graph events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.infra.session import append_session_messages


def extract_sql_from_trace_nodes(nodes: list[dict[str, Any]]) -> str | None:
    for node in reversed(nodes):
        node_id = node.get("node_id") or ""
        if node_id not in ("generate_sql", "validate_sql", "execute_sql", "repair_sql"):
            continue
        output = node.get("output")
        if isinstance(output, dict):
            sql = output.get("sql")
            if isinstance(sql, str) and sql.strip():
                return sql.strip()
    return None


def build_agent_trace(nodes: list[dict[str, Any]], detail: dict[str, Any] | None = None) -> dict[str, Any]:
    trace: dict[str, Any] = {"nodes": nodes}
    if detail:
        trace["detail"] = detail.get("agent_detail") or detail.get("tool") or detail
    sql = extract_sql_from_trace_nodes(nodes)
    if sql:
        trace["sql"] = sql
    return trace


def persist_session_turn(
    *,
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    detail: dict[str, Any] | None = None,
    chart: dict[str, Any] | None = None,
    agent_trace: dict[str, Any] | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    user_msg: dict[str, Any] = {"role": "user", "content": question, "timestamp": now}
    assistant_msg: dict[str, Any] = {"role": "assistant", "content": answer, "timestamp": now}
    if detail:
        assistant_msg["detail"] = detail
    if chart:
        assistant_msg["chart"] = chart
    if agent_trace:
        assistant_msg["agent_trace"] = agent_trace
    append_session_messages(session_id, user_id, [user_msg, assistant_msg])
