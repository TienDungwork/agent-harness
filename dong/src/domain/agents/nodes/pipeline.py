"""Docs RAG nodes, schema retrieval, chart render."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState
from src.infra.chart.render import _detect_chart_type, plan_chart, should_render_chart
from src.infra.db.catalog import build_schema_excerpt, select_relevant_tables
from src.infra.llm.schemas import ChartSpec
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


def retrieve_docs_node(state: AgentState) -> dict:
    from src.domain.knowledge import retrieve_docs
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    with trace_step(current_span(), "retrieve_docs", input={"question": q}, as_type="tool") as sub:
        cards = retrieve_docs(q)
        sub["output"] = {"card_count": len(cards)}
    card_ids = [str(c.get("id")) for c in cards if isinstance(c, dict) and c.get("id")]
    titles = [str(c.get("title")) for c in cards if isinstance(c, dict) and c.get("title")]
    return {
        "events": [node_event(
            "retrieve_docs",
            input={"question": q},
            output={"cards": cards, "card_count": len(cards), "card_ids": card_ids, "titles": titles},
            meta={"user_id": user_id, "session_id": session_id},
        )],
        "rows": cards  # temporary save cards in rows
    }

def answer_from_docs_node(state: AgentState) -> dict:
    from src.domain.knowledge import answer_from_docs
    from src.infra.memory.context import compress_tool_result

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    cards = state.get("rows", [])
    card_ids = [str(c.get("id")) for c in cards if isinstance(c, dict) and c.get("id")]
    docs_ans = answer_from_docs(q, cards)
    dumped = docs_ans.model_dump()
    ans = docs_ans.answer_vi

    if len(ans) > 300 * 4:
        with trace_step(current_span(), "compress_docs", input={"answer_len": len(ans)}, as_type="tool") as sub:
            ans = compress_tool_result(ans, query=q, max_tokens=300)
            dumped["answer_vi"] = ans
            sub["output"] = {"answer_len": len(ans)}

    return {
        "answer": ans,
        "respond_mode": "docs",
        "docs_answer": dumped,
        "events": [node_event(
            "answer_from_docs",
            input={"question": q, "cards": cards, "card_ids": card_ids},
            output={"docs_answer": dumped, "respond_mode": "docs"},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }

def retrieve_schema_node(state: AgentState) -> dict:
    from src.domain.agents.sql.batch import query_text_for_state

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
        from src.domain.agents.respond.chart_fallback import fallback_chart_query

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
            import src.domain.agents.graph as graph_mod

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
