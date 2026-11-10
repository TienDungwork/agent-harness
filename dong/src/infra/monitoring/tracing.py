"""Monitoring — Langfuse SDK trực tiếp (theo vn-stock-swarm).

* ``trace_answer`` — root một lượt chat/ask.
* ``trace_step(parent, ...)`` — bước con; lồng sâu: ``trace_step(box["_span"], ...)``.
* ``current_span()`` — ``_current`` hoặc LangGraph ``trace_span``.
* ``trace_stream`` — gom token dưới parent / ``current_span()``.

``MONITORING_ENABLED=false`` → no-op. Lỗi Langfuse → fail-safe, không crash API.
"""
from __future__ import annotations
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Literal
from src.shared.config import settings
from src.shared.guardrails import redact_pii
logger = logging.getLogger(__name__)
_REDACT_MAX_DEPTH = 8
_current: ContextVar[Any] = ContextVar('langfuse_current_span', default=None)
_request_tokens: ContextVar[dict[str, int] | None] = ContextVar('request_tokens', default=None)
ObservationType = Literal['span', 'generation', 'embedding', 'agent', 'tool', 'chain', 'retriever', 'evaluator', 'guardrail']
_langfuse_client: Any = None

def _redact_deep(value: Any, _depth: int=0) -> Any:
    if _depth >= _REDACT_MAX_DEPTH:
        return '[QUÁ SÂU — BỎ QUA]'
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {k: _redact_deep(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_deep(v, _depth + 1) for v in value]
    return value

def _get_langfuse():
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    from langfuse import Langfuse
    _langfuse_client = Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, host=settings.langfuse_host, mask=lambda *, data, **_: _redact_deep(data))
    return _langfuse_client

def current_span() -> Any:
    span = _current.get()
    if span is not None:
        return span
    try:
        from langgraph.runtime import get_runtime
        return (get_runtime().context or {})['trace_span'] if 'trace_span' in (get_runtime().context or {}) else None
    except Exception:
        return None

def bind_trace_root(span: Any) -> Token:
    return _current.set(span)

def reset_trace_root(token: Token) -> None:
    try:
        _current.reset(token)
    except ValueError:
        pass

def add_request_tokens(usage: dict[str, int]) -> None:
    tokens = _request_tokens.get()
    if tokens is not None and isinstance(usage, dict):
        tokens['prompt_tokens'] += usage['prompt_tokens'] if 'prompt_tokens' in usage else 0
        tokens['completion_tokens'] += usage['completion_tokens'] if 'completion_tokens' in usage else 0
        tokens['total_tokens'] += usage['total_tokens'] if 'total_tokens' in usage else 0

def extract_token_usage(response: Any) -> dict[str, int]:
    if not response:
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    usage_meta = getattr(response, 'usage_metadata', None)
    if isinstance(usage_meta, dict):
        p = (usage_meta['input_tokens'] if 'input_tokens' in usage_meta else None) or (usage_meta['prompt_tokens'] if 'prompt_tokens' in usage_meta else None) or 0
        c = (usage_meta['output_tokens'] if 'output_tokens' in usage_meta else None) or (usage_meta['completion_tokens'] if 'completion_tokens' in usage_meta else None) or 0
        tot = (usage_meta['total_tokens'] if 'total_tokens' in usage_meta else None) or p + c
        return {'prompt_tokens': int(p), 'completion_tokens': int(c), 'total_tokens': int(tot)}
    resp_meta = getattr(response, 'response_metadata', None)
    if isinstance(resp_meta, dict):
        tu = resp_meta['token_usage'] if 'token_usage' in resp_meta else None
        if isinstance(tu, dict):
            p = (tu['prompt_tokens'] if 'prompt_tokens' in tu else None) or (tu['input_tokens'] if 'input_tokens' in tu else None) or 0
            c = (tu['completion_tokens'] if 'completion_tokens' in tu else None) or (tu['output_tokens'] if 'output_tokens' in tu else None) or 0
            tot = (tu['total_tokens'] if 'total_tokens' in tu else None) or p + c
            return {'prompt_tokens': int(p), 'completion_tokens': int(c), 'total_tokens': int(tot)}
    if isinstance(response, dict):
        usage = (response['usage'] if 'usage' in response else None) or (response['usage_metadata'] if 'usage_metadata' in response else None) or (response['token_usage'] if 'token_usage' in response else None)
        if isinstance(usage, dict):
            p = (usage['prompt_tokens'] if 'prompt_tokens' in usage else None) or (usage['input_tokens'] if 'input_tokens' in usage else None) or 0
            c = (usage['completion_tokens'] if 'completion_tokens' in usage else None) or (usage['output_tokens'] if 'output_tokens' in usage else None) or 0
            tot = (usage['total_tokens'] if 'total_tokens' in usage else None) or p + c
            return {'prompt_tokens': int(p), 'completion_tokens': int(c), 'total_tokens': int(tot)}
    return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

