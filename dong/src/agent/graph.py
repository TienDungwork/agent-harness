"""Graph Agent v5 — LangGraph pipeline thay thế ReAct.

Pipeline chính:
  START → guardrail_input (check injection/toxic & redact PII) → recall → rewrite → classify
    - chat / clarify: respond_inline → respond → guardrail_output → END
    - tất cả còn lại: orchestrator (điều phối tập trung, fast passthrough cho câu đơn)
        * query_data: retrieve_schema → … → respond → guardrail_output → END
        * docs: retrieve_docs → answer_from_docs → respond → guardrail_output → END
        * out_of_scope: guardrail_out_of_scope → respond → guardrail_output → END
        * multi: orchestrator ⇄ (query_data|docs pipeline) ⇄ orchestrator_collect → respond → guardrail_output → END
"""

from __future__ import annotations

import contextvars
import logging
import queue
import re
import threading
from typing import Annotated, Any, TypedDict
import operator

logger = logging.getLogger(__name__)

from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage

from src.config import settings
from src.memory.shortterm import get_checkpointer
from src.agent.intent import classify_intent_safe, is_stat_event_domain, sanitize_intent_result
from src.agent.rewrite import rewrite_question
from src.db.catalog import build_schema_excerpt, select_relevant_tables
from src.db.validator import validate_sql
from src.db.executor import execute_sql
from src.chart.render import should_render_chart, plan_chart, render_chart, _detect_chart_type
from src.llm.schemas import ChartSpec, OrchestratorPlan, OrchestratorStep, QueryResult, RewrittenQuestion, StatAnswer
from src.guardrails import OUT_OF_SCOPE_REPLY
from src.monitoring.tracing import (
    bind_trace_root,
    get_trace_parent,
    reset_trace_root,
    trace_active_parent,
    trace_step,
    trace_substep,
)
from src.prompts import registry
from src.agent.node_io import json_safe, node_event
from src.agent.generate_sql import generate_sql_node
from src.agent.validate_sql import validate_sql_node, repair_sql_node
from src.agent.execute_sql import execute_sql_node

class Agent_Input(BaseModel):
    question: str
    rewritten: Any | None = None
    user_id: str = "default"
    stream_tokens: bool = False

class Agent_Output(BaseModel):
    question: str
    answer: str
    query: QueryResult | None = None
    detail: str = ""

class AgentState(TypedDict, total=False):
    question: str
    original_question: str
    rewritten: RewrittenQuestion
    intent: str
    answer: str
    stream_tokens: bool
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    recalled_memories: list[str]
    extracted_memories: list[str]
    orchestrator_plan: OrchestratorPlan
    orchestrator_step_index: int
    orchestrator_batch_sub_questions: list[str]
    orchestrator_batch_end_index: int
    orchestrator_step_results: list[dict]
    orchestrator_multi_active: bool
    sql_batch: list[dict]
    sql_batch_results: list[dict]
    multi_hop_ready: bool
    respond_mode: str
    docs_answer: dict

    # Query Data branch
    selected_tables: list[str]
    schema_excerpt: str
    sql: str
    sql_validation: dict
    repair_count: int
    params: list
    rows: list
    columns: list
    error: str
    chart_png_base64: str
    chart_spec: ChartSpec
    chart_requested: bool
    chart_type: str | None
    
    events: Annotated[list[dict], operator.add]
    result: Agent_Output
    guardrail_in_scope: bool
    _trace_span: Any

_stream_queue = contextvars.ContextVar("_stream_queue", default=None)


def emit_answer_chunks(ans_text: str, chunk_words: int = 3, enabled: bool = True) -> None:
    """Phát các SSE chunk event cho câu trả lời thời gian thực qua _stream_queue."""
    if not enabled:
        return
    q = _stream_queue.get()
    if q is None or not ans_text:
        return
    words = ans_text.split(" ")
    for i in range(0, len(words), chunk_words):
        group = words[i : i + chunk_words]
        delta = " ".join(group)
        if i + chunk_words < len(words):
            delta += " "
        q.put({"node_id": "__answer__", "status": "chunk", "delta": delta})


def _wrap_node(node_id: str, func):
    def wrapper(state: AgentState):
        import time
        t0 = time.perf_counter()
        q = _stream_queue.get()
        parent = state.get("_trace_span") or get_trace_parent()
        user_id = state.get("user_id") or "default"
        session_id = state.get("session_id") or "default"
        if q is not None:
            q.put({"node_id": node_id, "status": "running"})

        with trace_step(
            parent,
            node_id,
            metadata={"user_id": user_id, "session_id": session_id},
        ) as step:
            try:
                with trace_active_parent(step.get("_span")):
                    res = func(state)
                dur_ms = round((time.perf_counter() - t0) * 1000, 1)
            except Exception as e:
                dur_ms = round((time.perf_counter() - t0) * 1000, 1)
                err_io = {
                    "input": {"question": state.get("question", ""), "node_id": node_id},
                    "output": {"error": str(e), "error_type": type(e).__name__},
                }
                step["input"] = err_io["input"]
                step["output"] = err_io["output"]
                if q is not None:
                    q.put({
                        "node_id": node_id,
                        "status": "done",
                        "duration_ms": dur_ms,
                        "input": err_io["input"],
                        "output": err_io["output"],
                    })
                raise

            if isinstance(res, dict) and "events" in res and res["events"]:
                ev = res["events"][-1]
                step["input"] = json_safe(ev.get("input"))
                step["output"] = json_safe(ev.get("output"))
                meta = dict(ev.get("meta") or {})
                meta.setdefault("user_id", user_id)
                meta.setdefault("session_id", session_id)
                meta["duration_ms"] = dur_ms
                step["metadata"] = json_safe(meta)
                if q is not None:
                    for item in res["events"]:
                        q.put({
                            "node_id": item.get("node_id", node_id),
                            "status": "done",
                            "duration_ms": dur_ms,
                            "input": json_safe(item.get("input")),
                            "output": json_safe(item.get("output")),
                            "chart_png_base64": item.get("chart_png_base64"),
                            "chart_meta": json_safe(item.get("chart_meta")),
                            "chart_spec": json_safe(item.get("chart_spec")),
                            "meta": json_safe(meta),
                        })
            else:
                step["input"] = None
                step["output"] = None
                if q is not None:
                    q.put({
                        "node_id": node_id,
                        "status": "done",
                        "duration_ms": dur_ms,
                        "input": None,
                        "output": None,
                    })
            return res
    return wrapper


