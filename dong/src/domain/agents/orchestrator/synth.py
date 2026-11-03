"""Orchestrator multi-step answer synthesis và collect."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

from src.domain.agents.nodes.io import node_event
from src.domain.agents.state import AgentState, Agent_Output
from src.infra.chart.render import should_render_chart, plan_chart, render_chart, _detect_chart_type
from src.domain.agents.core.helpers import memory_context_block, original_question, strip_thinking
from src.domain.agents.orchestrator.core import _reset_pipeline_fields
from src.shared.config import settings
from src.infra.llm.schemas import OrchestratorPlan, QueryResult, StatAnswer
from src.infra.monitoring.tracing import trace_substep
from src.infra.prompts import registry


def _extract_primary_count(rows: list, columns: list) -> float | int | None:
    if not rows or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    for c in columns:
        v = row.get(c)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                return float(v.replace(",", ""))
            except ValueError:
                pass
    return None


def _domain_label_from_sub_question(sub_q: str) -> str:
    from src.domain.agents.orchestrator.plan import _ALL_EVENT_DOMAIN_LABELS

    low = (sub_q or "").lower()
    for label in _ALL_EVENT_DOMAIN_LABELS:
        if label in low:
            return label
    m = re.search(r"sự kiện\s+([^?]+)", low)
    return m.group(1).strip() if m else (sub_q or "khác")


def _aggregate_all_events_rows(step_results: list[dict]) -> tuple[list[str], list[dict]]:
    columns = ["domain", "count"]
    rows: list[dict] = []
    for sr in step_results:
        if sr.get("agent") != "query_data":
            continue
        cnt = _extract_primary_count(sr.get("rows") or [], sr.get("columns") or [])
        rows.append({
            "domain": _domain_label_from_sub_question(sr.get("sub_question") or ""),
            "count": 0 if cnt is None else cnt,
        })
    return columns, rows


def _try_format_all_events_answer(
    question: str,
    step_results: list[dict],
    plan: OrchestratorPlan | None,
) -> str | None:
    from src.domain.agents.orchestrator.plan import _time_lead_from_question, is_all_events_plan
    from src.domain.agents.respond.simple_answer import _fmt_num

    if not is_all_events_plan(plan) or len(step_results) < 2:
        return None
    if any(sr.get("agent") != "query_data" for sr in step_results):
        return None

    lead = _time_lead_from_question(question)
    parts: list[str] = []
    total = 0.0
    for sr in step_results:
        cnt = _extract_primary_count(sr.get("rows") or [], sr.get("columns") or [])
        if cnt is None:
            continue
        label = _domain_label_from_sub_question(sr.get("sub_question") or "")
        total += float(cnt)
        parts.append(f"{label}: {_fmt_num(cnt)}")

    if not parts:
        return None
    return f"{lead}, tổng {_fmt_num(total)} sự kiện ({', '.join(parts)})."


def _multi_step_evidence_text(step_results: list[dict]) -> str:
    lines: list[str] = []
    for idx, sr in enumerate(step_results, start=1):
        sub_q = sr.get("sub_question", "")
        if sr.get("agent") == "docs":
            lines.append(f"Bước {idx} (docs — {sub_q}):\n{sr.get('answer_vi', '')}")
            continue
        if sr.get("error"):
            lines.append(f"Bước {idx} ({sub_q}): Lỗi — {sr['error']}")
            continue
        step_rows = sr.get("rows") or []
        step_columns = sr.get("columns") or []
        if not step_rows:
            lines.append(f"Bước {idx} ({sub_q}): 0 bản ghi")
            continue
        row_lines = [
            ", ".join(f"{c}={r[c]}" for c in step_columns)
            for r in step_rows[:20]
        ]
        lines.append(f"Bước {idx} ({sub_q}):\n" + "\n".join(row_lines))
    return "\n\n".join(lines)


def _comparison_direction(question: str) -> str:
    """'less' cho ít hơn/thấp hơn; mặc định 'more'."""
    low = (question or "").lower()
    if any(m in low for m in ("ít hơn", "it hon", "thấp hơn", "thap hon")):
        return "less"
    return "more"


def _try_format_hay_comparison_answer(question: str, step_results: list[dict]) -> str | None:
    """Trả lời trực tiếp câu 'A hay B nhiều/ít hơn' từ 2 bước query_data."""
    from src.domain.agents.orchestrator.plan import _split_hay_comparison
    from src.domain.agents.respond.simple_answer import _fmt_num

    parts = _split_hay_comparison(question)
    if not parts or len(step_results) != 2:
        return None
    if any(sr.get("agent") != "query_data" for sr in step_results):
        return None
    prefix, left_lbl, right_lbl = parts
    c_left = _extract_primary_count(step_results[0].get("rows") or [], step_results[0].get("columns") or [])
    c_right = _extract_primary_count(step_results[1].get("rows") or [], step_results[1].get("columns") or [])
    if c_left is None or c_right is None:
        return None

    n_left, n_right = _fmt_num(c_left), _fmt_num(c_right)
    time_ctx = prefix.rstrip(",").strip()
    lead = f"{time_ctx}, " if time_ctx else ""
    direction = _comparison_direction(question)
    cmp_word = "ít hơn" if direction == "less" else "nhiều hơn"

    if direction == "less":
        if c_left < c_right:
            return (
                f"{lead}{left_lbl.capitalize()} xảy ra {cmp_word} "
                f"({n_left} sự kiện {left_lbl} so với {n_right} sự kiện {right_lbl})."
            )
        if c_right < c_left:
            return (
                f"{lead}{right_lbl.capitalize()} xảy ra {cmp_word} "
                f"({n_right} sự kiện {right_lbl} so với {n_left} sự kiện {left_lbl})."
            )
    else:
        if c_left > c_right:
            return (
                f"{lead}{left_lbl.capitalize()} xảy ra {cmp_word} "
                f"({n_left} sự kiện {left_lbl} so với {n_right} sự kiện {right_lbl})."
            )
        if c_right > c_left:
            return (
                f"{lead}{right_lbl.capitalize()} xảy ra {cmp_word} "
                f"({n_right} sự kiện {right_lbl} so với {n_left} sự kiện {left_lbl})."
            )
    return f"{lead}{left_lbl} và {right_lbl} xảy ra bằng nhau ({n_left} sự kiện mỗi loại)."


def _build_orchestrator_query_result(step_results: list[dict], answer: str) -> QueryResult:
    columns = ["label", "count"]
    rows: list[list] = []
    for sr in step_results:
        if sr.get("agent") != "query_data":
            continue
        cnt = _extract_primary_count(sr.get("rows") or [], sr.get("columns") or [])
        if cnt is None:
            continue
        label = (sr.get("sub_question") or "").strip() or "bước"
        rows.append([label, cnt])
    return QueryResult(
        tool="sql_builder",
        columns=columns,
        rows=rows,
        row_count=len(rows),
        error="",
        reply_vi=answer,
    )


def _synthesize_orchestrator_answer(question: str, step_results: list[dict], state: AgentState) -> tuple[str, str]:
    """Tổng hợp câu trả lời multi-hop; trả (answer, answer_source)."""
    from src.infra.llm.client import invoke_text, use_offline_tools

    plan = state.get("orchestrator_plan")
    compare_q = original_question(state) or question
    all_events = _try_format_all_events_answer(compare_q, step_results, plan)
    if all_events:
        return all_events, "template_all_events"

    comparison = _try_format_hay_comparison_answer(compare_q, step_results)
    if comparison:
        return comparison, "template_comparison"

    evidence = _multi_step_evidence_text(step_results)
    if not evidence.strip():
        return "Không có kết quả điều phối.", "empty"

    from src.infra.memory.context import compress_tool_result
    if len(evidence) > 300 * 4:
        evidence = compress_tool_result(evidence, query=question, max_tokens=300)

    if not use_offline_tools():
        try:
            safety_instruction = (
                "Tuân thủ nghiêm ngặt quy tắc an toàn VMS KCN Hưng Phú: "
                "Không suy diễn số liệu ngoài dữ liệu truy vấn."
            )
            sys_prompt = registry().render("respond_stat")
            sys_prompt = f"{sys_prompt}\n\n[Nhắc lại chỉ dẫn]: {safety_instruction}"

            with trace_substep("respond_stat", kind="agent", input={"multi_hop": True}):
                raw = invoke_text(
                    sys_prompt,
                    (
                        f"{memory_context_block(state, for_stat=True, question=question)}"
                        f"Câu hỏi gốc: {question}\n"
                        f"Kết quả từng bước:\n{evidence}"
                    ),
                    max_tokens=settings.sql_respond_max_tokens,
                    substep=None,
                )
            polished = strip_thinking(raw)
            if polished:
                return polished, "llm_text"
        except Exception as exc:
            return evidence, f"template_fallback:{type(exc).__name__}"

    return evidence, "template"


def orchestrator_collect_step_node(state: AgentState) -> dict:
    """Thu kết quả batch multi-hop; lặp orchestrator hoặc chuyển respond."""
    from src.domain.agents.orchestrator.plan import is_all_events_plan

    plan: OrchestratorPlan | None = state.get("orchestrator_plan")
    if not plan or not plan.steps:
        return {"events": [node_event("orchestrator_collect", output={"skipped": True})]}

    idx = int(state.get("orchestrator_step_index") or 0)
    end_idx = int(state.get("orchestrator_batch_end_index") or idx + 1)
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    step_results = list(state.get("orchestrator_step_results") or [])
    batch_results = state.get("sql_batch_results") or []
    batch_subs = state.get("orchestrator_batch_sub_questions") or []

    if batch_results:
        for item in batch_results:
            step_results.append({
                "agent": "query_data",
                "sub_question": item.get("sub_question", ""),
                "rows": list(item.get("rows") or []),
                "columns": list(item.get("columns") or []),
                "error": item.get("error") or "",
                "sql": item.get("sql") or "",
            })
    elif batch_subs and len(batch_subs) == 1:
        step = plan.steps[idx]
        if step.agent == "docs":
            docs_payload = state.get("docs_answer") or {}
            step_results.append({
                "agent": "docs",
                "sub_question": step.sub_question,
                "answer_vi": docs_payload.get("answer_vi") or (state.get("answer") or ""),
            })
        else:
            val = state.get("sql_validation") or {}
            err = state.get("error") or ""
            if not val.get("ok"):
                err = err or "sql_validation_failed"
            step_results.append({
                "agent": "query_data",
                "sub_question": step.sub_question,
                "rows": list(state.get("rows") or []),
                "columns": list(state.get("columns") or []),
                "error": err,
                "sql": state.get("sql") or "",
            })
        end_idx = idx + 1
    else:
        for step in plan.steps[idx:end_idx]:
            if step.agent == "docs":
                docs_payload = state.get("docs_answer") or {}
                step_results.append({
                    "agent": "docs",
                    "sub_question": step.sub_question,
                    "answer_vi": docs_payload.get("answer_vi") or (state.get("answer") or ""),
                })

    next_idx = end_idx
    out: dict = {
        "orchestrator_step_results": step_results,
        "orchestrator_step_index": next_idx,
        "orchestrator_batch_sub_questions": [],
        "sql_batch": [],
        "sql_batch_results": [],
        "events": [node_event(
            "orchestrator_collect",
            input={"from_index": idx, "to_index": end_idx, "batch_size": len(batch_results) or (end_idx - idx)},
            output={"next_step_index": next_idx, "collected_steps": len(step_results)},
            meta={"user_id": user_id, "session_id": session_id, "is_multi": True},
        )],
    }

    if next_idx >= len(plan.steps):
        out["multi_hop_ready"] = True
        out["orchestrator_multi_active"] = False
        if is_all_events_plan(plan):
            agg_columns, agg_rows = _aggregate_all_events_rows(step_results)
            if agg_rows:
                out["columns"] = agg_columns
                out["rows"] = agg_rows
        elif batch_results:
            last = batch_results[-1]
            out["rows"] = list(last.get("rows") or [])
            out["columns"] = list(last.get("columns") or [])
    else:
        out.update(_reset_pipeline_fields())

    return out


def route_after_orchestrator_collect(state: AgentState) -> str:
    plan: OrchestratorPlan | None = state.get("orchestrator_plan")
    if not plan:
        return "respond"
    idx = int(state.get("orchestrator_step_index") or 0)
    if idx < len(plan.steps):
        return "orchestrator"
    return "respond"

