"""Analytics team routing helpers."""

from __future__ import annotations

from src.domain.agents.state import AgentState
from src.infra.chart.render import should_render_chart
from src.shared.config import settings


def after_validate(state: AgentState) -> str:
    val = state.get("sql_validation") or {}
    if val.get("ok"):
        return "execute_sql"
    repair_count = int(state.get("repair_count") or 0)
    if repair_count < settings.sql_repair_max:
        return "repair_sql"
    return "done"


def after_execute(state: AgentState) -> str:
    if state.get("error") and int(state.get("repair_count") or 0) < settings.sql_repair_max:
        return "repair_sql"
    rows = state.get("rows") or []
    if not rows:
        return "done"
    q = state.get("question", "")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else q
    if state.get("chart_requested") or should_render_chart(q_text):
        return "render_chart"
    return "done"
