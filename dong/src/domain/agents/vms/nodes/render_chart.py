"""Chart render LangGraph node."""

from __future__ import annotations

from typing import Any

from src.domain.agents.vms.nodes.io import node_event
from src.domain.agents.vms.state import AgentState
from src.infra.chart.render import _detect_chart_type, plan_chart
from src.infra.monitoring.tracing import current_span, trace_step


def _pad_direction_rows(rows: list, columns: list) -> list:
    """Bổ sung IN/OUT count=0 khi GROUP BY direction chỉ trả một phía."""
    dir_col = next((c for c in columns if str(c).lower() == "direction"), None)
    if not dir_col:
        return rows
    count_col = next(
        (c for c in columns if str(c).lower() in ("count", "so_luot", "total")),
        columns[-1] if columns else None,
    )
    if not count_col:
        return rows
    present = {str(r.get(dir_col, "")).upper() for r in rows if isinstance(r, dict)}
    out = list(rows)
    for d in ("IN", "OUT"):
        if d not in present:
            out.append({dir_col: d, count_col: 0})
    return out


def render_chart_node(state: AgentState) -> dict:
    """Vẽ chart; thiếu dòng → pad direction / fallback SQL; vẫn thiếu → bỏ chart, không crash graph."""
    rows = list(state.get("rows") or [])
    columns = list(state.get("columns") or [])
    sql = state.get("sql") or ""
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    fallback_applied = False

    if len(rows) < 2:
        rows = _pad_direction_rows(rows, columns)
    if len(rows) < 2:
        from src.domain.agents.vms.chart_fallback import fallback_chart_query

        fb = fallback_chart_query(question=q, sql=sql, rows=rows)
        if fb:
            rows = list(fb.get("rows") or [])
            columns = list(fb.get("columns") or columns)
            sql = fb.get("sql") or sql
            fallback_applied = bool(fb.get("fallback"))

    if len(rows) < 2:
        return {
            "rows": rows,
            "columns": columns,
            "chart_png_base64": "",
            "events": [node_event(
                "render_chart",
                input={"question": q, "columns": columns, "rows": rows, "row_count": len(rows)},
                output={"skipped": True, "reason": "insufficient_rows", "row_count": len(rows)},
                meta={"user_id": user_id, "session_id": session_id},
            )],
        }

    try:
        chart_type = state.get("chart_type") or _detect_chart_type(q)
        spec = plan_chart(rows, q, chart_type=chart_type)
        with trace_step(current_span(), "render_png", input={"chart_type": getattr(spec, "chart_type", "")}, as_type="tool") as sub:
            import src.domain.agents.vms.graph as graph_mod

            png_base64 = graph_mod.render_chart(rows, spec)
            sub["output"] = {"rendered": bool(png_base64), "png_len": len(png_base64 or "")}
        meta = spec.model_dump() if spec else {}
        ok = bool(png_base64)
        node_meta = dict(meta)
        node_meta.update({
            "user_id": user_id,
            "session_id": session_id,
            "chart_spec": meta,
        })
        out_payload = {
            "chart_spec": meta,
            "rendered": ok,
            "chart_png_base64_len": len(png_base64 or ""),
        }
        if fallback_applied:
            out_payload["fallback_applied"] = True
        return {
            "rows": rows,
            "columns": columns,
            "sql": sql,
            "chart_png_base64": png_base64 or "",
            "chart_spec": spec,
            "events": [node_event(
                "render_chart",
                input={"question": q, "columns": columns, "rows": rows, "row_count": len(rows)},
                output=out_payload,
                chart_png_base64=png_base64 or "",
                chart_meta=meta,
                chart_spec=meta,
                meta=node_meta,
            )],
        }
    except Exception as e:
        raise RuntimeError(f"render_chart failed: {e}") from e
