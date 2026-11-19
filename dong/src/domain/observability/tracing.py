"""Monitoring — Langfuse SDK trực tiếp (theo vn-stock-swarm).

* ``trace_answer`` — root một lượt chat/ask/stream.
* ``trace_step(parent, ...)`` — bước con; lồng sâu: ``trace_step(box["_span"], ...)``.
* ``current_span()`` — ``_current`` hoặc LangGraph ``trace_span``.
* ``trace_stream`` — gom token dưới parent / ``current_span()``.
* ``slim_state`` / ``llm_io_payload`` — payload an toàn cho Langfuse.

``MONITORING_ENABLED=false`` → no-op.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Literal

from src.domain.observability.redaction import redact_deep, redact_text
from src.shared.settings import settings

_current: ContextVar[Any] = ContextVar("langfuse_current_span", default=None)
_request_tokens: ContextVar[dict[str, int] | None] = ContextVar("request_tokens", default=None)

ObservationType = Literal[
    "span", "generation", "embedding", "agent", "tool", "chain", "retriever", "evaluator", "guardrail"
]


def _get_langfuse():
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        mask=lambda *, data, **_: redact_deep(data),
    )


def current_span() -> Any:
    span = _current.get()
    if span is not None:
        return span
    try:
        from langgraph.runtime import get_runtime

        return (get_runtime().context or {}).get("trace_span")
    except Exception:
        return None


def bind_trace_root(span: Any) -> Token:
    return _current.set(span)


def reset_trace_root(token: Token) -> None:
    _current.reset(token)


def add_request_tokens(usage: dict[str, int]) -> None:
    tokens = _request_tokens.get()
    if tokens is None or not isinstance(usage, dict):
        return
    tokens["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
    tokens["completion_tokens"] += int(usage.get("completion_tokens") or 0)
    tokens["total_tokens"] += int(usage.get("total_tokens") or 0)


def extract_token_usage(response: Any) -> dict[str, int]:
    empty = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    if not response:
        return empty
    raw: Any = getattr(response, "usage_metadata", None)
    if not isinstance(raw, dict):
        meta = getattr(response, "response_metadata", None)
        raw = meta.get("token_usage") if isinstance(meta, dict) else None
    if not isinstance(raw, dict) and isinstance(response, dict):
        raw = response.get("usage") or response.get("usage_metadata") or response.get("token_usage")
    if not isinstance(raw, dict):
        return empty
    p = int(raw.get("input_tokens") or raw.get("prompt_tokens") or 0)
    c = int(raw.get("output_tokens") or raw.get("completion_tokens") or 0)
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": int(raw.get("total_tokens") or p + c)}


@contextmanager
def trace_answer(
    name: str,
    question: str,
    metadata: dict[str, Any] | None = None,
    as_type: ObservationType = "agent",
    box: dict[str, Any] | None = None,
):
    """Root observation một lượt. Gán ``box["output"]`` trước khi thoát."""
    if not settings.monitoring_enabled:
        yield box if box is not None else {}
        return

    if box is None:
        box = {}
    counter = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    token_var = _request_tokens.set(counter)
    langfuse = _get_langfuse()
    start = time.perf_counter()
    span = langfuse.start_observation(
        name=name, as_type=as_type, input=question, metadata=metadata or {}
    )
    box["_span"] = span
    cur = _current.set(span)
    try:
        yield box
    except Exception as exc:
        span.update(level="ERROR", status_message=str(exc))
        raise
    finally:
        _current.reset(cur)
        usage = box.setdefault("usage", {})
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[k] = int(usage.get(k) or 0) + counter[k]
        meta = {"latency_s": time.perf_counter() - start, **usage}
        if box.get("metadata"):
            meta.update(box["metadata"])
        span.update(output=box.get("output"), metadata=meta)
        span.end()
        langfuse.flush()
        _request_tokens.reset(token_var)


@contextmanager
def trace_step(
    parent_span: Any,
    name: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    as_type: ObservationType = "span",
):
    """Child dưới ``parent_span``. ``None`` / monitoring tắt → no-op."""
    if parent_span is None or not settings.monitoring_enabled:
        yield {}
        return

    start = time.perf_counter()
    span = parent_span.start_observation(
        name=name, as_type=as_type, input=input, metadata=metadata or {}
    )
    box: dict[str, Any] = {"_span": span}
    try:
        yield box
    except Exception as exc:
        span.update(level="ERROR", status_message=str(exc))
        raise
    finally:
        meta: dict[str, Any] = {"latency_s": time.perf_counter() - start}
        if box.get("usage"):
            meta.update(box["usage"])
        if box.get("metadata"):
            meta.update(box["metadata"])
        span.update(input=box.get("input", input), output=box.get("output"), metadata=meta)
        span.end()


def trace_stream(
    name: str,
    question: str,
    tokens: Iterator[str],
    parent: Any = None,
    as_type: ObservationType = "generation",
) -> Iterator[str]:
    """Gom token → 1 observation con; flush khi xong."""
    parent_span = parent if parent is not None else current_span()
    if not settings.monitoring_enabled or parent_span is None:
        yield from tokens
        return

    langfuse = _get_langfuse()
    start = time.perf_counter()
    chunks: list[str] = []
    try:
        for token in tokens:
            chunks.append(token)
            yield token
    finally:
        span = parent_span.start_observation(
            name=name,
            as_type=as_type,
            input=question,
            output="".join(chunks),
            metadata={"latency_s": time.perf_counter() - start, "streamed": True},
        )
        span.end()
        langfuse.flush()


def slim_state(state: Mapping[str, Any]) -> dict[str, Any]:
    rows = state["rows"] if "rows" in state and isinstance(state["rows"], list) else []
    snap: dict[str, Any] = {"row_count": len(rows)}
    for key in (
        "question",
        "intent",
        "sql",
        "error",
        "repair_count",
        "orchestrator_step_index",
        "respond_mode",
        "selected_tables",
    ):
        if key in state:
            snap[key] = state[key]
    return snap


def llm_io_payload(system: str, user: str, text: str) -> dict[str, Any]:
    return {
        "input": {"system": redact_text(system or ""), "user": redact_text(user or "")},
        "output": {"text": redact_text(text or "")},
    }
