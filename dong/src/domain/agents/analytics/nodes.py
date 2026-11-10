"""Analytics team routing helpers."""
from __future__ import annotations
from src.domain.agents.state import AgentState
from src.infra.chart.render import should_render_chart
from src.shared.config import settings

def after_validate(state: AgentState) -> str:
    val = (state['sql_validation'] if 'sql_validation' in state else None) or {}
    if val['ok'] if 'ok' in val else None:
        return 'execute_sql'
    repair_count = int((state['repair_count'] if 'repair_count' in state else None) or 0)
    if repair_count < settings.sql_repair_max:
        return 'repair_sql'
    return 'done'

def after_execute(state: AgentState) -> str:
    if (state['error'] if 'error' in state else None) and int((state['repair_count'] if 'repair_count' in state else None) or 0) < settings.sql_repair_max:
        return 'repair_sql'
    rows = (state['rows'] if 'rows' in state else None) or []
    if not rows:
        return 'done'
    q = state['question'] if 'question' in state else ''
    rewritten = state['rewritten'] if 'rewritten' in state else None
    q_text = rewritten.text if rewritten else q
    if (state['chart_requested'] if 'chart_requested' in state else None) or should_render_chart(q_text):
        return 'render_chart'
    return 'done'
