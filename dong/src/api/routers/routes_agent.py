"""Chat, ask, SSE stream — gọi LangGraph agent."""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.domain.agents.graph import Agent_Input


def _run_agent(*args, **kwargs):
    import src.main as main_mod

    return main_mod.run_agent(*args, **kwargs)


def _run_agent_stream(*args, **kwargs):
    import src.main as main_mod

    return main_mod.run_agent_stream(*args, **kwargs)
from src.api.helpers.errors import format_error_message
from src.api.models.schemas import AskRequest, AskResponse, ChatRequest, ChatResponse
from src.api.helpers.session_helpers import build_agent_trace, persist_session_turn
from src.api.helpers.sse_helpers import build_chart_sse_event, sanitize_sse_event, split_into_chunks
from src.shared.guardrails import GuardrailViolation, check_input, redact_pii
from src.infra.monitoring.tracing import trace_answer
from src.infra.session import get_session_messages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


def _record_chat_trace(
    t: dict[str, Any],
    *,
    status: str,
    answer: str = "",
    error: str = "",
    tool: str = "",
    row_count: int = 0,
) -> None:
    out: dict[str, Any] = {"status": status}
    if answer:
        out["answer"] = answer
    if error:
        out["error"] = error
    if tool:
        out["tool"] = tool
    if row_count:
        out["row_count"] = row_count
    t["output"] = out

@router.post("/api/chat", response_model=ChatResponse, tags=["agent"])
def chat(req: ChatRequest) -> ChatResponse:
    """Endpoint chính nhận câu hỏi từ Frontend UI."""
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id không được để trống.")
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id không được để trống.")
    with trace_answer(
        "chat",
        req.question,
        metadata={
            "endpoint": "/api/chat",
            "provider": req.model_provider,
            "session_id": req.session_id,
            "user_id": req.user_id,
        },
    ) as t:
        question = redact_pii(req.question)

        from src.infra.session import get_session_messages

        prev_messages = get_session_messages(session_id=req.session_id.strip(), user_id=req.user_id.strip()) or []

        try:
            from src.domain.agents.routing.intent import is_chat_greeting
            from src.domain.agents.routing.rewrite import rewrite_question_safe
            from src.infra.llm.schemas import RewrittenQuestion

            if is_chat_greeting(question):
                rewritten = RewrittenQuestion(text=question, intent_hint="chat")
            else:
                rewritten = rewrite_question_safe(question, history=prev_messages)
            out = _run_agent(
                Agent_Input(question=req.question.strip(), rewritten=rewritten, user_id=req.user_id),
                parent_span=t.get("_span"),
                session_id=req.session_id,
                user_id=req.user_id,
            )
        except GuardrailViolation:
            raise
        except Exception as exc:
            friendly_msg = format_error_message(exc)
            _record_chat_trace(t, status="error", error=friendly_msg, answer=friendly_msg)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query

        detail_payload: dict[str, Any] = {
            "tool": query.tool if query else "",
            "columns": query.columns if query else [],
            "row_count": query.row_count if query else 0,
            "agent_detail": out.detail,
        }

        persist_session_turn(
            session_id=req.session_id.strip(),
            user_id=req.user_id.strip(),
            question=out.question or req.question,
            answer=out.answer,
            detail=detail_payload,
        )

        response = ChatResponse(
            question=out.question,
            answer=out.answer,
            tool=query.tool if query else "",
            detail=detail_payload,
            row_count=query.row_count if query else 0,
        )
        _record_chat_trace(
            t,
            status="ok",
            answer=response.answer,
            tool=response.tool,
            row_count=response.row_count,
        )
        return response


