"""Agent turn service — process / SSE (v16), plus TTL cache helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from pydantic import BaseModel, Field

from src.api.helpers.cache_helpers import is_identity_query
from src.infra.memory.ttl_cache import make_cache_key
from src.shared.config import settings

logger = logging.getLogger(__name__)


def _set_ttl_cached(key: str, data: dict[str, Any], *, ttl: int) -> None:
    import src.main as main_mod

    main_mod.set_ttl_cached(key, data, ttl=ttl)


def build_cache_data_from_output(out: Any) -> dict[str, Any]:
    query = getattr(out, "query", None)
    return {
        "question": out.question,
        "answer": out.answer,
        "tool": getattr(query, "tool", "") if query else "",
        "columns": getattr(query, "columns", []) if query else [],
        "rows": getattr(query, "rows", []) if query else [],
        "row_count": getattr(query, "row_count", 0) if query else 0,
        "agent_detail": out.detail,
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
    if skip:
        return
    if is_identity_query(question) or is_identity_query(cache_q):
        return
    ttl = settings.memory_ttl_seconds
    try:
        _set_ttl_cached(make_cache_key(question, route=route), cache_data, ttl=ttl)
        if cache_q and cache_q != question:
            _set_ttl_cached(make_cache_key(cache_q, route=route), cache_data, ttl=ttl)
    except Exception as exc:
        logger.warning("Failed to store TTL cache: %s", exc)


class TurnInput(BaseModel):
    question: str
    user_id: str = "default"
    session_id: str = "default"
    request_id: str = ""
    stream_tokens: bool = False
    rewritten: Any | None = None


class TurnOutput(BaseModel):
    question: str
    answer: str
    detail: dict[str, Any] = Field(default_factory=dict)
    query: Any | None = None


class AgentTurnService:
    """Hỏi-đáp: deps → graph run (JSON hoặc SSE)."""

    def request_deps(self) -> dict[str, Any]:
        return {}

    def process(self, inp: TurnInput, **run_kwargs: Any) -> TurnOutput:
        # Via main so tests can monkeypatch ``main.run_agent`` / ``vms.graph``.
        import src.main as main_mod
        from src.domain.agents.graph import Agent_Input

        out = main_mod.run_agent(
            Agent_Input(
                question=inp.question,
                rewritten=inp.rewritten,
                user_id=inp.user_id,
                stream_tokens=inp.stream_tokens,
            ),
            session_id=inp.session_id,
            user_id=inp.user_id,
            **run_kwargs,
        )
        query = getattr(out, "query", None)
        detail = {
            "tool": getattr(query, "tool", "") if query else "",
            "columns": getattr(query, "columns", []) if query else [],
            "row_count": getattr(query, "row_count", 0) if query else 0,
            "agent_detail": out.detail,
        }
        return TurnOutput(
            question=out.question,
            answer=out.answer,
            detail=detail,
            query=query,
        )

    def iter_graph_events(self, inp: TurnInput, **stream_kwargs: Any) -> Iterator[dict[str, Any]]:
        """Map legacy run_agent_stream dicts → v16 event dicts (token/node/complete)."""
        import src.main as main_mod
        from src.domain.agents.graph import Agent_Input

        for event in main_mod.run_agent_stream(
            Agent_Input(
                question=inp.question,
                rewritten=inp.rewritten,
                user_id=inp.user_id,
                stream_tokens=inp.stream_tokens,
            ),
            session_id=inp.session_id,
            user_id=inp.user_id,
            **stream_kwargs,
        ):
            if not isinstance(event, dict):
                continue
            if "__final_result__" in event:
                out = event["__final_result__"]
                query = getattr(out, "query", None)
                detail = {
                    "tool": getattr(query, "tool", "") if query else "",
                    "columns": getattr(query, "columns", []) if query else [],
                    "row_count": getattr(query, "row_count", 0) if query else 0,
                    "agent_detail": getattr(out, "detail", ""),
                }
                yield {
                    "complete": True,
                    "question": getattr(out, "question", inp.question),
                    "answer": getattr(out, "answer", ""),
                    "detail": detail,
                    # legacy bridge for FE:
                    "node_id": "__answer__",
                    "status": "done",
                    "output": getattr(out, "answer", ""),
                }
                continue
            node_id = event.get("node_id")
            if node_id == "__answer__" and event.get("status") == "chunk":
                yield {"token": event.get("output") or "", "node_id": node_id, "status": "chunk", "output": event.get("output")}
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
        try:
            for payload in self.iter_graph_events(inp, **stream_kwargs):
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
