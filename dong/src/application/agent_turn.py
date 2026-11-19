"""Agent turn — SSE stream cùng graph (giống stock ChatService).

  POST /api/agent/stream → AgentTurnService.stream_sse_frames()
  stream_sse (v16 async) → iter_graph_events() rồi đóng SSE
"""

from __future__ import annotations

import inspect
import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from pydantic import BaseModel, Field

from src.api.helpers.cache_helpers import is_identity_query
from src.api.helpers.errors import format_error_message
from src.api.helpers.session_helpers import build_agent_trace, persist_session_turn
from src.api.helpers.sse_helpers import build_chart_sse_event, sanitize_sse_event
from src.api.models.schemas import ChatRequest
from src.infra.memory.ttl_cache import make_cache_key
from src.shared.settings import settings

logger = logging.getLogger(__name__)


# ── DTO ──────────────────────────────────────────────────────────────────────


class TurnInput(BaseModel):
    question: str
    user_id: str = "default"
    session_id: str = "default"
    request_id: str = ""
    stream_tokens: bool = False
    rewritten: Any | None = None
    access_context: Any | None = None


class TurnOutput(BaseModel):
    question: str
    answer: str
    detail: dict[str, Any] = Field(default_factory=dict)
    query: Any | None = None


# ── Cache helpers (export cho router / tests) ─────────────────────────────────


def _agent_detail(out: Any) -> str:
    detail = getattr(out, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("agent_detail") or "")
    return str(detail or "")


def _detail_from_out(out: Any) -> dict[str, Any]:
    """Map Agent_Output / TurnOutput → detail dict cho API + cache."""
    query = getattr(out, "query", None)
    return {
        "tool": getattr(query, "tool", "") if query else "",
        "columns": list(getattr(query, "columns", []) or []) if query else [],
        "row_count": int(getattr(query, "row_count", 0) or 0) if query else 0,
        "agent_detail": _agent_detail(out),
    }


def build_cache_data_from_output(out: Any) -> dict[str, Any]:
    query = getattr(out, "query", None)
    return {
        "question": getattr(out, "question", ""),
        "answer": getattr(out, "answer", ""),
        "rows": list(getattr(query, "rows", []) or []) if query else [],
        **_detail_from_out(out),
    }


def detail_payload_from_cache(cached: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": cached.get("tool") or "",
        "columns": cached.get("columns") or [],
        "row_count": int(cached.get("row_count") or 0),
        "agent_detail": cached.get("agent_detail") or "",
        "cache_hit": True,
    }


def store_turn_cache(
    question: str,
    cache_q: str,
    route: str,
    cache_data: dict[str, Any],
    *,
    skip: bool = False,
) -> None:
    if skip or is_identity_query(question) or is_identity_query(cache_q):
        return
    import src.main as main_mod

    ttl = settings.memory_ttl_seconds
    try:
        main_mod.set_ttl_cached(make_cache_key(question, route=route), cache_data, ttl=ttl)
        if cache_q and cache_q != question:
            main_mod.set_ttl_cached(make_cache_key(cache_q, route=route), cache_data, ttl=ttl)
    except Exception as exc:
        logger.warning("Failed to store TTL cache: %s", exc)


