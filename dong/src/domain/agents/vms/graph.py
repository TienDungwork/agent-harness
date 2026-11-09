"""LangGraph VMS pipeline — build, run, stream (ai_backend-style graph.py)."""

from __future__ import annotations

# --- runtime ---
import contextvars
import logging
import time
from typing import Any

from src.domain.agents.vms.nodes.io import json_safe, node_event
from src.domain.agents.vms.state import AgentState
from src.infra.monitoring.tracing import ObservationType, _current, current_span, trace_step

_GRAPH_NODE_AS_TYPE: dict[str, ObservationType] = {
    "recall": "retriever",
    "retrieve_schema": "retriever",
    "retrieve_docs": "retriever",
    "guardrail_input": "guardrail",
    "guardrail_output": "guardrail",
}


def _graph_node_as_type(node_id: str) -> ObservationType:
    return _GRAPH_NODE_AS_TYPE.get(node_id, "chain")

logger = logging.getLogger(__name__)

from src.domain.agents.vms.stream import _stream_queue, emit_answer_chunks  # noqa: E402




def _wrap_node(node_id: str, func):
    def wrapper(state: AgentState):
        import time
        t0 = time.perf_counter()
        q = _stream_queue.get()
        parent = state.get("_trace_span") or current_span()
        user_id = state.get("user_id") or "default"
        session_id = state.get("session_id") or "default"
        if q is not None:
            q.put({"node_id": node_id, "status": "running"})

        with trace_step(
            parent,
            node_id,
            metadata={"user_id": user_id, "session_id": session_id},
            as_type=_graph_node_as_type(node_id),
        ) as step:
            node_token = _current.set(step["_span"]) if step.get("_span") else None
            try:
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
            finally:
                if node_token is not None:
                    try:
                        _current.reset(node_token)
                    except ValueError:
                        pass

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

# --- wiring ---
from langgraph.graph import END, START, StateGraph

from src.domain.agents.vms.nodes.memory import recall_node
from src.domain.agents.multi_agent.core import orchestrator_node, route_orchestrator
from src.domain.agents.multi_agent.synth import (
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
)
from src.domain.agents.docs_agent.graph import answer_from_docs_node, retrieve_docs_node
from src.domain.agents.sql_agent.graph import retrieve_schema_node
from src.domain.agents.vms.nodes.render_chart import render_chart_node
from src.domain.agents.vms.nodes.respond import respond_node
from src.domain.agents.vms.nodes.rewrite_classify import (
    classify_node,
    respond_inline_node,
    rewrite_node,
)
from src.domain.agents.vms.nodes.intent import is_stat_event_domain
from src.domain.agents.vms.state import AgentState
from src.infra.chart.render import should_render_chart
from src.shared.config import settings
from src.infra.memory.shortterm import get_checkpointer

_compiled = None


