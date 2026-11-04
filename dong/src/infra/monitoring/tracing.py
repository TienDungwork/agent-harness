"""Monitoring — Langfuse SDK trực tiếp (vn-stock style).

* ``trace_answer`` — root một lượt chat/ask.
* ``current_span()`` — span đang mở (``_current`` hoặc LangGraph ``trace_span``).
* ``trace_step(current_span(), name, as_type=...)`` — bước con; lồng sâu: ``_current.set(box["_span"])`` trong node graph.
* ``trace_stream`` — gom token dưới parent / ``current_span()``.

``MONITORING_ENABLED=false`` → no-op. Langfuse lỗi → fail-safe, không crash API.
"""

from __future__ import annotations

import contextvars
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any, Literal

from src.shared.config import settings
from src.shared.guardrails import redact_pii

logger = logging.getLogger(__name__)

_REDACT_MAX_DEPTH = 8


def _redact_deep(value: Any, _depth: int = 0) -> Any:
    if _depth >= _REDACT_MAX_DEPTH:
        return "[QUÁ SÂU — BỎ QUA]"
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {k: _redact_deep(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_deep(v, _depth + 1) for v in value]
    return value

_current: contextvars.ContextVar[Any] = contextvars.ContextVar("langfuse_current_span", default=None)
_request_tokens = contextvars.ContextVar("request_tokens", default=None)

ObservationType = Literal[
    "span",
    "generation",
    "embedding",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "guardrail",
]


_langfuse_client: Any = None


def _get_langfuse():
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    from langfuse import Langfuse

    _langfuse_client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        mask=lambda *, data, **_: _redact_deep(data),
    )
    return _langfuse_client


def current_span() -> Any:
    span = _current.get()
    if span is not None:
        return span
    try:
        from langgraph.runtime import get_runtime

        return (get_runtime().context or {}).get("trace_span")
    except Exception:  # noqa: BLE001
        return None


def bind_trace_root(span: Any):
    """Gắn span gốc (từ ``trace_answer``) cho pipeline / graph invoke."""
    return _current.set(span)


def reset_trace_root(token: contextvars.Token) -> None:
    try:
        _current.reset(token)
    except ValueError:
        pass


def add_request_tokens(usage: dict[str, int]) -> None:
    tokens = _request_tokens.get()
    if tokens is not None and isinstance(usage, dict):
        tokens["prompt_tokens"] += usage.get("prompt_tokens", 0)
        tokens["completion_tokens"] += usage.get("completion_tokens", 0)
        tokens["total_tokens"] += usage.get("total_tokens", 0)


