"""Graph Agent v5 — LangGraph pipeline thay thế ReAct.

Pipeline chính:
  START → rewrite → classify → [route]
    - query_data: retrieve_schema → plan_query → validate → execute → [render_chart] → respond → END
    - docs: retrieve_docs → answer_from_docs → END
    - out: out_of_scope_node → END
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
from src.chart.render import should_render_chart, plan_chart, render_chart
from src.llm.schemas import ChartSpec, OrchestratorPlan, QueryResult, RewrittenQuestion, StatAnswer
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

class Agent_Output(BaseModel):
    question: str
    answer: str
    query: QueryResult | None = None
    detail: str = ""

class AgentState(TypedDict, total=False):
    question: str
    rewritten: RewrittenQuestion
    intent: str
    answer: str
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    recalled_memories: list[str]
    extracted_memories: list[str]
    orchestrator_plan: OrchestratorPlan
    
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
    
    events: Annotated[list[dict], operator.add]
    result: Agent_Output
    _trace_span: Any

_stream_queue = contextvars.ContextVar("_stream_queue", default=None)


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
    from src.memory.longterm import recall_long_term

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
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
        "recalled_memories": memories,
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
    from src.memory.extract import extract_and_store_memory, memory_detail_includes_answer

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
    from src.llm.client import use_offline_tools

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    rewritten = state.get("rewritten")
    llm_used = False
    is_chat = is_chat_greeting(q)
    if not rewritten:
        if not is_chat:
            llm_used = not use_offline_tools()
        rewritten = rewrite_question(q)
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
                **({"skipped": True} if is_chat else {}),
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
    
    out_state = {
        "intent": intent,
        "events": [node_event(
            "classify",
            input={"rewritten_text": rewritten.text, "rewritten": rewritten.model_dump()},
            output={"intent": intent, "reason": res.reason, "answer": res.answer},
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }
    if res.answer:
        out_state["answer"] = res.answer
    else:
        out_state["answer"] = ""
        
    return out_state

def respond_inline_node(state: AgentState) -> dict:
    q = state.get("question", "")
    ans = (state.get("answer") or "").strip()
    intent = state.get("intent", "chat")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    
    if not ans and intent == "chat":
        ans = "Chào bạn! Tôi là trợ lý AI giám sát camera VMS KCN Hưng Phú. Tôi có thể hỗ trợ gì cho bạn về dữ liệu camera, sự kiện hoặc hướng dẫn sử dụng hệ thống?"

    result = Agent_Output(
        question=q,
        answer=ans,
        detail=intent or "chat",
    )
    
    return {
        "result": result,
        "answer": ans,
        "events": [node_event(
            "respond_inline",
            input={"question": q, "intent": intent},
            output={"answer": ans},
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

    if intent == "out_of_scope" and is_stat_event_domain(q_text):
        plan = plan_orchestration(q_text)
    elif intent == "out_of_scope":
        plan = OrchestratorPlan(steps=[], is_multi=False, reason="out_of_scope")
    else:
        plan = plan_orchestration(q_text)

    return {
        "orchestrator_plan": plan,
        "events": [node_event(
            "orchestrator",
            input={"question": q_text, "intent": intent},
            output={"orchestrator_plan": plan.model_dump()},
            meta={"llm_used": llm_used, "user_id": user_id, "session_id": session_id},
        )],
    }

def route_orchestrator(state: AgentState) -> str:
    intent = state.get("intent", "query_data")
    rewritten = state.get("rewritten")
    q_text = rewritten.text if rewritten else state.get("question", "")

    plan: OrchestratorPlan | None = state.get("orchestrator_plan")
    if intent == "out_of_scope":
        if is_stat_event_domain(q_text):
            return "query_data"
        return "out"

    if plan and (plan.is_multi or len(plan.steps) >= 2):
        return "multi"

    if plan and plan.steps:
        agent = plan.steps[0].agent
        if agent == "docs":
            return "docs"
        elif agent == "query_data":
            return "query_data"

    if intent in ("how_to", "troubleshoot", "concept"):
        return "docs"
    return "query_data"


def orchestrator_respond_node(state: AgentState) -> dict:
    from src.agent.execute_sql import execute_sql_node
    from src.agent.generate_sql import generate_sql_node
    from src.agent.validate_sql import validate_and_repair_sql
    from src.knowledge.answer import answer_from_docs
    from src.knowledge.retrieval import retrieve_docs
    from src.llm.client import invoke_text, use_offline_tools

    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    plan: OrchestratorPlan | None = state.get("orchestrator_plan")

    query_res: QueryResult | None = None
    sub_events: list[dict] = []
    step_answers: list[str] = []
    rows: list = []
    columns: list = []

    steps = plan.steps if plan else []
    for idx, step in enumerate(steps):
        sub_q = step.sub_question
        if step.agent == "docs":
            cards = retrieve_docs(sub_q)
            docs_ans = answer_from_docs(sub_q, cards)
            docs_text = docs_ans.answer_vi
            step_answers.append(docs_text)
            sub_events.append(node_event(
                f"orchestrator_docs_step_{idx+1}",
                input={"sub_question": sub_q, "agent": "docs"},
                output={"docs_answer": docs_ans.model_dump()},
                meta={"user_id": user_id, "session_id": session_id},
            ))
        elif step.agent == "query_data":
            tables = select_relevant_tables(sub_q)
            schema = build_schema_excerpt(tables)
            gen_out = generate_sql_node({
                "question": sub_q,
                "schema_excerpt": schema,
                "user_id": user_id,
                "session_id": session_id,
            })
            sub_events.extend(gen_out.get("events") or [])
            sql_candidate = gen_out.get("sql") or ""

            repaired_sql, val_res, rep_cnt, val_events = validate_and_repair_sql(
                sql_candidate,
                sub_q,
                schema_excerpt=schema,
                user_id=user_id,
                session_id=session_id,
            )
            sub_events.extend(val_events)

            exec_res = execute_sql_node({
                "sql": repaired_sql,
                "user_id": user_id,
                "session_id": session_id,
            })
            step_rows = exec_res.get("rows") or []
            step_columns = exec_res.get("columns") or []
            if step_rows:
                rows = step_rows
                columns = step_columns
            err = exec_res.get("error") if not val_res.ok or exec_res.get("error") else ""

            if err:
                query_ans_vi = f"Lỗi khi truy vấn số liệu: {err}"
            elif not step_rows:
                from src.guardrails import empty_stat_reply

                query_ans_vi = empty_stat_reply()
            else:
                lines = [", ".join(f"{c}={r[c]}" for c in step_columns) for r in step_rows[:20]]
                template_ans = f"Số liệu ({len(step_rows)} dòng):\n" + "\n".join(lines)
                query_ans_vi = template_ans
                if not use_offline_tools():
                    try:
                        raw = invoke_text(
                            registry().render("respond_stat"),
                            f"{_memory_context_block(state)}Câu hỏi: {sub_q}\nDữ liệu:\n{template_ans}",
                            substep="respond_stat",
                        )
                        polished = _strip_thinking(raw)
                        if polished:
                            query_ans_vi = polished
                    except Exception:
                        pass

            step_answers.append(query_ans_vi)
            query_res = QueryResult(
                tool="sql_builder",
                columns=step_columns,
                rows=[[r[c] for c in step_columns] for r in step_rows] if step_rows else [],
                row_count=len(step_rows),
                error=err or "",
                reply_vi=query_ans_vi,
            )
            sub_events.append(node_event(
                f"orchestrator_query_step_{idx+1}",
                input={
                    "sub_question": sub_q,
                    "agent": "query_data",
                    "sql": exec_res.get("sql"),
                    "params": exec_res.get("params"),
                },
                output={
                    "columns": step_columns,
                    "rows": step_rows,
                    "row_count": len(step_rows),
                    "error": err or "",
                    "answer_vi": query_ans_vi,
                },
                meta={"user_id": user_id, "session_id": session_id},
            ))

    merged_answer = "\n\n".join(step_answers) if step_answers else "Không có kết quả điều phối."

    result = Agent_Output(
        question=q,
        answer=merged_answer,
        query=query_res,
        detail="orchestrator:multi",
    )

    return {
        "result": result,
        "rows": rows,
        "columns": columns,
        "events": sub_events + [node_event(
            "orchestrator_respond",
            input={
                "question": q,
                "orchestrator_plan": plan.model_dump() if plan else {},
                "step_count": len(steps),
            },
            output={
                "answer": merged_answer,
                "has_query": query_res is not None,
                "has_docs": any(s.agent == "docs" for s in steps),
                "query": query_res.model_dump() if query_res else None,
            },
            meta={"user_id": user_id, "session_id": session_id, "is_multi": True},
        )],
    }

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
    result = Agent_Output(question=q, answer=docs_ans.answer_vi, detail="docs")
    return {
        "result": result,
        "events": [node_event(
            "answer_from_docs",
            input={"question": q, "cards": cards, "card_ids": card_ids},
            output={"docs_answer": docs_ans.model_dump()},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }

def out_of_scope_node(state: AgentState) -> dict:
    q = state.get("question", "")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    result = Agent_Output(question=q, answer=OUT_OF_SCOPE_REPLY, detail="out_of_scope")
    return {
        "result": result,
        "events": [node_event(
            "out_of_scope",
            input={"question": q},
            output={"answer": OUT_OF_SCOPE_REPLY, "intent": "out_of_scope"},
            meta={"user_id": user_id, "session_id": session_id},
        )],
    }

def retrieve_schema_node(state: AgentState) -> dict:
    q = state.get("question", "")
    intent = state.get("intent", "query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    rewritten = state.get("rewritten")
    if rewritten is not None:
        if hasattr(rewritten, "text"):
            q_text = rewritten.text or q
        elif isinstance(rewritten, dict):
            q_text = rewritten.get("text") or q
        elif isinstance(rewritten, str):
            q_text = rewritten or q
        else:
            q_text = q
    else:
        q_text = q

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
        spec = plan_chart(rows, q)
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


def _memory_context_block(state: AgentState) -> str:
    """Chèn recalled long-term memories vào prompt downstream."""
    memories = state.get("recalled_memories") or []
    if not memories:
        return ""
    lines = "\n".join(f"- {m}" for m in memories)
    return f"Thông tin đã biết về người dùng:\n{lines}\n\n"


def respond_node(state: AgentState) -> dict:
    q = state.get("question", "")
    error = state.get("error")
    rows = state.get("rows", [])
    columns = state.get("columns", [])
    chart_png = state.get("chart_png_base64") or ""
    
    from src.agent.simple_answer import try_format_simple_answer
    from src.config import settings
    from src.llm.client import invoke_text, use_offline_tools
    
    answer_source = "template"
    llm_used = False
    q_low = q.lower()
    is_cam_list_query = "danh sách" in q_low and "camera" in q_low and any(k in q_low for k in ("khu vực", "hợp lệ", "hiện có", "tất cả"))

    if error:
        ans = f"Lỗi khi truy vấn: {error}"
        answer_source = "error"
    elif is_cam_list_query:
        from pathlib import Path
        import yaml
        reg_path = Path(__file__).resolve().parent.parent.parent / "resource" / "db" / "camera_registry.yaml"
        if reg_path.exists():
            try:
                reg = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
                cams = reg.get("cameras", [])
                area = reg.get("area_name", "Sản xuất & lắp ráp")
                cam_names = [c.get("camera_name") for c in cams if c.get("camera_name")]
                zones = [f"{z.get('zone_code')} ({z.get('camera_name')})" for z in reg.get("virtual_zones", [])]
                ans = (
                    f"Danh sách các khu vực và camera hợp lệ hiện có:\n"
                    f"- Khu vực: {area}\n"
                    f"- Danh sách {len(cam_names)} camera: {', '.join(cam_names)}\n"
                    f"- Khu vực hàng rào ảo / vùng cấm: {', '.join(zones)}."
                )
                columns = ["camera_name", "area", "status", "ai_service"]
                rows = [
                    {
                        "camera_name": c.get("camera_name", ""),
                        "area": c.get("area", area),
                        "status": c.get("status", "ONLINE"),
                        "ai_service": c.get("ai_service", ""),
                    }
                    for c in cams
                ]
                answer_source = "master_registry"
            except Exception:
                ans = f"Danh sách camera: {len(rows)} bản ghi."
                answer_source = "master_registry_fallback"
        else:
            ans = f"Danh sách camera: {len(rows)} bản ghi."
            answer_source = "master_registry_fallback"
    elif not rows:
        from src.guardrails import empty_stat_reply

        ans = empty_stat_reply()
        answer_source = "empty"
    else:
        with trace_substep("simple_answer", kind="tool", input={"row_count": len(rows)}) as sub:
            simple_ans = try_format_simple_answer(q, rows)
            sub["output"] = {"matched": simple_ans is not None}
        if simple_ans is not None:
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
                            f"{_memory_context_block(state)}Câu hỏi: {q}\nDữ liệu:\n{template_ans}",
                            max_tokens=settings.sql_respond_max_tokens,
                            substep=None,
                        )
                    polished = _strip_thinking(raw)
                    if polished:
                        ans = polished
                        answer_source = "llm_text"
                except Exception as exc:
                    answer_source = f"template_fallback:{type(exc).__name__}"


    if any(k in q_low for k in ("chỗ", "cho ngoi", "5 chỗ", "7 chỗ", "9 chỗ", "16 chỗ", "29 chỗ", "40 chỗ", "45 chỗ")):
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
    
    result = Agent_Output(question=q, answer=ans, query=query_res, detail="query_data")
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"
    return {
        "result": result,
        "events": [node_event(
            "respond",
            input={
                "question": q,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "recalled_memories": state.get("recalled_memories") or [],
                "error": error or "",
            },
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

    graph = StateGraph(AgentState)
    graph.add_node("recall", _wrap_node("recall", recall_node))
    graph.add_node("rewrite", _wrap_node("rewrite", rewrite_node))
    graph.add_node("classify", _wrap_node("classify", classify_node))
    graph.add_node("respond_inline", _wrap_node("respond_inline", respond_inline_node))
    graph.add_node("orchestrator", _wrap_node("orchestrator", orchestrator_node))
    graph.add_node("orchestrator_respond", _wrap_node("orchestrator_respond", orchestrator_respond_node))
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
    
    graph.add_node("out_of_scope", _wrap_node("out_of_scope", out_of_scope_node))
    
    graph.add_edge(START, "recall")
    graph.add_edge("recall", "rewrite")
    graph.add_edge("rewrite", "classify")
    
    def route_classify(state: AgentState) -> str:
        ans = (state.get("answer") or "").strip()
        intent = state.get("intent", "query_data")
        if (ans and intent in ("chat", "clarify")) or intent == "chat":
            return "respond_inline"

        from src.agent.orchestrator import is_multi_question
        q = state.get("question", "")
        rewritten = state.get("rewritten")
        q_text = rewritten.text if rewritten else q

        if is_multi_question(q_text):
            return "orchestrator"

        if intent == "query_data":
            return "retrieve_schema"
        elif intent in ("how_to", "troubleshoot", "concept"):
            from src.agent.intent import is_stat_event_domain
            if is_stat_event_domain(q_text):
                return "retrieve_schema"
            return "retrieve_docs"
        elif intent == "out_of_scope":
            from src.agent.intent import is_stat_event_domain
            if is_stat_event_domain(q_text):
                return "retrieve_schema"
            return "out_of_scope"

        return "orchestrator"

    graph.add_conditional_edges("classify", route_classify, {
        "respond_inline": "respond_inline",
        "retrieve_schema": "retrieve_schema",
        "retrieve_docs": "retrieve_docs",
        "out_of_scope": "out_of_scope",
        "orchestrator": "orchestrator",
    })
    graph.add_edge("respond_inline", END)
    
    graph.add_conditional_edges("orchestrator", route_orchestrator, {
        "query_data": "retrieve_schema",
        "docs": "retrieve_docs",
        "out": "out_of_scope",
        "multi": "orchestrator_respond",
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
        if should_render_chart(q_text):
            return "render_chart"
        return "respond"

    def _after_execute(state: AgentState) -> str:
        if state.get("error") and int(state.get("repair_count") or 0) < settings.sql_repair_max:
            return "repair_sql"
        return should_render_chart_edge(state)

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
    })
    graph.add_edge("render_chart", "respond")
    graph.add_edge("respond", END)
    
    # Docs branch
    graph.add_edge("retrieve_docs", "answer_from_docs")
    graph.add_edge("answer_from_docs", END)
    
    # Multi orchestrator branch
    graph.add_edge("orchestrator_respond", END)

    graph.add_edge("out_of_scope", END)
    
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


def run_agent(inp: Agent_Input, parent_span: Any = None, session_id: str = "default", user_id: str | None = None) -> Agent_Output:
    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}
    token = bind_trace_root(parent_span)
    try:
        state = _get_graph().invoke(
            {
                "question": question,
                "rewritten": inp.rewritten,
                "user_id": uid,
                "session_id": session_id,
                "events": [],
                "sql": "",
                "repair_count": 0,
                "error": "",
                "rows": [],
                "columns": [],
            },
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
                {
                    "question": question,
                    "rewritten": inp.rewritten,
                    "user_id": uid,
                    "session_id": session_id,
                    "events": [],
                    "sql": "",
                    "repair_count": 0,
                    "error": "",
                    "rows": [],
                    "columns": [],
                },
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