def _stamp_root_trace_attrs(span: Any, *, name: str, meta: dict[str, Any]) -> None:
    """user/session/trace name — không dùng propagate_attributes (OTEL cross-thread)."""
    try:
        otel = getattr(span, '_otel_span', None)
        if otel is None or not otel.is_recording():
            return
        from langfuse._client.attributes import LangfuseOtelSpanAttributes as attrs
        otel.set_attribute(attrs.TRACE_NAME, str(name)[:200])
        if meta['user_id'] if 'user_id' in meta else None:
            otel.set_attribute(attrs.TRACE_USER_ID, str(meta['user_id'])[:200])
        if meta['session_id'] if 'session_id' in meta else None:
            otel.set_attribute(attrs.TRACE_SESSION_ID, str(meta['session_id'])[:200])
    except Exception as exc:
        logger.debug('stamp root trace attrs: %s', exc)

def _default_model_name(meta: dict[str, Any], box: dict[str, Any]) -> str:
    return (box['model_name'] if 'model_name' in box else None) or (meta['model_name'] if 'model_name' in meta else None) or (settings.model_name if settings.llm_backend == 'self_hosted' else settings.llm_model)

def _usage_from_box(box: dict[str, Any], meta: dict[str, Any]) -> tuple[int, int, int]:
    usage = (box['usage'] if 'usage' in box else None) or {}
    p = int(usage['prompt_tokens'] if 'prompt_tokens' in usage else meta['prompt_tokens'] if 'prompt_tokens' in meta else 0)
    c = int(usage['completion_tokens'] if 'completion_tokens' in usage else meta['completion_tokens'] if 'completion_tokens' in meta else 0)
    t = int(usage['total_tokens'] if 'total_tokens' in usage else meta['total_tokens'] if 'total_tokens' in meta else p + c)
    return (p, c, t)

def _format_latency_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)

def _finish_step(span: Any, box: dict[str, Any], trace_in: Any, meta: dict[str, Any], start: float) -> None:
    latency_ms = _format_latency_ms(start)
    latency_s = round(latency_ms / 1000, 3)
    out = (box['output'] if 'output' in box else None) or {'status': 'completed'}
    meta = dict(meta)
    meta['latency_ms'] = latency_ms
    meta['latency_s'] = latency_s
    if box['metadata'] if 'metadata' in box else None:
        meta.update(box['metadata'])
    model_name = (box['model_name'] if 'model_name' in box else None) or (meta['model_name'] if 'model_name' in meta else None)
    temperature = box['temperature'] if 'temperature' in box else meta['temperature'] if 'temperature' in meta else None
    if model_name:
        meta['model_name'] = model_name
    if temperature is not None:
        meta['temperature'] = temperature
    if box['metadata'] if 'metadata' in box else None:
        meta.update(box['metadata'])
    p, c, t = _usage_from_box(box, meta)
    if t > 0 or p > 0 or c > 0:
        meta.update({'prompt_tokens': p, 'completion_tokens': c, 'total_tokens': t})
    kw: dict[str, Any] = {'input': box['input'] if 'input' in box else trace_in, 'output': out, 'metadata': meta}
    if model_name:
        kw['model'] = model_name
    if temperature is not None:
        kw['model_parameters'] = {'temperature': temperature}
    if t > 0 or p > 0 or c > 0:
        kw['usage_details'] = {'input': p, 'output': c, 'total': t}
    span.update(**kw)
    span.end()

