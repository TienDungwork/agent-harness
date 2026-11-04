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

    # Nén câu trả lời docs hoặc cards nếu vượt ngưỡng 300 tokens
    if len(ans) > 300 * 4:
        ans = compress_tool_result(ans, query=q, max_tokens=300)
        dumped["answer_vi"] = ans

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
    """Vẽ chart khi đủ dữ liệu; lỗi render → raise."""
    rows = list(state.get("rows") or [])
    columns = list(state.get("columns") or [])
    sql = state.get("sql") or ""
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    if len(rows) < 2:
        raise ValueError("Không đủ dòng dữ liệu để vẽ biểu đồ (cần ≥ 2).")

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
        res_dict = {
            "chart_png_base64": png_base64 or "",
            "chart_spec": spec,
            "events": [node_event(
                "render_chart",
                input={"question": q, "columns": columns, "rows": rows, "row_count": len(rows)},
                output={
                    "chart_spec": meta,
                    "rendered": ok,
                    "chart_png_base64_len": len(png_base64 or ""),
                },
                chart_png_base64=png_base64 or "",
                chart_meta=meta,
                chart_spec=meta,
                meta=node_meta,
            )],
        }
        return res_dict
    except Exception as e:
        raise RuntimeError(f"render_chart failed: {e}") from e