def recall_node(state: AgentState) -> dict:
    from src.config import settings
    from src.memory.longterm import recall_long_term

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    if not settings.long_term_memory_enabled:
        return {
            "user_id": user_id,
            "session_id": session_id,
            "original_question": q,
            "recalled_memories": [],
            "rewritten": None,
            "intent": "",
            "answer": "",
            "respond_mode": "",
            "docs_answer": None,
            "orchestrator_plan": None,
            "orchestrator_step_index": 0,
            "orchestrator_step_results": [],
            "orchestrator_multi_active": False,
            "multi_hop_ready": False,
            "result": None,
            "rows": [],
            "columns": [],
            "sql": "",
            "error": "",
            "repair_count": 0,
            "events": [node_event(
                "recall",
                input={"user_id": user_id, "question": q},
                output={"recalled_memories": [], "disabled": True},
                meta={"user_id": user_id, "session_id": session_id, "recalled_count": 0, "disabled": True},
            )],
        }
    try:
        memories = recall_long_term(user_id, q, k=3)
        ev_output: dict[str, Any] = {"recalled_memories": memories}
        ev_meta: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "recalled_count": len(memories),
        }
    except Exception as exc:
        logger.warning("recall_long_term failed, degrading safely: %s", exc)
        memories = []
        ev_output = {
            "recalled_memories": [],
            "degraded": True,
            "error": str(exc)[:200],
        }
        ev_meta = {
            "user_id": user_id,
            "session_id": session_id,
            "recalled_count": 0,
            "degraded": True,
        }
    return {
        "user_id": user_id,
        "session_id": session_id,
        "original_question": q,
        "recalled_memories": memories,
        "rewritten": None,
        "intent": "",
        "answer": "",
        "respond_mode": "",
        "docs_answer": None,
        "orchestrator_plan": None,
        "orchestrator_step_index": 0,
        "orchestrator_batch_sub_questions": [],
        "orchestrator_batch_end_index": 0,
        "orchestrator_step_results": [],
        "orchestrator_multi_active": False,
        "sql_batch": [],
        "sql_batch_results": [],
        "multi_hop_ready": False,
        "result": None,
        "rows": [],
        "columns": [],
        "sql": "",
        "error": "",
        "repair_count": 0,
        "events": [node_event(
            "recall",
            input={"user_id": user_id, "question": q},
            output=ev_output,
            meta=ev_meta,
        )],
    }

def run_store_extract(
    user_id: str,
    session_id: str,
    question: str,
    result: Agent_Output | None,
    parent_span: Any = None,
) -> list[dict]:
    """Post-pipeline: extract + store memory sau khi đã trả lời (không chặn respond)."""
    from src.config import settings
    from src.memory.extract import extract_and_store_memory, memory_detail_includes_answer

    if not settings.long_term_memory_enabled:
        return []

    q = question or ""
    uid = user_id or "default"
    sid = session_id or "default"
    res = result
    detail = res.detail if res else ""
    ans = res.answer if res else ""
    include_answer = memory_detail_includes_answer(detail)

    input_payload = {
        "user_id": uid,
        "question": q,
        "answer": ans if include_answer else "",
        "detail": detail,
        "include_answer": include_answer,
    }

    import time
    t0 = time.perf_counter()
    try:
        with trace_step(
            parent_span,
            "store_extract",
            metadata={"user_id": uid, "session_id": sid},
        ) as step:
            try:
                extracted = extract_and_store_memory(
                    uid, q, ans if include_answer else "", detail=detail, include_answer=include_answer
                )
                dur_ms = round((time.perf_counter() - t0) * 1000, 1)
                ev = node_event(
                    "store_extract",
                    input=input_payload,
                    output={"extracted_memories": extracted},
                    meta={"user_id": uid, "session_id": sid, "extracted_count": len(extracted), "duration_ms": dur_ms},
                )
            except Exception as exc:
                dur_ms = round((time.perf_counter() - t0) * 1000, 1)
                logger.warning("extract_and_store_memory failed, degrading safely: %s", exc)
                err_msg = str(exc)[:200]
                ev = node_event(
                    "store_extract",
                    input=input_payload,
                    output={"extracted_memories": [], "degraded": True, "error": err_msg},
                    meta={"user_id": uid, "session_id": sid, "extracted_count": 0, "degraded": True, "duration_ms": dur_ms},
                )
            step["input"] = ev["input"]
            step["output"] = ev["output"]
            step["metadata"] = ev["meta"]

        return [
            {"node_id": "store_extract", "status": "running"},
            {"node_id": "store_extract", "status": "done", "duration_ms": dur_ms, **{k: ev[k] for k in ("input", "output", "meta")}},
        ]
    except Exception as exc:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.warning("run_store_extract failed, degrading safely: %s", exc)
        err_msg = str(exc)[:200]
        return [
            {"node_id": "store_extract", "status": "running"},
            {
                "node_id": "store_extract",
                "status": "done",
                "duration_ms": dur_ms,
                "input": input_payload,
                "output": {"extracted_memories": [], "degraded": True, "error": err_msg},
                "meta": {"user_id": uid, "session_id": sid, "extracted_count": 0, "degraded": True, "duration_ms": dur_ms},
            },
        ]