def _build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    from src.domain.agents.vms.nodes.guardrails import (
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
    from src.domain.agents.sql_agent.graph import generate_sql_node
    from src.domain.agents.sql_agent.graph import validate_sql_node, repair_sql_node
    from src.domain.agents.sql_agent.graph import execute_sql_node
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

    import src.domain.agents.vms.graph as graph_mod

    build = graph_mod._build_graph
    if isinstance(build, Mock):
        return build()
    if _compiled is None:
        _compiled = build()
    return _compiled


# --- run ---
import logging
import queue
import threading
from contextlib import nullcontext
from typing import Any

logger = logging.getLogger(__name__)

from src.domain.agents.vms.nodes.memory import run_store_extract
from src.domain.agents.vms.state import Agent_Input, Agent_Output
from src.shared.config import settings
from src.infra.monitoring.tracing import bind_trace_root, reset_trace_root


def _trace_output_from_result(result: Agent_Output, *, status: str = "ok", error: str = "") -> dict[str, Any]:
    query = getattr(result, "query", None)
    out: dict[str, Any] = {"status": status}
    if error:
        out["error"] = error
        out["answer"] = error
    else:
        out["answer"] = getattr(result, "answer", "") or ""
        if query:
            out["tool"] = getattr(query, "tool", "") or ""
            out["row_count"] = getattr(query, "row_count", 0) or 0
    return out

def _fresh_invoke_state(question: str, inp: Agent_Input, uid: str, session_id: str) -> dict:
    """State khởi tạo mỗi lượt — xóa orchestrator cũ khỏi checkpointer."""
    return {
        "question": question,
        "original_question": question,
        "rewritten": getattr(inp, "rewritten", None),
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


def run_agent(
    inp: Agent_Input,
    parent_span: Any = None,
    session_id: str = "default",
    user_id: str | None = None,
    *,
    trace_name: str = "chat",
    trace_metadata: dict[str, Any] | None = None,
) -> Agent_Output:
    from src.infra.monitoring.tracing import trace_answer

    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}
    meta = dict(trace_metadata or {})
    trace_question = meta.get("trace_question", question)
    own_root = parent_span is None and settings.monitoring_enabled
    trace_ctx = (
        trace_answer(trace_name, trace_question, metadata=meta)
        if own_root
        else nullcontext({})
    )

    with trace_ctx as trace_box:
        active_span = parent_span
        if own_root:
            active_span = trace_box.get("_span")
        span_token = None
        if not own_root and active_span is not None:
            span_token = bind_trace_root(active_span)
        try:
            state = _get_graph().invoke(
                _fresh_invoke_state(question, inp, uid, session_id),
                config=config,
            )
            result = state.get("result")
            if result is None:
                raise RuntimeError("Pipeline không trả về kết quả.")
            if own_root:
                trace_box["output"] = _trace_output_from_result(result)
            threading.Thread(
                target=run_store_extract,
                args=(uid, session_id, question, result, active_span),
                daemon=True,
            ).start()
            return result
        finally:
            if span_token is not None:
                reset_trace_root(span_token)


def run_agent_stream(
    inp: Agent_Input,
    parent_span: Any = None,
    session_id: str = "default",
    user_id: str | None = None,
    *,
    trace_box: dict[str, Any] | None = None,
    trace_name: str = "chat",
    trace_metadata: dict[str, Any] | None = None,
):
    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}

    q = queue.Queue()
    meta = dict(trace_metadata or {})
    if trace_box is None and parent_span is None and settings.monitoring_enabled:
        trace_box = {}
    use_worker_trace = trace_box is not None and parent_span is None

    def target():
        from src.infra.monitoring.tracing import trace_answer

        _stream_queue.set(q)
        span_token = None
        active_span = parent_span
        trace_ctx = nullcontext({})
        if use_worker_trace:
            trace_ctx = trace_answer(
                trace_name,
                meta.get("trace_question", question),
                metadata=meta,
                box=trace_box,
            )
        try:
            with trace_ctx as t:
                if use_worker_trace:
                    active_span = t.get("_span")
                elif active_span is not None:
                    span_token = bind_trace_root(active_span)
                try:
                    res = _get_graph().invoke(
                        _fresh_invoke_state(question, inp, uid, session_id),
                        config=config,
                    )
                    if res and "result" in res:
                        result = res["result"]
                        if trace_box is not None:
                            trace_box["output"] = _trace_output_from_result(result)
                        q.put({"__final_result__": result})
                        for store_ev in run_store_extract(
                            uid, session_id, question, res["result"], active_span
                        ):
                            q.put(store_ev)
                except Exception as e:
                    logger.exception("run_agent_stream worker failed: %s", e)
                    from src.main import _format_error_message
                    msg = _format_error_message(e)
                    if trace_box is not None:
                        trace_box["output"] = {"status": "error", "error": msg, "answer": msg}
                    q.put({"node_id": "error", "status": "done", "output": msg})
                    q.put({"node_id": "__answer__", "status": "error", "output": msg, "detail": {"status": "error"}})
                finally:
                    if span_token is not None:
                        reset_trace_root(span_token)
        finally:
            q.put(None)

    t = threading.Thread(target=target)
    t.start()

    token = None
    if parent_span is not None and not use_worker_trace:
        token = bind_trace_root(parent_span)
    try:
        while True:
            ev = q.get()
            if ev is None:
                break
            yield ev
    finally:
        t.join()
        if token is not None:
            reset_trace_root(token)


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

# --- facade re-exports (tests / callers) ---
from src.domain.agents.vms.tools import memory_context_block as _memory_context_block
from src.domain.agents.vms.tools import strip_thinking as _strip_thinking
from src.domain.agents.vms.nodes.memory import (
    extract_memory_node,
    recall_memory_node,
    recall_node,
    run_store_extract,
)
from src.domain.agents.docs_agent.graph import answer_from_docs_node, retrieve_docs_node
from src.domain.agents.sql_agent.graph import retrieve_schema_node
from src.domain.agents.vms.nodes.render_chart import render_chart_node
from src.domain.agents.vms.nodes.respond import respond_node
from src.domain.agents.vms.nodes.rewrite_classify import (
    classify_node,
    respond_inline_node,
    rewrite_node,
    route_intent,
)
from src.domain.agents.multi_agent.core import orchestrator_node, route_orchestrator
from src.domain.agents.multi_agent.synth import (
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
)
from src.domain.agents.vms.nodes.intent import classify_intent_safe, sanitize_intent_result
from src.domain.agents.vms.nodes.rewrite import rewrite_question
from src.domain.agents.vms.state import Agent_Input, Agent_Output, AgentState
from src.infra.chart.render import render_chart
from src.infra.db.executor import execute_sql

__all__ = [
    "Agent_Input",
    "Agent_Output",
    "AgentState",
    "run_agent",
    "run_agent_stream",
    "_build_graph",
    "_get_graph",
    "reset_graph",
    "_compiled",
    "_fresh_invoke_state",
    "_stream_queue",
    "_wrap_node",
    "emit_answer_chunks",
    "recall_node",
    "recall_memory_node",
    "extract_memory_node",
    "run_store_extract",
    "rewrite_node",
    "classify_node",
    "respond_inline_node",
    "route_intent",
    "orchestrator_node",
    "route_orchestrator",
    "orchestrator_collect_step_node",
    "route_after_orchestrator_collect",
    "retrieve_docs_node",
    "answer_from_docs_node",
    "retrieve_schema_node",
    "render_chart_node",
    "respond_node",
    "save_graph_visualization",
    "classify_intent_safe",
    "rewrite_question",
    "execute_sql",
    "render_chart",
    "_memory_context_block",
    "_strip_thinking",
]

if __name__ == "__main__":
    png = save_graph_visualization("graph.png")
    print(f"Exported: {png}, graph.mmd, graph_diagram.html")