def _sse(payload: dict[str, Any] | str) -> str:
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _filter_stream_kwargs(fn: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Bỏ session_id/user_id nếu mock/signature không nhận (giữ tương thích test)."""
    if not callable(fn):
        return kwargs
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return kwargs
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    out = dict(kwargs)
    if not has_var_kw and "session_id" not in sig.parameters:
        out.pop("session_id", None)
    if not has_var_kw and "user_id" not in sig.parameters:
        out.pop("user_id", None)
    return out


# ── Service ──────────────────────────────────────────────────────────────────


class AgentTurnService:
    """Hỏi-đáp: TTL cache → graph (JSON hoặc SSE)."""

    def request_deps(self) -> dict[str, Any]:
        return {}

    def process(self, inp: TurnInput, **run_kwargs: Any) -> TurnOutput:
        """JSON một lần: chạy graph → TurnOutput."""
        import src.main as main_mod
        from src.domain.agents.graph import Agent_Input

        # Bước 1: gọi graph
        out = main_mod.run_agent(
            Agent_Input(
                question=inp.question,
                rewritten=inp.rewritten,
                user_id=inp.user_id,
                stream_tokens=inp.stream_tokens,
                access_context=inp.access_context,
            ),
            session_id=inp.session_id,
            user_id=inp.user_id,
            **run_kwargs,
        )
        # Bước 2: map sang DTO
        return TurnOutput(
            question=out.question,
            answer=out.answer,
            detail=_detail_from_out(out),
            query=getattr(out, "query", None),
        )

    def stream_sse_frames(self, req: ChatRequest, *, access: Any, user_id: str) -> Iterator[str]:
        """POST /api/agent/stream — yield dòng SSE (cache / graph / chart / complete)."""
        import src.main as main_mod
        from src.domain.agents.graph import Agent_Input
        from src.domain.guardrails import redact_pii

        # Router đã redact; gọi lại idempotent nếu service được gọi trực tiếp.
        question = redact_pii((req.question or "").strip())
        raw_question = question
        session_id = req.session_id.strip()
        last_error = ""
        got_final = False
        chart: dict[str, Any] = {}
        trace_nodes: list[dict[str, Any]] = []

        try:
            # Bước 2: cache hit → SSE cache + complete
            cached = main_mod._lookup_ttl_cache(raw_question)
            if cached:
                detail = detail_payload_from_cache(cached)
                ans = cached.get("answer") or ""
                q = cached.get("question") or raw_question
                yield _sse({"node": "cache", "node_id": "cache", "status": "done", "output": ans})
                persist_session_turn(
                    session_id=session_id, user_id=user_id, question=q, answer=ans, detail=detail
                )
                yield _sse(
                    {
                        "complete": True,
                        "question": q,
                        "answer": ans,
                        "detail": detail,
                        "node_id": "__answer__",
                        "status": "done",
                        "output": ans,
                    }
                )
                return

            # Bước 3: kwargs stream (lọc theo signature mock/test)
            stream_kwargs = _filter_stream_kwargs(
                getattr(main_mod.run_agent_stream, "side_effect", None) or main_mod.run_agent_stream,
                {
                    "trace_name": "chat",
                    "trace_metadata": {
                        "endpoint": "/api/agent/stream",
                        "provider": req.model_provider,
                        "session_id": req.session_id,
                        "user_id": user_id,
                        "trace_question": question,
                        "role_group": getattr(access, "role_group", None),
                    },
                    "session_id": req.session_id,
                    "user_id": user_id,
                },
            )

            # Bước 4: drain graph events — question đã redact
            for event in main_mod.run_agent_stream(
                Agent_Input(
                    question=question,
                    user_id=user_id,
                    stream_tokens=req.stream_tokens,
                    access_context=access,
                ),
                **stream_kwargs,
            ):
                # Bước 4a: kết quả cuối → persist + cache + complete
                if "__final_result__" in event:
                    got_final = True
                    out = event["__final_result__"]
                    detail = _detail_from_out(out)
                    if chart.get("png") or chart.get("url"):
                        detail["chart_type"] = chart.get("type") or "bar"
                        detail["chart_spec"] = chart.get("spec") or {}
                        if chart.get("rows") is not None:
                            detail["chart_rows"] = chart["rows"]
                        if chart.get("url"):
                            detail["chart_url"] = chart["url"]
                    chart_payload = None
                    if chart.get("png") or chart.get("url") or detail.get("chart_spec"):
                        chart_payload = {
                            "png": chart.get("png"),
                            "url": chart.get("url"),
                            "spec": detail.get("chart_spec"),
                            "type": detail.get("chart_type", "bar"),
                            "rows": detail.get("chart_rows"),
                        }
                    agent_trace = build_agent_trace(trace_nodes, detail)
                    persist_session_turn(
                        session_id=session_id,
                        user_id=user_id,
                        question=out.question or question,
                        answer=out.answer,
                        detail=detail,
                        chart=chart_payload,
                        agent_trace=agent_trace,
                    )
                    detail["agent_trace"] = agent_trace
                    store_turn_cache(
                        raw_question,
                        out.question or raw_question,
                        out.detail or "query_data",
                        build_cache_data_from_output(out),
                    )
                    yield _sse(
                        {
                            "complete": True,
                            "question": out.question or question,
                            "answer": out.answer,
                            "detail": detail,
                            "node_id": "__answer__",
                            "status": "done",
                            "output": out.answer,
                        }
                    )
                    continue

                node_id = event.get("node_id") or ""
                if node_id == "error":
                    last_error = str(event.get("output") or last_error or "Agent error")
                if node_id and node_id not in ("__answer__", "__chart__", "error"):
                    trace_nodes.append(
                        {
                            "node_id": node_id,
                            "status": event.get("status"),
                            "input": event.get("input"),
                            "output": event.get("output"),
                            "meta": event.get("meta"),
                            "duration_ms": event.get("duration_ms"),
                        }
                    )

                # Bước 4b: chart từ node render_chart
                png = event.get("chart_png_base64") or ""
                url = event.get("chart_url") or ""
                spec = event.get("chart_spec")
                if node_id == "render_chart" and (png or url):
                    spec_dict = spec if isinstance(spec, dict) else {}
                    event_input = event.get("input") or {}
                    raw_rows = event_input.get("rows") if isinstance(event_input, dict) else None
                    if raw_rows is None:
                        raw_rows = event.get("rows")
                    chart = {
                        "png": png or None,
                        "url": url or None,
                        "spec": spec_dict,
                        "type": (spec_dict.get("chart_type") or "bar") if spec_dict else "bar",
                        "rows": raw_rows if isinstance(raw_rows, list) else None,
                    }
                    yield _sse(
                        build_chart_sse_event(
                            spec_dict, png, chart["rows"], chart_url=url or None
                        )
                    )

                # Bước 4c: forward event đã sanitize
                try:
                    yield _sse(sanitize_sse_event(event))
                except Exception as ser_exc:
                    msg = format_error_message(ser_exc)
                    yield _sse({"node_id": "error", "status": "done", "output": msg})
                    yield _sse(
                        {
                            "node_id": "__answer__",
                            "status": "error",
                            "output": msg,
                            "detail": {"status": "error"},
                        }
                    )
                    break

            if not got_final and last_error:
                logger.warning("Stream incomplete: %s", last_error)
        except Exception as exc:
            # Bước 5: lỗi → SSE error (không đứt im lặng)
            msg = format_error_message(exc)
            yield _sse({"node_id": "error", "status": "done", "output": msg})
            yield _sse(
                {
                    "node_id": "__answer__",
                    "status": "error",
                    "output": msg,
                    "detail": {"status": "error"},
                }
            )

    def iter_graph_events(self, inp: TurnInput, **stream_kwargs: Any) -> Iterator[dict[str, Any]]:
        """Map run_agent_stream dicts → event v16 (token / node / complete)."""
        import src.main as main_mod
        from src.domain.agents.graph import Agent_Input

        for event in main_mod.run_agent_stream(
            Agent_Input(
                question=inp.question,
                rewritten=inp.rewritten,
                user_id=inp.user_id,
                stream_tokens=inp.stream_tokens,
                access_context=inp.access_context,
            ),
            session_id=inp.session_id,
            user_id=inp.user_id,
            **stream_kwargs,
        ):
            if not isinstance(event, dict):
                continue
            if "__final_result__" in event:
                out = event["__final_result__"]
                yield {
                    "complete": True,
                    "question": getattr(out, "question", inp.question),
                    "answer": getattr(out, "answer", ""),
                    "detail": _detail_from_out(out),
                    "node_id": "__answer__",
                    "status": "done",
                    "output": getattr(out, "answer", ""),
                }
                continue
            node_id = event.get("node_id")
            if node_id == "__answer__" and event.get("status") == "chunk":
                yield {
                    "token": event.get("output") or "",
                    "node_id": node_id,
                    "status": "chunk",
                    "output": event.get("output"),
                }
                continue
            if node_id:
                yield {
                    "node": node_id,
                    "status": event.get("status"),
                    "node_id": node_id,
                    "input": event.get("input"),
                    "output": event.get("output"),
                    "duration_ms": event.get("duration_ms"),
                    "chart_png_base64": event.get("chart_png_base64"),
                    "chart_spec": event.get("chart_spec"),
                    "chart_meta": event.get("chart_meta"),
                    "meta": event.get("meta"),
                }

    async def stream_sse(self, inp: TurnInput, **stream_kwargs: Any) -> AsyncIterator[str]:
        """SSE v16: event → complete → [DONE]; lỗi → một event error."""
        try:
            for payload in self.iter_graph_events(inp, **stream_kwargs):
                yield _sse(payload)
            yield _sse("[DONE]")
        except Exception as exc:
            yield _sse({"error": str(exc)})