def rewrite_node(state: AgentState) -> dict:
    from src.agent.intent import is_chat_greeting

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    rewritten = state.get("rewritten")
    is_chat = is_chat_greeting(q)
    from src.agent.rewrite import _needs_rewrite_llm

    if not rewritten:
        rewritten = rewrite_question(q)
    skip_llm = is_chat or not _needs_rewrite_llm(q.strip())
    llm_used = not skip_llm
    return {
        "rewritten": rewritten,
        "question": rewritten.text,
        "messages": [HumanMessage(q)],
        "events": [node_event(
            "rewrite",
            input={"question": q},
            output={"rewritten": rewritten.model_dump()},
            meta={
                "llm_used": llm_used,
                "user_id": user_id,
                "session_id": session_id,
                "sub_question_count": len(rewritten.sub_questions or []),
                **({"skipped": True} if skip_llm else {}),
            },
        )],
    }

def classify_node(state: AgentState) -> dict:
    from src.llm.client import use_offline_tools

    rewritten = state["rewritten"]
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    llm_used = not use_offline_tools()
    res = sanitize_intent_result(classify_intent_safe(rewritten))
    intent = res.intent
    
    chart_req = getattr(res, "chart_requested", False)
    chart_t = getattr(res, "chart_type", None)

    out_state = {
        "intent": intent,
        "chart_requested": chart_req,
        "chart_type": chart_t,
        "events": [node_event(
            "classify",
            input={"rewritten_text": rewritten.text, "rewritten": rewritten.model_dump()},
            output={
                "intent": intent,
                "reason": res.reason,
                "answer": res.answer,
                "chart_requested": chart_req,
                "chart_type": chart_t,
            },
            meta={
                "llm_used": llm_used,
                "user_id": user_id,
                "session_id": session_id,
                "chart_requested": chart_req,
                "chart_type": chart_t,
            },
        )],
    }
    if res.answer:
        out_state["answer"] = res.answer
    else:
        out_state["answer"] = ""
        
    return out_state