@contextmanager
def trace_answer(name: str, question: str, metadata: dict[str, Any] | None=None, as_type: ObservationType='agent', box: dict[str, Any] | None=None):
    if not settings.monitoring_enabled:
        yield (box if box is not None else {})
        return
    meta = dict(metadata or {})
    if box is None:
        box = {}
    token_counter = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    token_var = _request_tokens.set(token_counter)
    start = time.perf_counter()
    try:
        langfuse = _get_langfuse()
    except Exception as exc:
        logger.warning('Langfuse init fail-safe: %s', exc)
        try:
            yield box
        finally:
            try:
                _request_tokens.reset(token_var)
            except ValueError:
                pass
        return
    try:
        try:
            span = langfuse.start_observation(name=name, as_type=as_type, input=question, metadata=meta)
        except Exception as exc:
            logger.warning('Langfuse start_observation fail-safe: %s', exc)
            yield box
            return
        _stamp_root_trace_attrs(span, name=name, meta=meta)
        box['_span'] = span
        cur = _current.set(span)
        try:
            yield box
        except Exception as exc:
            if (box['output'] if 'output' in box else None) is None:
                box['output'] = {'error': str(exc)}
            span.update(level='ERROR', status_message=str(exc))
            raise
        finally:
            reset_trace_root(cur)
            if 'usage' not in box:
                box['usage'] = {}
            for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                box['usage'][k] = (box['usage'][k] if k in box['usage'] else 0) + token_counter[k]
            out = box['output'] if 'output' in box else None
            if out is None:
                out = {'status': 'incomplete', 'reason': 'no_output_recorded', 'question_preview': (question or '')[:500]}
            latency_ms = _format_latency_ms(start)
            model_name = _default_model_name(meta, box)
            temperature = box['temperature'] if 'temperature' in box else meta['temperature'] if 'temperature' in meta else settings.llm_temperature
            p, c, t = _usage_from_box(box, meta)
            meta.update({'latency_ms': latency_ms, 'latency_s': round(latency_ms / 1000, 3), 'model_name': model_name, 'temperature': temperature, 'prompt_tokens': p, 'completion_tokens': c, 'total_tokens': t})
            kw: dict[str, Any] = {'name': name, 'input': question, 'output': out, 'metadata': meta, 'model': model_name, 'model_parameters': {'temperature': temperature}}
            if isinstance(out, dict) and (out['status'] if 'status' in out else None) in ('error', 'incomplete'):
                kw['level'] = 'ERROR'
                kw['status_message'] = str((out['error'] if 'error' in out else None) or (out['reason'] if 'reason' in out else None) or (out['status'] if 'status' in out else None))[:500]
            if t > 0 or p > 0 or c > 0:
                kw['usage_details'] = {'input': p, 'output': c, 'total': t}
            span.update(**kw)
            span.end()
            try:
                langfuse.flush()
            except Exception as exc:
                logger.warning('Langfuse flush fail-safe: %s', exc)
    finally:
        try:
            _request_tokens.reset(token_var)
        except ValueError:
            pass

@contextmanager
def trace_step(parent_span: Any, name: str, input: Any=None, metadata: dict[str, Any] | None=None, as_type: ObservationType='span'):
    if parent_span is None or not settings.monitoring_enabled:
        yield {}
        return
    meta = dict(metadata or {})
    start = time.perf_counter()
    try:
        span = parent_span.start_observation(name=name, as_type=as_type, input=input, metadata=meta)
    except TypeError:
        span = parent_span.start_observation(name=name, input=input, metadata=meta)
    except Exception as exc:
        logger.warning('Langfuse child start fail-safe: %s', exc)
        yield {}
        return
    box: dict[str, Any] = {'_span': span}
    try:
        yield box
    except Exception as exc:
        if (box['output'] if 'output' in box else None) is None:
            box['output'] = {'error': str(exc)}
        span.update(level='ERROR', status_message=str(exc))
        raise
    finally:
        try:
            _finish_step(span, box, input, meta, start)
        except Exception as exc:
            logger.warning('Langfuse child end fail-safe: %s', exc)

def trace_stream(name: str, question: str, tokens: Iterator[str], parent: Any=None, as_type: ObservationType='generation') -> Iterator[str]:
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
        try:
            span = parent_span.start_observation(name=name, as_type=as_type, input=question, output=''.join(chunks), metadata={'latency_ms': _format_latency_ms(start), 'streamed': True})
            span.end()
            langfuse.flush()
        except Exception as exc:
            logger.warning('Langfuse stream trace fail-safe: %s', exc)
