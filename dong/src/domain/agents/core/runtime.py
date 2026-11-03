"""SSE stream queue và wrap LangGraph nodes."""

from __future__ import annotations

import contextvars
import logging
import time
from typing import Any

from src.domain.agents.nodes.io import json_safe, node_event
from src.domain.agents.state import AgentState
from src.infra.monitoring.tracing import get_trace_parent, trace_active_parent, trace_step

logger = logging.getLogger(__name__)

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