@router.post("/ask", response_model=AskResponse, tags=["agent"])
def ask(req: AskRequest) -> AskResponse:
    """Endpoint tương thích ngược cho /ask."""
    with trace_answer(
        "ask",
        req.question,
        metadata={
            "endpoint": "/ask",
            "session_id": getattr(req, "session_id", "default"),
            "user_id": getattr(req, "user_id", "default"),
        },
    ) as t:
        question = redact_pii(req.question)

        from src.infra.session import get_session_messages

        try:
            from src.domain.agents.routing.intent import is_chat_greeting
            from src.domain.agents.routing.rewrite import rewrite_question_safe
            from src.infra.llm.schemas import RewrittenQuestion

            if is_chat_greeting(question):
                rewritten = RewrittenQuestion(text=question, intent_hint="chat")
            else:
                rewritten = rewrite_question_safe(question)
            out = _run_agent(Agent_Input(question=req.question.strip(), rewritten=rewritten), parent_span=t.get("_span"))
        except GuardrailViolation:
            raise
        except Exception as exc:
            friendly_msg = format_error_message(exc)
            _record_chat_trace(t, status="error", error=friendly_msg, answer=friendly_msg)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query

        response = AskResponse(
            question=out.question,
            answer=out.answer,
            tool=query.tool if query else "",
            columns=query.columns if query else [],
            rows=query.rows if query else [],
            row_count=query.row_count if query else 0,
        )
        _record_chat_trace(
            t,
            status="ok",
            answer=response.answer,
            tool=response.tool,
            row_count=response.row_count,
        )
        return response


