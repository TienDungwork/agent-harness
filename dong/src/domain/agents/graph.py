"""Root graph: prefix → top_supervisor → analytics_team | knowledge_team → respond.

Checkpointer, build_graph, run_agent / run_agent_stream (entrypoint), vẽ sơ đồ.
Giống vn-stock: invoke/stream + ``context={trace_span, ...}`` — không wrap node.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

from langgraph.graph import END, START, StateGraph

from src.domain.agents.analytics.graph import build_analytics_graph
from src.domain.agents.knowledge.graph import build_knowledge_graph
from src.domain.agents.nodes.guardrails import guardrail_input_node, guardrail_output_node
from src.domain.agents.nodes.memory import recall_node, run_store_extract
from src.domain.agents.nodes.respond import respond_node
from src.domain.agents.nodes.rewrite_classify import (
    classify_node,
    respond_inline_node,
    rewrite_node,
    route_classify,
)
from src.domain.agents.nodes.supervisor import orchestrator_node, route_orchestrator
from src.domain.agents.nodes.synth import (
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
    route_after_team,
)
from src.domain.agents.nodes.io import json_safe
from src.domain.agents.state import Agent_Input, Agent_Output, AgentState
from src.infra.memory.shortterm import get_checkpointer
from src.infra.prompts import resolve_prompt_version
from src.domain.observability.tracing import bind_trace_root, reset_trace_root, trace_answer
from src.shared.settings import settings

logger = logging.getLogger(__name__)

_compiled = None


def _build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    graph = StateGraph(AgentState)
    graph.add_node("guardrail_input", guardrail_input_node)
    graph.add_node("guardrail_output", guardrail_output_node)
    graph.add_node("recall", recall_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("classify", classify_node)
    graph.add_node("respond_inline", respond_inline_node)
    graph.add_node("top_supervisor", orchestrator_node)
    graph.add_node("orchestrator_collect", orchestrator_collect_step_node)
    graph.add_node("analytics_team", build_analytics_graph())
    graph.add_node("knowledge_team", build_knowledge_graph())
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "guardrail_input")
    graph.add_edge("guardrail_input", "recall")
    graph.add_edge("recall", "rewrite")
    graph.add_edge("rewrite", "classify")
    graph.add_conditional_edges(
        "classify",
        route_classify,
        {"respond_inline": "respond_inline", "top_supervisor": "top_supervisor"},
    )
    graph.add_edge("respond_inline", "respond")
    graph.add_conditional_edges(
        "top_supervisor",
        route_orchestrator,
        {
            "query_data": "analytics_team",
            "docs": "knowledge_team",
            "out": "respond_inline",
            "respond": "respond",
        },
    )
    graph.add_conditional_edges(
        "analytics_team",
        route_after_team,
        {"orchestrator_collect": "orchestrator_collect", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "knowledge_team",
        route_after_team,
        {"orchestrator_collect": "orchestrator_collect", "respond": "respond"},
    )
    graph.add_edge("respond", "guardrail_output")
    graph.add_edge("guardrail_output", END)
    graph.add_conditional_edges(
        "orchestrator_collect",
        route_after_orchestrator_collect,
        {"orchestrator": "top_supervisor", "respond": "respond"},
    )
    return graph.compile(checkpointer=checkpointer)


def reset_graph() -> None:
    global _compiled
    _compiled = None


def _get_graph():
    global _compiled
    from unittest.mock import Mock

    import src.domain.agents.graph as graph_mod

    build = graph_mod._build_graph
    if isinstance(build, Mock):
        return build()
    if _compiled is None:
        _compiled = build()
    return _compiled


def build_graph(checkpointer=None):
    """Canonical compile entry (v16)."""
    return _build_graph(checkpointer=checkpointer)


def fresh_invoke_state(question: str, inp: Agent_Input, uid: str, session_id: str) -> dict:
    """State mỗi lượt — reset orchestrator/SQL để không dính checkpointer cũ."""
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
        "access_context": getattr(inp, "access_context", None),
    }


_fresh_invoke_state = fresh_invoke_state  # alias tests cũ


def _prepare_turn(
    inp: Agent_Input,
    session_id: str,
    user_id: str | None,
    trace_metadata: dict[str, Any] | None,
) -> tuple[str, str, dict, dict, str]:
    question = (inp.question or "").strip()
    uid = user_id or getattr(inp, "user_id", "default") or "default"
    config = {"configurable": {"thread_id": session_id}}
    meta = dict(trace_metadata or {})
    prompt_version = resolve_prompt_version(uid)
    meta.setdefault("prompt_version", prompt_version)
    return question, uid, config, meta, prompt_version


def _runtime_context(
    inp: Agent_Input, uid: str, *, trace_span: Any = None, prompt_version: str | None = None
) -> dict[str, Any]:
    return {
        "trace_span": trace_span,
        "access_context": getattr(inp, "access_context", None),
        "prompt_version": prompt_version or resolve_prompt_version(uid),
    }


def _trace_output_from_result(result: Agent_Output, *, error: str = "") -> dict[str, Any]:
    if error:
        return {"status": "error", "error": error, "answer": error}
    query = getattr(result, "query", None)
    out: dict[str, Any] = {"status": "ok", "answer": getattr(result, "answer", "") or ""}
    if query:
        out["tool"] = getattr(query, "tool", "") or ""
        out["row_count"] = getattr(query, "row_count", 0) or 0
    return out


def _events_from_update(node_id: str, update: Any) -> list[dict]:
    """Map node update → SSE events (shape AgentTurnService đang đọc)."""
    if not isinstance(update, dict):
        return [{"node_id": node_id, "status": "done", "output": json_safe(update)}]
    events = update.get("events") or []
    if not events:
        payload = {k: update[k] for k in update if k not in ("events", "messages")}
        return [{"node_id": node_id, "status": "done", "input": None, "output": json_safe(payload)}]
    out = []
    for item in events:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "node_id": item.get("node_id") or node_id,
                "status": "done",
                "input": json_safe(item.get("input")),
                "output": json_safe(item.get("output")),
                "chart_png_base64": item.get("chart_png_base64"),
                "chart_url": item.get("chart_url") or "",
                "chart_meta": json_safe(item.get("chart_meta")),
                "chart_spec": json_safe(item.get("chart_spec")),
                "meta": json_safe(item.get("meta")),
            }
        )
    return out


def _unpack_stream_item(item: Any) -> tuple[str, Any] | None:
    if isinstance(item, tuple) and len(item) == 3:
        return item[1], item[2]
    if isinstance(item, tuple) and len(item) == 2:
        return item[0], item[1]
    return None


def _require_result(state_or_result: Any) -> Agent_Output:
    result = state_or_result.get("result") if isinstance(state_or_result, dict) else state_or_result
    if result is None:
        raise RuntimeError("Pipeline không trả về kết quả.")
    return result


@contextmanager
def _turn_trace(
    *,
    own_root: bool,
    parent_span: Any,
    trace_name: str,
    trace_question: str,
    meta: dict,
    trace_box: dict | None = None,
):
    """Mở root Langfuse hoặc gắn parent_span → yield (trace_dict, active_span)."""
    if own_root:
        ctx = trace_answer(trace_name, trace_question, metadata=meta, box=trace_box)
    else:
        ctx = nullcontext(trace_box if trace_box is not None else {})
    span_token = None
    with ctx as trace:
        active = parent_span
        if own_root:
            active = trace["_span"] if isinstance(trace, dict) and "_span" in trace else None
        elif active is not None:
            span_token = bind_trace_root(active)
        try:
            yield trace, active
        finally:
            if span_token is not None:
                reset_trace_root(span_token)


def _iter_graph_events(app, initial: dict, config: dict, context: dict) -> Iterator[dict]:
    """Yield SSE events realtime; cuối cùng yield ``{"__final_result__": ...}``."""
    final: Agent_Output | None = None
    for item in app.stream(
        initial, config=config, context=context, stream_mode=["updates", "custom"], subgraphs=True
    ):
        unpacked = _unpack_stream_item(item)
        if unpacked is None:
            continue
        mode, chunk = unpacked
        if mode == "custom":
            yield chunk if isinstance(chunk, dict) else {
                "node_id": "__answer__",
                "status": "chunk",
                "delta": str(chunk),
            }
        elif mode == "updates" and isinstance(chunk, dict):
            for node_id, update in chunk.items():
                if isinstance(update, dict) and update.get("result") is not None:
                    final = update["result"]
                yield from _events_from_update(node_id, update)
    if final is None:
        snap = app.get_state(config)
        vals = snap.values if snap else {}
        final = vals.get("result") if isinstance(vals, dict) else None
    yield {"__final_result__": _require_result(final)}


def run_agent(
    inp: Agent_Input,
    parent_span: Any = None,
    session_id: str = "default",
    user_id: str | None = None,
    *,
    trace_name: str = "chat",
    trace_metadata: dict[str, Any] | None = None,
) -> Agent_Output:
    """Lượt sync — ``invoke(..., context=)`` như vn-stock ainvoke."""
    question, uid, config, meta, prompt_version = _prepare_turn(inp, session_id, user_id, trace_metadata)
    own_root = parent_span is None and settings.monitoring_enabled
    with _turn_trace(
        own_root=own_root,
        parent_span=parent_span,
        trace_name=trace_name,
        trace_question=meta.get("trace_question", question),
        meta=meta,
    ) as (trace, span):
        state = _get_graph().invoke(
            fresh_invoke_state(question, inp, uid, session_id),
            config=config,
            context=_runtime_context(inp, uid, trace_span=span, prompt_version=prompt_version),
        )
        result = _require_result(state)
        if own_root and isinstance(trace, dict):
            trace["output"] = _trace_output_from_result(result)
        threading.Thread(
            target=run_store_extract, args=(uid, session_id, question, result, span), daemon=True
        ).start()
        return result


def run_agent_stream(
    inp: Agent_Input,
    parent_span: Any = None,
    session_id: str = "default",
    user_id: str | None = None,
    *,
    trace_box: dict[str, Any] | None = None,
    trace_name: str = "chat",
    trace_metadata: dict[str, Any] | None = None,
) -> Iterator[dict]:
    """SSE — ``stream(..., updates+custom, context=)`` như vn-stock astream."""
    question, uid, config, meta, prompt_version = _prepare_turn(inp, session_id, user_id, trace_metadata)
    if trace_box is None and parent_span is None and settings.monitoring_enabled:
        trace_box = {}
    own_root = parent_span is None and (trace_box is not None or settings.monitoring_enabled)

    with _turn_trace(
        own_root=own_root,
        parent_span=parent_span,
        trace_name=trace_name,
        trace_question=meta.get("trace_question", question),
        meta=meta,
        trace_box=trace_box,
    ) as (trace, span):
        try:
            final: Agent_Output | None = None
            for ev in _iter_graph_events(
                _get_graph(),
                fresh_invoke_state(question, inp, uid, session_id),
                config,
                _runtime_context(inp, uid, trace_span=span, prompt_version=prompt_version),
            ):
                if "__final_result__" in ev:
                    final = ev["__final_result__"]
                    if isinstance(trace, dict):
                        trace["output"] = _trace_output_from_result(final)
                yield ev
            if final is not None:
                yield from run_store_extract(uid, session_id, question, final, span)
        except Exception as e:
            logger.exception("run_agent_stream failed: %s", e)
            from src.main import _format_error_message

            msg = _format_error_message(e)
            if isinstance(trace, dict):
                trace["output"] = {"status": "error", "error": msg, "answer": msg}
            yield {"node_id": "error", "status": "done", "output": msg}
            yield {"node_id": "__answer__", "status": "error", "output": msg, "detail": {"status": "error"}}


def save_graph_visualization(path: str = "graph.png", *, xray: bool = True) -> str:
    """PNG qua mermaid; lỗi → ghi .mmd (như demo)."""
    g = _get_graph().get_graph(xray=xray)
    try:
        png_path = path if path.endswith(".png") else f"{path.rsplit('.', 1)[0]}.png"
        with open(png_path, "wb") as f:
            f.write(g.draw_mermaid_png())
        return png_path
    except Exception:
        mmd_path = path.rsplit(".", 1)[0] + ".mmd"
        with open(mmd_path, "w", encoding="utf-8") as f:
            f.write(g.draw_mermaid())
        return mmd_path


if __name__ == "__main__":
    print(save_graph_visualization("graph.png"))
