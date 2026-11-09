"""Analytics team state — SQL/chart fields (+ shared keys for subgraph I/O)."""

from __future__ import annotations

from typing import Any, TypedDict

from src.infra.llm.schemas import ChartSpec, RewrittenQuestion


class AnalyticsTeamState(TypedDict, total=False):
    question: str
    rewritten: RewrittenQuestion
    intent: str
    user_id: str
    session_id: str
    answer: str
    error: str
    selected_tables: list[str]
    schema_excerpt: str
    sql: str
    sql_validation: dict
    repair_count: int
    params: list
    rows: list
    columns: list
    chart_png_base64: str
    chart_spec: ChartSpec
    chart_requested: bool
    chart_type: str | None
    orchestrator_multi_active: bool
    sql_batch: list[dict]
    sql_batch_results: list[dict]
    events: list[dict]
    result: Any