def extract_token_usage(response: Any) -> dict[str, int]:
    if not response:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    usage_meta = getattr(response, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        p = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens") or 0
        c = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens") or 0
        tot = usage_meta.get("total_tokens") or (p + c)
        return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    resp_meta = getattr(response, "response_metadata", None)
    if isinstance(resp_meta, dict):
        tu = resp_meta.get("token_usage")
        if isinstance(tu, dict):
            p = tu.get("prompt_tokens") or tu.get("input_tokens") or 0
            c = tu.get("completion_tokens") or tu.get("output_tokens") or 0
            tot = tu.get("total_tokens") or (p + c)
            return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    if isinstance(response, dict):
        usage = response.get("usage") or response.get("usage_metadata") or response.get("token_usage")
        if isinstance(usage, dict):
            p = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            c = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            tot = usage.get("total_tokens") or (p + c)
            return {"prompt_tokens": int(p), "completion_tokens": int(c), "total_tokens": int(tot)}

    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _langfuse_propagate(meta: dict[str, Any]):
    """Langfuse 5: user/session trên root span (gọi **bên trong** ``start_as_current_observation``)."""
    from langfuse import propagate_attributes

    kw: dict[str, Any] = {}
    if meta.get("user_id"):
        kw["user_id"] = str(meta["user_id"])[:200]
    if meta.get("session_id"):
        kw["session_id"] = str(meta["session_id"])[:200]
    if not kw:
        return nullcontext()
    return propagate_attributes(**kw)


def _start_observation(parent_or_client: Any, **kwargs: Any) -> Any | None:
    try:
        return parent_or_client.start_observation(**kwargs)
    except TypeError:
        kwargs.pop("as_type", None)
        try:
            return parent_or_client.start_observation(**kwargs)
        except Exception as exc:
            logger.warning("Langfuse start_observation fail-safe: %s", exc)
            return None
    except Exception as exc:
        logger.warning("Langfuse start_observation fail-safe: %s", exc)
        return None


@contextmanager
def trace_answer(
    name: str,
    question: str,
    metadata: dict[str, Any] | None = None,
    as_type: ObservationType = "agent",
):
    if not settings.monitoring_enabled:
        yield {}
        return

    langfuse = None
    start = time.perf_counter()
    box: dict[str, Any] = {}
    meta = dict(metadata or {})
    token_counter = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    token_var_token = _request_tokens.set(token_counter)
    cur_token = None

    try:
        langfuse = _get_langfuse()
    except Exception as exc:
        logger.warning("Không thể khởi tạo Langfuse trace (fail-safe): %s", exc)
        try:
            yield box
        finally:
            try:
                _request_tokens.reset(token_var_token)
            except ValueError:
                pass
        return

    try:
        with langfuse.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=question,
            metadata=meta,
        ) as span:
            with _langfuse_propagate(meta):
                box["_span"] = span
                cur_token = _current.set(span)
                try:
                    yield box
                except Exception as exc:
                    try:
                        if box.get("output") is None:
                            box["output"] = {"error": str(exc)}
                        span.update(level="ERROR", status_message=str(exc))
                    except Exception as update_exc:
                        logger.warning("Lỗi cập nhật Langfuse ERROR span: %s", update_exc)
                    raise
                finally:
                    if "usage" not in box:
                        box["usage"] = {}
                    box["usage"]["prompt_tokens"] = box["usage"].get("prompt_tokens", 0) + token_counter["prompt_tokens"]
                    box["usage"]["completion_tokens"] = (
                        box["usage"].get("completion_tokens", 0) + token_counter["completion_tokens"]
                    )
                    box["usage"]["total_tokens"] = box["usage"].get("total_tokens", 0) + token_counter["total_tokens"]
                    try:
                        latency_s = time.perf_counter() - start
                        out = box.get("output")
                        if out is None:
                            out = {
                                "status": "incomplete",
                                "reason": "no_output_recorded",
                                "question_preview": (question or "")[:500],
                            }
                        model_name = box.get("model_name") or meta.get("model_name") or (
                            settings.model_name if settings.llm_backend == "self_hosted" else settings.llm_model
                        )
                        temperature = box.get("temperature", meta.get("temperature", settings.llm_temperature))
                        usage = box.get("usage") or {}
                        p_tokens = int(usage.get("prompt_tokens", meta.get("prompt_tokens", 0)))
                        c_tokens = int(usage.get("completion_tokens", meta.get("completion_tokens", 0)))
                        tot_tokens = int(usage.get("total_tokens", meta.get("total_tokens", p_tokens + c_tokens)))
                        meta.update({
                            "latency_s": latency_s,
                            "model_name": model_name,
                            "temperature": temperature,
                            "prompt_tokens": p_tokens,
                            "completion_tokens": c_tokens,
                            "total_tokens": tot_tokens,
                        })
                        update_kwargs: dict[str, Any] = {
                            "name": name,
                            "input": question,
                            "output": out,
                            "metadata": meta,
                            "model": model_name,
                            "model_parameters": {"temperature": temperature},
                        }
                        if isinstance(out, dict) and out.get("status") in ("error", "incomplete"):
                            update_kwargs["level"] = "ERROR"
                            update_kwargs["status_message"] = str(
                                out.get("error") or out.get("reason") or out.get("status")
                            )[:500]
                        if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                            update_kwargs["usage_details"] = {
                                "input": p_tokens,
                                "output": c_tokens,
                                "total": tot_tokens,
                            }
                        span.update(**update_kwargs)
                    except Exception as update_exc:
                        logger.warning("Lỗi kết thúc Langfuse span: %s", update_exc)
                    if cur_token is not None:
                        reset_trace_root(cur_token)
    finally:
        try:
            _request_tokens.reset(token_var_token)
        except ValueError:
            pass
        try:
            langfuse.flush()
        except Exception as flush_exc:
            logger.warning("Lỗi flush Langfuse: %s", flush_exc)