def respond_inline_node(state: AgentState) -> dict:
    from src.agent.inline_respond import generate_inline_response

    q = state.get("question", "")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else q
    ans = (state.get("answer") or "").strip()
    intent = state.get("intent", "chat")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    if intent in ("chat", "out_of_scope"):
        if not ans:
            ans = generate_inline_response(q_text, intent=intent)
    elif intent == "clarify" and not ans:
        ans = "Bạn có thể nói rõ hơn yêu cầu của mình được không?"

    resp_mode = "out_of_scope" if intent == "out_of_scope" else "inline"

    return {
        "answer": ans,
        "respond_mode": resp_mode,
        "events": [node_event(
            "respond_inline",
            input={"question": q, "intent": intent},
            output={"answer": ans, "respond_mode": resp_mode},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }

def route_intent(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    elif intent == "out_of_scope":
        return "out"
    return "query_data"


def _is_multi_plan(plan: OrchestratorPlan | None) -> bool:
    return bool(plan and (plan.is_multi or len(plan.steps) >= 2))


def _reset_pipeline_fields() -> dict:
    return {
        "sql": "",
        "repair_count": 0,
        "error": "",
        "rows": [],
        "columns": [],
        "sql_validation": {},
        "params": [],
        "schema_excerpt": "",
        "selected_tables": [],
        "docs_answer": None,
        "respond_mode": "",
        "answer": "",
        "chart_png_base64": "",
        "chart_spec": None,
        "sql_batch": [],
        "sql_batch_results": [],
    }


def _batch_steps_from_plan(plan: OrchestratorPlan, start_idx: int) -> tuple[list[str], int, str]:
    """Gom các bước liên tiếp cùng agent; trả (sub_questions, end_idx, agent)."""
    steps = plan.steps
    if start_idx >= len(steps):
        return [], start_idx, ""
    agent = steps[start_idx].agent
    subs: list[str] = []
    i = start_idx
    while i < len(steps) and steps[i].agent == agent:
        subs.append(steps[i].sub_question)
        i += 1
    return subs, i, agent


def _apply_orchestrator_batch(out: dict, plan: OrchestratorPlan, start_idx: int) -> None:
    subs, end_idx, agent = _batch_steps_from_plan(plan, start_idx)
    out["orchestrator_batch_sub_questions"] = subs
    out["orchestrator_batch_end_index"] = end_idx
    if subs:
        out["question"] = subs[0]
    out.setdefault("events", [])
    if out["events"]:
        out["events"][-1].setdefault("meta", {})["batch_agent"] = agent
        out["events"][-1]["meta"]["batch_size"] = len(subs)


def orchestrator_node(state: AgentState) -> dict:
    from src.agent.orchestrator import plan_orchestration
    from src.llm.client import use_offline_tools

    q = state.get("question", "")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else q
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    intent = state.get("intent", "query_data")
    llm_used = not use_offline_tools()

    plan_existing: OrchestratorPlan | None = state.get("orchestrator_plan")
    if state.get("orchestrator_multi_active") and plan_existing and plan_existing.steps:
        idx = int(state.get("orchestrator_step_index") or 0)
        subs, end_idx, agent = _batch_steps_from_plan(plan_existing, idx)
        out = {
            **_reset_pipeline_fields(),
            "orchestrator_batch_sub_questions": subs,
            "orchestrator_batch_end_index": end_idx,
            "events": [node_event(
                "orchestrator",
                input={"question": q_text, "dispatch_from": idx, "batch_sub_questions": subs},
                output={"agent": agent, "batch_size": len(subs), "batch_end_index": end_idx},
                meta={"user_id": user_id, "session_id": session_id, "is_multi": True},
            )],
        }
        if subs:
            out["question"] = subs[0]
        return out

    sub_questions = list(getattr(rewritten, "sub_questions", None) or [])
    original_q = state.get("original_question") or q

    from src.agent.orchestrator import is_multi_question
    # Fast pass-through nếu là câu đơn, tránh gọi LLM lần 2
    if not is_multi_question(q_text, rewritten=rewritten, original=original_q, intent=intent):
        if is_stat_event_domain(q_text):
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="query_data", sub_question=q_text)], is_multi=False, reason="Fast passthrough: stat domain")
        elif intent == "out_of_scope":
            plan = OrchestratorPlan(steps=[], is_multi=False, reason="Fast passthrough: out_of_scope")
        elif intent in ("how_to", "troubleshoot", "concept"):
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="docs", sub_question=q_text)], is_multi=False, reason="Fast passthrough: docs")
        elif intent in ("chat", "clarify"):
            plan = OrchestratorPlan(steps=[], is_multi=False, reason="Fast passthrough: inline")
        else:
            plan = OrchestratorPlan(steps=[OrchestratorStep(agent="query_data", sub_question=q_text)], is_multi=False, reason="Fast passthrough: query_data")
        llm_used = False
    elif intent == "out_of_scope" and is_stat_event_domain(q_text):
        plan = plan_orchestration(
            q_text, sub_questions=sub_questions, original=original_q, intent=intent,
        )
    elif intent == "out_of_scope":
        plan = OrchestratorPlan(steps=[], is_multi=False, reason="out_of_scope")
    else:
        plan = plan_orchestration(
            q_text, sub_questions=sub_questions, original=original_q, intent=intent,
        )

    out: dict = {
        "orchestrator_plan": plan,
        "events": [node_event(
            "orchestrator",
            input={"question": q_text, "intent": intent, "sub_questions": sub_questions},
            output={"orchestrator_plan": plan.model_dump()},
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }
    if _is_multi_plan(plan):
        out.update({
            "orchestrator_multi_active": True,
            "orchestrator_step_index": 0,
            "orchestrator_step_results": [],
            "multi_hop_ready": False,
            **_reset_pipeline_fields(),
        })
        _apply_orchestrator_batch(out, plan, 0)
        out["events"][0]["meta"]["is_multi"] = True
    return out


def route_orchestrator(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else state.get("question", "")

    plan: OrchestratorPlan | None = state.get("orchestrator_plan")
    if state.get("orchestrator_multi_active") and plan and plan.steps:
        idx = int(state.get("orchestrator_step_index") or 0)
        if idx >= len(plan.steps):
            return "respond"
        batch = state.get("orchestrator_batch_sub_questions") or []
        if batch:
            agent = plan.steps[idx].agent
        else:
            agent = plan.steps[idx].agent
        return "query_data" if agent == "query_data" else "docs"

    if is_stat_event_domain(q_text):
        return "query_data"

    if intent == "out_of_scope":
        return "out"

    if plan and plan.steps:
        agent = plan.steps[0].agent
        if agent == "docs":
            return "docs"
        elif agent == "query_data":
            return "query_data"

    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    return "query_data"


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
    from src.agent.orchestrator import _ALL_EVENT_DOMAIN_LABELS

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
    from src.agent.orchestrator import _time_lead_from_question, is_all_events_plan
    from src.agent.simple_answer import _fmt_num

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
    from src.agent.orchestrator import _split_hay_comparison
    from src.agent.simple_answer import _fmt_num

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
    from src.llm.client import invoke_text, use_offline_tools

    plan = state.get("orchestrator_plan")
    compare_q = _original_question(state) or question
    all_events = _try_format_all_events_answer(compare_q, step_results, plan)
    if all_events:
        return all_events, "template_all_events"

    comparison = _try_format_hay_comparison_answer(compare_q, step_results)
    if comparison:
        return comparison, "template_comparison"

    evidence = _multi_step_evidence_text(step_results)
    if not evidence.strip():
        return "Không có kết quả điều phối.", "empty"

    if not use_offline_tools():
        try:
            with trace_substep("respond_stat", kind="agent", input={"multi_hop": True}):
                raw = invoke_text(
                    registry().render("respond_stat"),
                    (
                        f"{_memory_context_block(state, for_stat=True, question=question)}"
                        f"Câu hỏi gốc: {question}\n"
                        f"Kết quả từng bước:\n{evidence}"
                    ),
                    max_tokens=settings.sql_respond_max_tokens,
                    substep=None,
                )
            polished = _strip_thinking(raw)
            if polished:
                return polished, "llm_text"
        except Exception as exc:
            return evidence, f"template_fallback:{type(exc).__name__}"

    return evidence, "template"


def orchestrator_collect_step_node(state: AgentState) -> dict:
    """Thu kết quả batch multi-hop; lặp orchestrator hoặc chuyển respond."""
    from src.agent.orchestrator import is_all_events_plan

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


def retrieve_docs_node(state: AgentState) -> dict:
    from src.knowledge import retrieve_docs
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    with trace_substep("retrieve_docs", kind="tool", input={"question": q}) as sub:
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
    from src.knowledge import answer_from_docs
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    cards = state.get("rows", [])
    card_ids = [str(c.get("id")) for c in cards if isinstance(c, dict) and c.get("id")]
    docs_ans = answer_from_docs(q, cards)
    dumped = docs_ans.model_dump()
    return {
        "answer": docs_ans.answer_vi,
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
    from src.agent.sql_batch import query_text_for_state

    q = state.get("question", "")
    intent = state.get("intent", "query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    q_text = query_text_for_state(state)

    with trace_substep("select_tables", kind="tool", input={"question": q_text}):
        tables = select_relevant_tables(q_text, limit=4)
    with trace_substep("build_schema_excerpt", kind="tool", input={"tables": tables}) as sub:
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
    """Vẽ chart nếu được; nếu kết quả thiếu dòng tự động fallback SQL; lỗi render → bỏ chart, vẫn để respond trả text."""
    from src.agent.chart_fallback import fallback_chart_query
    rows = list(state.get("rows") or [])
    columns = list(state.get("columns") or [])
    sql = state.get("sql") or ""
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    # Chart fallback retry nếu kết quả chưa đủ dòng
    fallback_applied = False
    if len(rows) < 2:
        with trace_substep("chart_fallback_query", kind="tool", input={"row_count": len(rows)}):
            fb_res = fallback_chart_query(question=q, sql=sql, rows=rows)
        if fb_res and fb_res.get("rows"):
            rows = fb_res["rows"]
            columns = fb_res.get("columns") or list(rows[0].keys())
            sql = fb_res.get("sql") or sql
            fallback_applied = True

    try:
        chart_type = state.get("chart_type") or _detect_chart_type(q)
        spec = plan_chart(rows, q, chart_type=chart_type)
        with trace_substep("render_png", kind="tool", input={"chart_type": getattr(spec, "chart_type", "")}) as sub:
            png_base64 = render_chart(rows, spec)
            sub["output"] = {"rendered": bool(png_base64), "png_len": len(png_base64 or "")}
        meta = spec.model_dump() if spec else {}
        ok = bool(png_base64)
        node_meta = dict(meta)
        node_meta.update({
            "user_id": user_id,
            "session_id": session_id,
            "chart_spec": meta,
            "fallback_applied": fallback_applied,
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
                    "fallback_applied": fallback_applied,
                },
                chart_png_base64=png_base64 or "",
                chart_meta=meta,
                chart_spec=meta,
                meta=node_meta,
            )],
        }
        if fallback_applied:
            res_dict["rows"] = rows
            res_dict["columns"] = columns
            res_dict["sql"] = sql
        return res_dict
    except Exception as e:
        return {
            "chart_png_base64": "",
            "chart_spec": None,
            "events": [node_event(
                "render_chart",
                input={"question": q, "columns": columns, "rows": rows, "row_count": len(rows)},
                output={"rendered": False, "error": str(e)},
                chart_png_base64="",
                chart_meta={},
                chart_spec=None,
                meta={"user_id": user_id, "session_id": session_id, "error": str(e)},
            )],
        }

_THINKING_BLOCK = re.compile(r"\x3cthink\x3e.*?\x3c/think\x3e", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Bỏ block reasoning Qwen3."""
    if re.search(r"\x3cthink\x3e", text, re.IGNORECASE) and not re.search(
        r"\x3c/think\x3e", text, re.IGNORECASE
    ):
        return ""
    return _THINKING_BLOCK.sub("", text).strip()


_STAT_MEMORY_RE = re.compile(
    r"\d[\d.,]*\s*(?:sự kiện|su kien|lượt|luot|cảnh báo|canh bao|phát hiện|phat hien)",
    re.IGNORECASE,
)


def _domains_in_text(text: str) -> set[str]:
    from src.agent.orchestrator import _DOMAIN_PHRASES

    low = (text or "").lower()
    return {tbl for phrases, tbl in _DOMAIN_PHRASES if any(p in low for p in phrases)}


def _filter_memories_for_stat(memories: list[str], question: str) -> list[str]:
    """Bỏ memory chứa số liệu thống kê hoặc domain ngoài phạm vi câu hỏi hiện tại."""
    q_domains = _domains_in_text(question)
    kept: list[str] = []
    for memory in memories:
        if _STAT_MEMORY_RE.search(memory):
            continue
        m_domains = _domains_in_text(memory)
        if q_domains and m_domains and not m_domains <= q_domains:
            continue
        kept.append(memory)
    return kept


def _rewritten_text(state: AgentState) -> str:
    rewritten = state.get("rewritten")
    if rewritten is None:
        return ""
    if hasattr(rewritten, "text"):
        return (rewritten.text or "").strip()
    if isinstance(rewritten, dict):
        return (rewritten.get("text") or "").strip()
    return ""


def _original_question(state: AgentState) -> str:
    return (state.get("original_question") or state.get("question") or "").strip()


def _effective_question(state: AgentState) -> str:
    return _rewritten_text(state) or (state.get("question") or "").strip()


def _respond_event_input(state: AgentState, **extra) -> dict:
    return {
        "question": _original_question(state),
        "rewritten_question": _effective_question(state),
        **extra,
    }


def _memory_context_block(state: AgentState, *, for_stat: bool = False, question: str = "") -> str:
    """Chèn recalled long-term memories vào prompt downstream."""
    memories = state.get("recalled_memories") or []
    if for_stat:
        memories = _filter_memories_for_stat(memories, question)
    if not memories:
        return ""
    lines = "\n".join(f"- {m}" for m in memories)
    stat_rule = ""
    if for_stat:
        stat_rule = (
            "Chỉ dùng bối cảnh người dùng khi liên quan trực tiếp; "
            "KHÔNG bổ sung số liệu ngoài dữ liệu truy vấn.\n\n"
        )
    return f"Thông tin đã biết về người dùng:\n{lines}\n\n{stat_rule}"


def respond_node(state: AgentState) -> dict:
    q_original = _original_question(state)
    q = _effective_question(state)
    error = state.get("error")
    rows = state.get("rows", [])
    columns = state.get("columns", [])
    chart_png = state.get("chart_png_base64") or ""
    plan = state.get("orchestrator_plan")
    step_results = state.get("orchestrator_step_results") or []
    respond_mode = state.get("respond_mode") or ""
    intent = state.get("intent", "query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    is_multi_respond = bool(
        state.get("multi_hop_ready")
        and step_results
        and plan
        and (getattr(plan, "is_multi", False) or len(getattr(plan, "steps", []) or []) >= 2)
    )

    from src.agent.simple_answer import try_format_simple_answer
    from src.config import settings
    from src.llm.client import invoke_text, use_offline_tools

    answer_source = "template"
    llm_used = False
    q_low = q.lower()

    if respond_mode == "inline":
        ans = (state.get("answer") or "").strip()
        if not ans and intent == "chat":
            ans = "Chào bạn! Tôi là trợ lý AI giám sát camera VMS KCN Hưng Phú. Tôi có thể hỗ trợ gì cho bạn về dữ liệu camera, sự kiện hoặc hướng dẫn sử dụng hệ thống?"
        detail = intent or "chat"
        result = Agent_Output(question=q_original, answer=ans, detail=detail)
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=_respond_event_input(state, respond_mode="inline", intent=intent),
                output={"answer_vi": ans, "answer_source": "inline"},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    if respond_mode == "out_of_scope":
        ans = (state.get("answer") or "").strip() or OUT_OF_SCOPE_REPLY
        result = Agent_Output(question=q_original, answer=ans, detail="out_of_scope")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=_respond_event_input(state, respond_mode="out_of_scope"),
                output={"answer_vi": ans, "answer_source": "out_of_scope"},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    if is_multi_respond:
        from src.agent.orchestrator import is_all_events_plan

        ans, answer_source = _synthesize_orchestrator_answer(q, step_results, state)
        check_q = f"{q} {q_original}".lower()
        if any(k in check_q for k in ("chỗ", "cho ngoi", "5 chỗ", "7 chỗ", "9 chỗ", "16 chỗ", "29 chỗ", "40 chỗ", "45 chỗ")):
            if "không có thông tin số chỗ ngồi" not in ans.lower():
                ans = f"{ans}\n(Lưu ý: Hệ thống chỉ phân loại 4 nhóm phương tiện CAR, MOTORCYCLE, TRUCK, BUS, không có thông tin số chỗ ngồi.)"
        llm_used = answer_source == "llm_text"
        agg_columns, agg_rows = _aggregate_all_events_rows(step_results) if is_all_events_plan(plan) else ([], [])
        if agg_rows:
            query_res = QueryResult(
                tool="sql_builder",
                columns=agg_columns,
                rows=[[r["domain"], r["count"]] for r in agg_rows],
                row_count=len(agg_rows),
                error="",
                reply_vi=ans,
            )
        else:
            query_res = _build_orchestrator_query_result(step_results, ans)

        chart_rows = agg_rows if agg_rows else []
        chart_spec = None
        if should_render_chart(q) and len(chart_rows) >= 2 and not chart_png:
            try:
                c_type = state.get("chart_type") or _detect_chart_type(q)
                chart_spec = plan_chart(chart_rows, q, chart_type=c_type)
                chart_png = render_chart(chart_rows, chart_spec) or ""
            except Exception:
                chart_png = ""
                chart_spec = None

        if chart_png and len(chart_rows) > 1 and should_render_chart(q):
            ans = f"{ans} Biểu đồ phân bố theo loại sự kiện ({len(chart_rows)} nhóm)."
            answer_source = "chart_template" if answer_source == "template_all_events" else answer_source

        stat = StatAnswer(
            answer_vi=ans,
            highlights=[],
            chart_requested=should_render_chart(q) or bool(chart_png),
        )
        ans = stat.answer_vi
        result = Agent_Output(question=q_original, answer=ans, query=query_res, detail="orchestrator:multi")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        chart_meta = chart_spec.model_dump() if chart_spec else {}
        return {
            "result": result,
            "chart_png_base64": chart_png,
            "events": [node_event(
                "respond",
                input=_respond_event_input(
                    state,
                    respond_mode="multi",
                    orchestrator_step_results=step_results,
                    step_count=len(step_results),
                ),
                output={
                    "answer_vi": ans,
                    "answer_source": answer_source,
                    "stat_answer": stat.model_dump(),
                    "query": query_res.model_dump(),
                },
                chart_png_base64=chart_png,
                chart_meta=chart_meta,
                chart_spec=chart_meta,
                meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id, "is_multi": True},
            )],
        }

    if respond_mode == "docs":
        docs_payload = state.get("docs_answer") or {}
        ans = (state.get("answer") or docs_payload.get("answer_vi") or "").strip()
        if not ans:
            ans = "Không tìm thấi tài liệu hướng dẫn phù hợp."
        result = Agent_Output(question=q_original, answer=ans, detail="docs")
        emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
        return {
            "result": result,
            "events": [node_event(
                "respond",
                input=_respond_event_input(state, respond_mode="docs"),
                output={"answer_vi": ans, "docs_answer": docs_payload},
                meta={"llm_used": False, "user_id": user_id, "session_id": session_id},
            )],
        }

    from src.agent.camera_registry import (
        is_camera_count_query,
        is_camera_list_query,
        format_camera_count_answer,
        format_camera_list_answer,
    )

    if is_camera_count_query(q):
        ans, rows, columns = format_camera_count_answer()
        answer_source = "master_registry"
    elif is_camera_list_query(q) or (
        "danh sách" in q_low and "camera" in q_low and any(k in q_low for k in ("khu vực", "hợp lệ", "hiện có", "tất cả"))
    ):
        ans, rows, columns = format_camera_list_answer()
        answer_source = "master_registry"
    elif error:
        ans = f"Lỗi khi truy vấn: {error}"
        answer_source = "error"
    elif not rows:
        from src.guardrails import empty_stat_reply

        ans = empty_stat_reply()
        answer_source = "empty"
    else:
        with trace_substep("simple_answer", kind="tool", input={"row_count": len(rows)}) as sub:
            simple_ans = try_format_simple_answer(q, rows)
            sub["output"] = {"matched": simple_ans is not None}
        if chart_png and len(rows) > 1 and should_render_chart(q):
            label = (columns[0] if columns else "dữ liệu").replace("_", " ")
            ans = f"Biểu đồ phân bố theo {label} ({len(rows)} nhóm)."
            answer_source = "chart_template"
            llm_used = False
        elif simple_ans is not None:
            ans = simple_ans
            if chart_png:
                ans = f"{ans} Biểu đồ đã tạo từ kết quả truy vấn."
            answer_source = "template_simple"
            llm_used = False
        else:
            lines = [", ".join(f"{c}={r[c]}" for c in columns) for r in rows[:20]]
            template_ans = f"Kết quả ({len(rows)} dòng):\n" + "\n".join(lines)
            ans = template_ans

            if not use_offline_tools():
                llm_used = True
                try:
                    with trace_substep("respond_stat", kind="agent", input={"row_count": len(rows)}):
                        raw = invoke_text(
                            registry().render("respond_stat"),
                            (
                                f"{_memory_context_block(state, for_stat=True, question=q)}"
                                f"Câu hỏi: {q}\nDữ liệu:\n{template_ans}"
                            ),
                            max_tokens=settings.sql_respond_max_tokens,
                            substep=None,
                        )
                    polished = _strip_thinking(raw)
                    if polished:
                        ans = polished
                        answer_source = "llm_text"
                except Exception as exc:
                    answer_source = f"template_fallback:{type(exc).__name__}"


    check_q = f"{q} {q_original}".lower()
    if any(k in check_q for k in ("chỗ", "cho ngoi", "5 chỗ", "7 chỗ", "9 chỗ", "16 chỗ", "29 chỗ", "40 chỗ", "45 chỗ")):
        if "không có thông tin số chỗ ngồi" not in ans.lower():
            ans = f"{ans}\n(Lưu ý: Hệ thống chỉ phân loại 4 nhóm phương tiện CAR, MOTORCYCLE, TRUCK, BUS, không có thông tin số chỗ ngồi.)"


    stat = StatAnswer(
        answer_vi=ans,
        highlights=[],
        chart_requested=should_render_chart(q) or bool(state.get("chart_png_base64")),
    )
    ans = stat.answer_vi

    query_res = QueryResult(
        tool="sql_builder",
        columns=columns,
        rows=[[r[c] for c in columns] for r in rows] if rows else [],
        row_count=len(rows) if rows else 0,
        error=error or "",
        reply_vi=ans
    )
    
    result = Agent_Output(question=q_original, answer=ans, query=query_res, detail="query_data")
    emit_answer_chunks(ans, enabled=bool(state.get("stream_tokens")))
    return {
        "result": result,
        "events": [node_event(
            "respond",
            input=_respond_event_input(
                state,
                respond_mode="stat",
                columns=columns,
                rows=rows,
                row_count=len(rows),
                recalled_memories=_filter_memories_for_stat(
                    state.get("recalled_memories") or [], q
                ),
                error=error or "",
            ),
            output={
                "answer_vi": ans,
                "answer_source": answer_source,
                "stat_answer": stat.model_dump(),
                "query": query_res.model_dump(),
            },
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }

_compiled = None


def _build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    from src.agent.guardrail_nodes import (
        guardrail_input_node,
        guardrail_output_node,
    )

    graph = StateGraph(AgentState)
    graph.add_node("guardrail_input", _wrap_node("guardrail_input", guardrail_input_node))
    graph.add_node("guardrail_output", _wrap_node("guardrail_output", guardrail_output_node))
    graph.add_node("recall", _wrap_node("recall", recall_node))
    graph.add_node("rewrite", _wrap_node("rewrite", rewrite_node))
    graph.add_node("classify", _wrap_node("classify", classify_node))
    graph.add_node("respond_inline", _wrap_node("respond_inline", respond_inline_node))
    graph.add_node("orchestrator", _wrap_node("orchestrator", orchestrator_node))
    graph.add_node("orchestrator_collect", _wrap_node("orchestrator_collect", orchestrator_collect_step_node))
    graph.add_node("retrieve_schema", _wrap_node("retrieve_schema", retrieve_schema_node))
    from src.agent.generate_sql import generate_sql_node
    from src.agent.validate_sql import validate_sql_node, repair_sql_node
    from src.agent.execute_sql import execute_sql_node
    graph.add_node("generate_sql", _wrap_node("generate_sql", generate_sql_node))
    graph.add_node("validate_sql", _wrap_node("validate_sql", validate_sql_node))
    graph.add_node("repair_sql", _wrap_node("repair_sql", repair_sql_node))
    graph.add_node("execute_sql", _wrap_node("execute_sql", execute_sql_node))
    graph.add_node("render_chart", _wrap_node("render_chart", render_chart_node))
    graph.add_node("respond", _wrap_node("respond", respond_node))
    
    graph.add_node("retrieve_docs", _wrap_node("retrieve_docs", retrieve_docs_node))
    graph.add_node("answer_from_docs", _wrap_node("answer_from_docs", answer_from_docs_node))
    
    # 1. Entry Guardrail: gom check input + redact PII vào guardrail_input
    graph.add_edge(START, "guardrail_input")
    graph.add_edge("guardrail_input", "recall")
    graph.add_edge("recall", "rewrite")
    graph.add_edge("rewrite", "classify")
    
    # 2. Sau classify: chào hỏi / clarify / out_of_scope rẽ respond_inline; còn lại truyền sang orchestrator điều phối
    def route_classify(state: AgentState) -> str:
        ans = (state.get("answer") or "").strip()
        intent = state.get("intent", "query_data")
        q = state.get("question", "")
        rewritten = state.get("rewritten")
        q_text = rewritten.text if rewritten else q

        if intent == "out_of_scope" and is_stat_event_domain(q_text):
            return "orchestrator"

        if (ans and intent in ("chat", "clarify")) or intent in ("chat", "out_of_scope"):
            return "respond_inline"
        return "orchestrator"

    graph.add_conditional_edges("classify", route_classify, {
        "respond_inline": "respond_inline",
        "orchestrator": "orchestrator",
    })
    graph.add_edge("respond_inline", "respond")
    
    # 3. Orchestrator: làm trung tâm điều phối rẽ sang các nhánh thực thi (đơn pass-through, đa ý multi)
    graph.add_conditional_edges("orchestrator", route_orchestrator, {
        "query_data": "retrieve_schema",
        "docs": "retrieve_docs",
        "out": "respond_inline",
        "respond": "respond",
    })
    
    def _after_validate(state: AgentState) -> str:
        val = state.get("sql_validation") or {}
        if val.get("ok"):
            return "execute_sql"
        repair_count = int(state.get("repair_count") or 0)
        if repair_count < settings.sql_repair_max:
            return "repair_sql"
        return "respond"

    def should_render_chart_edge(state: AgentState) -> str:
        rows = state.get("rows") or []
        if not rows:
            return "respond"
        q = state.get("question", "")
        rewritten = state.get("rewritten")
        q_text = rewritten.text if rewritten else q
        if state.get("chart_requested") or should_render_chart(q_text):
            return "render_chart"
        return "respond"

    def _after_execute(state: AgentState) -> str:
        if state.get("error") and int(state.get("repair_count") or 0) < settings.sql_repair_max:
            return "repair_sql"
        if state.get("orchestrator_multi_active"):
            return "orchestrator_collect"
        return should_render_chart_edge(state)

    def _after_docs(state: AgentState) -> str:
        if state.get("orchestrator_multi_active"):
            return "orchestrator_collect"
        return "respond"

    # Query Data branch (v7 text-to-SQL: retrieve_schema -> generate_sql -> validate_sql <-> repair_sql -> execute_sql -> render_chart/respond)
    graph.add_edge("retrieve_schema", "generate_sql")
    graph.add_edge("generate_sql", "validate_sql")
    graph.add_conditional_edges("validate_sql", _after_validate, {
        "execute_sql": "execute_sql",
        "repair_sql": "repair_sql",
        "respond": "respond",
    })
    graph.add_edge("repair_sql", "validate_sql")
    graph.add_conditional_edges("execute_sql", _after_execute, {
        "repair_sql": "repair_sql",
        "render_chart": "render_chart",
        "respond": "respond",
        "orchestrator_collect": "orchestrator_collect",
    })
    graph.add_edge("render_chart", "respond")
    graph.add_edge("respond", "guardrail_output")
    graph.add_edge("guardrail_output", END)
    
    # Docs branch
    graph.add_edge("retrieve_docs", "answer_from_docs")
    graph.add_conditional_edges("answer_from_docs", _after_docs, {
        "orchestrator_collect": "orchestrator_collect",
        "respond": "respond",
    })

    graph.add_conditional_edges("orchestrator_collect", route_after_orchestrator_collect, {
        "orchestrator": "orchestrator",
        "respond": "respond",
    })

    return graph.compile(checkpointer=checkpointer)


def reset_graph() -> None:
    global _compiled
    _compiled = None


def _get_graph():
    global _compiled
    from unittest.mock import Mock
    if isinstance(_build_graph, Mock):
        return _build_graph()
    if _compiled is None:
        _compiled = _build_graph()
    return _compiled


def _fresh_invoke_state(question: str, inp: Agent_Input, uid: str, session_id: str) -> dict:
    """State khởi tạo mỗi lượt — xóa orchestrator cũ khỏi checkpointer."""
    return {
        "question": question,
        "original_question": question,
        "rewritten": None,
        "user_id": uid,
        "session_id": session_id,
        "stream_tokens": getattr(inp, "stream_tokens", False),
        "events": [],
        "sql": "",
        "repair_count": 0,
        "error": "",
        "rows": [],
        "columns": [],
        "orchestrator_plan": None,
        "orchestrator_step_index": 0,
        "orchestrator_batch_sub_questions": [],
        "orchestrator_batch_end_index": 0,
        "orchestrator_step_results": [],
        "orchestrator_multi_active": False,
        "sql_batch": [],
        "sql_batch_results": [],
        "multi_hop_ready": False,
        "intent": "",
        "chart_requested": False,
        "chart_type": None,
        "answer": "",
        "respond_mode": "",
        "docs_answer": None,
        "guardrail_in_scope": True,
    }


def run_agent(inp: Agent_Input, parent_span: Any = None, session_id: str = "default", user_id: str | None = None) -> Agent_Output:
    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}
    token = bind_trace_root(parent_span)
    try:
        state = _get_graph().invoke(
            _fresh_invoke_state(question, inp, uid, session_id),
            config=config,
        )
        result = state.get("result")
        if result is None:
            raise RuntimeError("Pipeline không trả về kết quả.")
        threading.Thread(
            target=run_store_extract,
            args=(uid, session_id, question, result, parent_span),
            daemon=True,
        ).start()
        return result
    finally:
        reset_trace_root(token)


def run_agent_stream(inp: Agent_Input, parent_span: Any = None, session_id: str = "default", user_id: str | None = None):
    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}
    
    q = queue.Queue()
    _stream_queue.set(q)
    token = bind_trace_root(parent_span)
    ctx = contextvars.copy_context()
    
    def target():
        try:
            res = ctx.run(
                _get_graph().invoke,
                _fresh_invoke_state(question, inp, uid, session_id),
                config=config,
            )
            if res and "result" in res:
                q.put({"__final_result__": res["result"]})
                for store_ev in run_store_extract(
                    uid, session_id, question, res["result"], parent_span
                ):
                    q.put(store_ev)
        except Exception as e:
            from src.main import _format_error_message
            msg = _format_error_message(e)
            q.put({"node_id": "error", "status": "done", "output": msg})
            q.put({"node_id": "__answer__", "status": "error", "output": msg, "detail": {"status": "error"}})
        finally:
            q.put(None)
            
    t = threading.Thread(target=target)
    t.start()
    
    try:
        while True:
            ev = q.get()
            if ev is None:
                break
            yield ev
    finally:
        reset_trace_root(token)
    
    t.join()


def save_graph_visualization(path: str = "graph.png") -> str:
    """Xuất sơ đồ LangGraph: PNG + Mermaid source + HTML xem trên browser."""
    graph = _get_graph().get_graph()
    mermaid_code = graph.draw_mermaid()
    base = path.rsplit(".", 1)[0]
    mmd_path = f"{base}.mmd"
    png_path = path if path.endswith(".png") else f"{base}.png"
    html_path = f"{base}_diagram.html"

    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid_code)
    with open(png_path, "wb") as f:
        f.write(graph.draw_mermaid_png())
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(
            "<!DOCTYPE html><html lang=\"vi\"><head><meta charset=\"UTF-8\">"
            "<title>Agent graph v5</title>"
            "<script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>"
            "</head><body><div class=\"mermaid\">\n"
            f"{mermaid_code}\n"
            "</div><script>mermaid.initialize({{startOnLoad:true}});</script></body></html>"
        )
    return png_path


if __name__ == "__main__":
    png = save_graph_visualization("graph.png")
    print(f"Exported: {png}, graph.mmd, graph_diagram.html")