@router.post("/api/agent/stream", tags=["agent"])
def stream_agent(req: ChatRequest) -> StreamingResponse:
    if not req.session_id or not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id không được để trống.")
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id không được để trống.")
    check_input(req.question)

    def event_generator():
        with trace_answer(
            "chat",
            req.question,
            metadata={
                "endpoint": "/api/agent/stream",
                "provider": req.model_provider,
                "session_id": req.session_id,
                "user_id": req.user_id,
            },
        ) as t:
            question = redact_pii(req.question)
            last_stream_error = ""
            got_final = False

            try:
                prev_messages = get_session_messages(
                    session_id=req.session_id.strip(), user_id=req.user_id.strip()
                ) or []

                from src.domain.agents.routing.intent import is_chat_greeting
                from src.domain.agents.routing.rewrite import rewrite_question_safe
                from src.infra.llm.schemas import RewrittenQuestion

                if is_chat_greeting(question):
                    rewritten = RewrittenQuestion(text=question, intent_hint="chat")
                else:
                    rewritten = rewrite_question_safe(question, history=prev_messages)
                stream_kwargs = {"parent_span": t.get("_span")}
                target_fn = getattr(_run_agent_stream, "side_effect", None) or _run_agent_stream
                can_pass_session = True
                can_pass_user = True
                if callable(target_fn):
                    try:
                        import inspect
                        sig = inspect.signature(target_fn)
                        can_pass_session = "session_id" in sig.parameters or any(
                            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                        )
                        can_pass_user = "user_id" in sig.parameters or any(
                            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                        )
                    except (ValueError, TypeError):
                        pass
                if can_pass_session:
                    stream_kwargs["session_id"] = req.session_id
                if can_pass_user:
                    stream_kwargs["user_id"] = req.user_id

                # Track chart info emitted from render_chart node during this stream run.
                last_chart_png: str | None = None
                last_chart_spec: dict[str, Any] | None = None
                last_chart_type: str | None = None
                last_chart_rows: list[dict] | None = None
                stream_trace_nodes: list[dict[str, Any]] = []

                for event in _run_agent_stream(
                    Agent_Input(
                        question=req.question.strip(),
                        rewritten=rewritten,
                        user_id=req.user_id,
                        stream_tokens=req.stream_tokens,
                    ),
                    **stream_kwargs,
                ):
                    if "__final_result__" in event:
                        got_final = True
                        out = event["__final_result__"]
                        query = getattr(out, "query", None)

                        detail_payload: dict[str, Any] = {
                            "tool": getattr(query, "tool", "") if query else "",
                            "columns": getattr(query, "columns", []) if query else [],
                            "row_count": getattr(query, "row_count", 0) if query else 0,
                            "agent_detail": out.detail,
                        }
                        # Attach chart info to __answer__ detail when chart was rendered
                        if last_chart_png:
                            detail_payload["chart_type"] = last_chart_type or "bar"
                            detail_payload["chart_spec"] = last_chart_spec or {}
                            if last_chart_rows is not None:
                                detail_payload["chart_rows"] = last_chart_rows

                        _record_chat_trace(
                            t,
                            status="ok",
                            answer=out.answer,
                            tool=getattr(query, "tool", "") if query else "",
                            row_count=getattr(query, "row_count", 0) if query else 0,
                        )
                        chart_payload = None
                        if last_chart_png or detail_payload.get("chart_spec"):
                            chart_payload = {
                                "png": last_chart_png,
                                "spec": detail_payload.get("chart_spec"),
                                "type": detail_payload.get("chart_type", "bar"),
                                "rows": detail_payload.get("chart_rows"),
                            }
                        agent_trace = build_agent_trace(stream_trace_nodes, detail_payload)
                        persist_session_turn(
                            session_id=req.session_id.strip(),
                            user_id=req.user_id.strip(),
                            question=out.question or question,
                            answer=out.answer,
                            detail=detail_payload,
                            chart=chart_payload,
                            agent_trace=agent_trace,
                        )
                        detail_payload["agent_trace"] = agent_trace
                        ans_event = {
                            "node_id": "__answer__",
                            "status": "done",
                            "output": out.answer,
                            "detail": detail_payload,
                        }
                        yield f"data: {json.dumps(ans_event, ensure_ascii=False)}\n\n"
                        continue

                    event_node = event.get("node_id", "")
                    if event_node == "error":
                        last_stream_error = str(event.get("output") or last_stream_error or "Agent error")
                    if event_node == "__answer__" and event.get("status") == "error":
                        err_text = str(event.get("output") or last_stream_error or "Stream error")
                        last_stream_error = err_text
                        _record_chat_trace(t, status="error", error=err_text, answer=err_text)

                    if event_node and event_node not in ("__answer__", "__chart__", "error"):
                        stream_trace_nodes.append({
                            "node_id": event_node,
                            "status": event.get("status"),
                            "input": event.get("input"),
                            "output": event.get("output"),
                            "meta": event.get("meta"),
                            "duration_ms": event.get("duration_ms"),
                        })

                    # Detect render_chart node event — emit dedicated __chart__ SSE event
                    event_chart_png = event.get("chart_png_base64") or ""
                    event_chart_spec = event.get("chart_spec")
                    if event_node == "render_chart" and event_chart_png:
                        spec_dict = event_chart_spec if isinstance(event_chart_spec, dict) else {}
                        last_chart_png = event_chart_png
                        last_chart_spec = spec_dict
                        last_chart_type = spec_dict.get("chart_type", "bar") if spec_dict else "bar"
                        # Extract rows from event input for Chart.js rendering
                        event_input = event.get("input") or {}
                        raw_rows = None
                        if isinstance(event_input, dict):
                            raw_rows = event_input.get("rows") or event.get("rows")
                        if raw_rows is None:
                            raw_rows = event.get("rows")
                        last_chart_rows = raw_rows if isinstance(raw_rows, list) else None
                        chart_sse = build_chart_sse_event(spec_dict, event_chart_png, last_chart_rows)
                        yield f"data: {json.dumps(chart_sse, ensure_ascii=False)}\n\n"

                    try:
                        payload = json.dumps(sanitize_sse_event(event), ensure_ascii=False, default=str)
                    except Exception as ser_exc:
                        friendly_msg = format_error_message(ser_exc)
                        _record_chat_trace(t, status="error", error=friendly_msg, answer=friendly_msg)
                        yield f'data: {json.dumps({"node_id": "error", "status": "done", "output": friendly_msg}, ensure_ascii=False)}\n\n'
                        yield f'data: {json.dumps({"node_id": "__answer__", "status": "error", "output": friendly_msg, "detail": {"status": "error"}}, ensure_ascii=False)}\n\n'
                        break
                    yield f"data: {payload}\n\n"

                if not got_final and t.get("output") is None:
                    msg = last_stream_error or "Stream kết thúc không có __final_result__."
                    _record_chat_trace(t, status="incomplete", error=msg)
            except Exception as exc:
                friendly_msg = format_error_message(exc)
                _record_chat_trace(t, status="error", error=friendly_msg, answer=friendly_msg)
                yield f'data: {json.dumps({"node_id": "error", "status": "done", "output": friendly_msg}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"node_id": "__answer__", "status": "error", "output": friendly_msg, "detail": {"status": "error"}}, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