@contextmanager
def trace_step(
    parent_span: Any,
    name: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    as_type: ObservationType = "span",
):
    if parent_span is None or not settings.monitoring_enabled:
        yield {}
        return

    start = time.perf_counter()
    span = None
    box: dict[str, Any] = {}
    meta = dict(metadata or {})

    kwargs: dict[str, Any] = {"name": name, "as_type": as_type, "input": input, "metadata": meta}
    span = _start_observation(parent_span, **kwargs)
    if span is not None:
        box["_span"] = span

    try:
        yield box
    except Exception as exc:
        if span is not None:
            try:
                if box.get("output") is None:
                    box["output"] = {"error": str(exc)}
                span.update(level="ERROR", status_message=str(exc))
            except Exception as update_exc:
                logger.warning("Lỗi cập nhật child span ERROR: %s", update_exc)
        raise
    finally:
        if span is not None:
            try:
                latency_s = time.perf_counter() - start
                out = box.get("output") or {"status": "completed"}
                trace_in = box.get("input", input)
                model_name = box.get("model_name") or meta.get("model_name")
                temperature = box.get("temperature", meta.get("temperature"))
                meta["latency_s"] = latency_s
                if model_name:
                    meta["model_name"] = model_name
                if temperature is not None:
                    meta["temperature"] = temperature
                if box.get("metadata"):
                    meta.update(box["metadata"])
                usage = box.get("usage") or {}
                p_tokens = int(usage.get("prompt_tokens", meta.get("prompt_tokens", 0)))
                c_tokens = int(usage.get("completion_tokens", meta.get("completion_tokens", 0)))
                tot_tokens = int(usage.get("total_tokens", meta.get("total_tokens", p_tokens + c_tokens)))
                if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                    meta["prompt_tokens"] = p_tokens
                    meta["completion_tokens"] = c_tokens
                    meta["total_tokens"] = tot_tokens
                update_kwargs: dict[str, Any] = {"input": trace_in, "output": out, "metadata": meta}
                if model_name:
                    update_kwargs["model"] = model_name
                if temperature is not None:
                    update_kwargs["model_parameters"] = {"temperature": temperature}
                if tot_tokens > 0 or p_tokens > 0 or c_tokens > 0:
                    update_kwargs["usage_details"] = {"input": p_tokens, "output": c_tokens, "total": tot_tokens}
                span.update(**update_kwargs)
                span.end()
            except Exception as update_exc:
                logger.warning("Lỗi kết thúc child span: %s", update_exc)


def trace_stream(
    name: str,
    question: str,
    tokens: Iterator[str],
    parent: Any = None,
    as_type: ObservationType = "generation",
) -> Iterator[str]:
    parent_span = parent if parent is not None else current_span()
    if not settings.monitoring_enabled or parent_span is None:
        yield from tokens
        return

    langfuse = None
    start = time.perf_counter()
    chunks: list[str] = []
    try:
        for token in tokens:
            chunks.append(token)
            yield token
    finally:
        try:
            langfuse = _get_langfuse()
            span = _start_observation(
                parent_span,
                name=name,
                as_type=as_type,
                input=question,
                output="".join(chunks),
                metadata={"latency_s": time.perf_counter() - start, "streamed": True},
            )
            if span is not None:
                span.end()
            if langfuse is not None:
                langfuse.flush()
        except Exception as exc:
            logger.warning("Lỗi ghi stream trace (fail-safe): %s", exc)
