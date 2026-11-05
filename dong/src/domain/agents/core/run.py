"""run_agent / run_agent_stream entrypoints."""

from __future__ import annotations

import logging
import queue
import threading
from contextlib import nullcontext
from typing import Any

logger = logging.getLogger(__name__)

from src.domain.agents.core.wiring import _build_graph, _get_graph
from src.domain.agents.nodes.memory import run_store_extract
from src.domain.agents.state import Agent_Input, Agent_Output
from src.domain.agents.core.runtime import _stream_queue
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
