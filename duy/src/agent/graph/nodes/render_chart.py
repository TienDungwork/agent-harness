from __future__ import annotations

from agent.graph.state import AgentState
from agent.services.chart_detect import wants_chart
from agent.services.chart_fallback import fallback_vehicle_type_chart
from agent.services.chart_service import render_chart_png


def _resolve_dbname(state: AgentState) -> str:
    datasets = state.get("relevant_datasets") or []
    sql = (state.get("sql") or "").lower()
    for ds in datasets:
        table = str(ds.get("table") or "").lower()
        if table and table in sql:
            return str(ds.get("database") or "its")
    for ds in datasets:
        if ds.get("database"):
            return str(ds["database"])
    return "its"


def render_chart(state: AgentState) -> dict:
    question = state.get("question") or ""
    if not wants_chart(question):
        return {"chart_png_base64": "", "chart_meta": ""}

    if state.get("error"):
        return {"chart_png_base64": "", "chart_meta": "skip-error"}

    qr = state.get("query_result") or {}
    rows = qr.get("rows") or []
    if not isinstance(rows, list):
        return {"chart_png_base64": "", "chart_meta": "no-rows"}

    sql = state.get("sql") or ""
    out: dict = {}

    fallback = fallback_vehicle_type_chart(
        question=question,
        sql=sql,
        rows=rows,
        dbname=_resolve_dbname(state),
    )
    if fallback:
        qr = fallback["query_result"]
        rows = qr.get("rows") or []
        out["query_result"] = qr
        out["sql"] = fallback["sql"]

    png, meta = render_chart_png(question=question, rows=rows)
    out.update(
        {
            "chart_png_base64": png or "",
            "chart_meta": meta,
        }
    )
    return out
