"""Backend FastAPI entry point — Phase 4 API Gateway & Agent Routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import json
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import logging
import threading
import time

from src.sessions import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionItem,
    SessionListResponse,
    SessionMessagesResponse,
    append_session_messages,
    create_session,
    delete_session,
    get_session_messages,
    list_sessions,
)

logger = logging.getLogger(__name__)

from src.memory.ttl_cache import (
    _ttl_cache,
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)

_cache = _ttl_cache

from src.config import settings
from src.agent.graph import Agent_Input, run_agent
from src.guardrails import (
    GuardrailViolation,
    check_input,
    redact_pii,
    rejection_detail,
)
from src.monitoring.tracing import trace_answer
from src.llm.schemas import FeedbackRequest

app = FastAPI(
    title="agent_ATIN v3 API",
    description="Backend API Gateway cho hệ thống VMS KCN Hưng Phú",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_SSE_SCHEMA_EXCERPT_MAX = 16000


def _lookup_ttl_cache(question: str) -> dict[str, Any] | None:
    """Tra TTL cache theo câu hỏi gốc (hỗ trợ key có route suffix)."""
    try:
        return get_ttl_cached(make_cache_key(question))
    except Exception as exc:
        logger.warning("TTL cache lookup failed, degrading to cache miss: %s", exc)
        return None


def _sanitize_sse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Giữ I/O structured thực; chỉ cắt field quá lớn (schema excerpt) trên SSE."""
    import copy

    ev = copy.deepcopy(event)
    for side in ("input", "output"):
        payload = ev.get(side)
        if not isinstance(payload, dict):
            continue
        excerpt = payload.get("schema_excerpt")
        if isinstance(excerpt, str) and len(excerpt) > _SSE_SCHEMA_EXCERPT_MAX:
            payload["schema_excerpt"] = (
                excerpt[:_SSE_SCHEMA_EXCERPT_MAX]
                + f"\n… (cắt {len(excerpt) - _SSE_SCHEMA_EXCERPT_MAX} ký tự cho SSE; xem Langfuse để full)"
            )
    return ev


def _build_chart_sse_event(
    chart_spec: dict[str, Any] | None,
    chart_png_base64: str | None,
    chart_rows: list[dict] | None = None,
) -> dict[str, Any]:
    """Xây dựng SSE event chuẩn cho __chart__ node.

    Args:
        chart_spec: dict từ ChartSpec.model_dump() (chart_type, x_column, y_column, title_vi, ...).
        chart_png_base64: chuỗi PNG base64 (không có prefix data:image/png;base64,).
        chart_rows: list[dict] rows dữ liệu để FE render Chart.js (optional).

    Returns:
        dict SSE event với node_id='__chart__', status='done', chart_type, chart_spec,
        chart_png_base64, chart_rows (khi có).
    """
    spec = chart_spec or {}
    chart_type = spec.get("chart_type", "bar") if isinstance(spec, dict) else "bar"
    event: dict[str, Any] = {
        "node_id": "__chart__",
        "status": "done",
        "chart_type": chart_type,
        "chart_spec": spec,
        "chart_png_base64": chart_png_base64 or "",
    }
    if chart_rows is not None:
        event["chart_rows"] = chart_rows
    return event


def _split_into_chunks(text: str, chunk_words: int = 3) -> list[str]:
    """Tách câu trả lời thành các chunk nhỏ để phát SSE token/chunk stream."""
    if not text:
        return []
    words = text.split(" ")
    chunks: list[str] = []
    for i in range(0, len(words), chunk_words):
        group = words[i : i + chunk_words]
        delta = " ".join(group)
        if i + chunk_words < len(words):
            delta += " "
        chunks.append(delta)
    return chunks


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi thống kê tự nhiên")
    model_provider: str | None = Field(default=None, description="Tùy chọn: 'openai' hoặc 'self_hosted'")
    model_override: str | None = Field(default=None, description="Tùy chọn ghi đè model name")
    session_id: str = Field(default="default", description="ID phiên hội thoại")
    user_id: str = Field(default="default", description="ID người dùng")
    stream_tokens: bool = Field(default=False, description="Phát các SSE chunk events cho câu trả lời")



class ChatResponse(BaseModel):
    question: str
    answer: str
    tool: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi thống kê tự nhiên")


class AskResponse(BaseModel):
    question: str
    answer: str
    tool: str = ""
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0


@app.get("/api/health", tags=["meta"])
@app.get("/health", tags=["meta"])
def health():
    """Kiểm tra trạng thái backend và cấu hình."""
    return {
        "status": "ok",
        "service": "agent_ATIN v3 Backend",
        "llm_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "db_configured": settings.db_configured,
        "monitoring_enabled": settings.monitoring_enabled,
    }


@app.get("/api/models", tags=["meta"])
def get_available_models():
    """Danh sách các model AI được hỗ trợ."""
    return {
        "active_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "supported_models": [
            {
                "id": "gpt-4o-mini",
                "name": "OpenAI Cloud (gpt-4o-mini)",
                "provider": "openai",
            },
            {
                "id": "qwen3-4b",
                "name": "Self-hosted Qwen3-4B",
                "provider": "self_hosted",
                "endpoint": settings.model_base_url,
            },
        ],
    }


from src.llm import ping as llm_ping

@app.get("/api/llm/ping", tags=["meta"])
def ping_llm():
    """Endpoint ping LLM."""
    try:
        status = llm_ping()
        return {
            "status": status,
            "backend": settings.llm_backend,
            "model": settings.effective_model,
            "base_url": settings.effective_base_url or "",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))



@app.get("/api/config", tags=["meta"])
def get_config():
    """Cung cấp thông tin cấu hình an toàn cho Frontend."""
    return {
        "llm_backend": settings.llm_backend,
        "active_model": settings.effective_model,
        "self_hosted_endpoint": settings.model_base_url,
        "self_hosted_model": settings.model_name,
        "monitoring_enabled": settings.monitoring_enabled,
        "supported_domains": [
            "Phương tiện (ITS)",
            "Vùng cấm (Fence)",
            "Khuôn mặt (Face)",
            "Ẩu đả (Fight)",
            "Đám đông (Crowd)",
            "Leo trèo (Intrusion)",
            "Cháy khói (Fire)",
            "Mực nước (Water)",
        ],
    }


# ==============================================================================
# Sessions API (Phase 4)
# ==============================================================================


@app.get("/api/sessions", response_model=SessionListResponse, tags=["sessions"])
def api_list_sessions(
    user_id: str = Query(..., min_length=1, description="ID người dùng"),
) -> SessionListResponse:
    """Liệt kê danh sách các phiên hội thoại của người dùng."""
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    sessions = list_sessions(user_id=user_id.strip())
    return SessionListResponse(sessions=sessions)


@app.post("/api/sessions", response_model=SessionItem, tags=["sessions"])
def api_create_session(req: CreateSessionRequest) -> SessionItem:
    """Tạo phiên hội thoại mới cho người dùng."""
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    sess = create_session(user_id=req.user_id.strip(), title=req.title)
    return SessionItem(**sess)


@app.delete("/api/sessions/{session_id}", response_model=DeleteSessionResponse, tags=["sessions"])
def api_delete_session(
    session_id: str,
    user_id: str = Query(..., min_length=1, description="ID người dùng"),
) -> DeleteSessionResponse:
    """Xóa một phiên hội thoại theo session_id và user_id."""
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    deleted = delete_session(session_id=session_id, user_id=user_id.strip())
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteSessionResponse(deleted=True)


@app.get(
    "/api/sessions/{session_id}/messages",
    response_model=SessionMessagesResponse,
    tags=["sessions"],
)
def api_get_session_messages(
    session_id: str,
    user_id: str = Query(..., min_length=1, description="ID người dùng"),
) -> SessionMessagesResponse:
    """Lấy lịch sử tin nhắn short-term của một phiên hội thoại."""
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    messages = get_session_messages(session_id=session_id, user_id=user_id.strip())
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionMessagesResponse(messages=messages)


def _extract_sql_from_trace_nodes(nodes: list[dict[str, Any]]) -> str | None:
    """Lấy SQL cuối cùng từ các node generate_sql / validate_sql / execute_sql."""
    for node in reversed(nodes):
        node_id = node.get("node_id") or ""
        if node_id not in ("generate_sql", "validate_sql", "execute_sql", "repair_sql"):
            continue
        output = node.get("output")
        if isinstance(output, dict):
            sql = output.get("sql")
            if isinstance(sql, str) and sql.strip():
                return sql.strip()
    return None


def _build_agent_trace(
    nodes: list[dict[str, Any]],
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace: dict[str, Any] = {"nodes": nodes}
    if detail:
        trace["detail"] = detail.get("agent_detail") or detail.get("tool") or detail
    sql = _extract_sql_from_trace_nodes(nodes)
    if sql:
        trace["sql"] = sql
    return trace


def _persist_session_turn(
    *,
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    detail: dict[str, Any] | None = None,
    chart: dict[str, Any] | None = None,
    agent_trace: dict[str, Any] | None = None,
) -> None:
    """Lưu một lượt hỏi–đáp vào session store (short-term UI history)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    user_msg: dict[str, Any] = {"role": "user", "content": question, "timestamp": now}
    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": answer,
        "timestamp": now,
    }
    if detail:
        assistant_msg["detail"] = detail
    if chart:
        assistant_msg["chart"] = chart
    if agent_trace:
        assistant_msg["agent_trace"] = agent_trace
    append_session_messages(session_id, user_id, [user_msg, assistant_msg])


USER_ERROR_MAX_LEN = 240


def _short_user_error(message: str) -> str:
    """Cắt message hiển thị UI — không dump stack/SQL dài."""
    msg = (message or "").strip()
    if len(msg) <= USER_ERROR_MAX_LEN:
        return msg
    return msg[: USER_ERROR_MAX_LEN - 1].rstrip() + "…"


def _format_error_message(exc: Exception) -> str:
    """Định dạng thông báo lỗi thân thiện cho người dùng khi gặp sự cố DB hoặc LLM."""
    err_str = str(exc).lower()
    if any(k in err_str for k in ("clickhouse", "ch timeout")):
        return _short_user_error(
            "Lỗi cơ sở dữ liệu phân tích: không truy vấn được số liệu. Kiểm tra ClickHouse."
        )
    if any(k in err_str for k in ("database", "postgres", "psycopg2", "could not connect to server", "connection refused to server")):
        return _short_user_error(
            "Lỗi cơ sở dữ liệu VMS: không truy vấn được số liệu. Kiểm tra dịch vụ database."
        )
    if any(k in err_str for k in ("timeout", "timed out", "connection error", "connection refused", "apiconnectionerror", "connect error")):
        return _short_user_error(
            "Lỗi mô hình AI: quá thời gian chờ hoặc máy chủ không phản hồi. Thử lại sau."
        )
    if any(k in err_str for k in ("rate limit", "429", "quota", "too many requests")):
        return _short_user_error(
            "Mô hình AI đang bận (rate limit). Vui lòng thử lại sau giây lát."
        )
    if any(k in err_str for k in ("llm structured", "parse", "schema", "validationerror")):
        return _short_user_error(
            "Mô hình AI trả về sai định dạng. Thử lại với cách diễn đạt khác."
        )
    if (
        any(k in err_str for k in ("thiếu biến", "template rỗng", "placeholder", "render prompt"))
        or ("prompt" in err_str and any(k in err_str for k in ("thiếu", "rỗng", "template", "biến", "placeholder")))
    ):
        return _short_user_error(
            "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
        )
    if any(k in err_str for k in ("lỗi tạo sql", "lỗi validate sql", "vượt quá số lần sửa", "select ", " from ")):
        return _short_user_error(
            "Không tạo được truy vấn dữ liệu phù hợp. Thử câu hỏi đơn giản hơn."
        )
    if any(k in err_str for k in ("lỗi truy vấn cơ sở dữ liệu", "lỗi execute")):
        return _short_user_error(
            "Lỗi thực thi truy vấn. Tạm thời không lấy được số liệu. Thử lại sau."
        )
    return _short_user_error(
        "Không thể xử lý câu hỏi lúc này. Vui lòng thử lại hoặc diễn đạt khác."
    )




@app.post("/api/chat", response_model=ChatResponse, tags=["agent"])
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

        try:
            cached = _lookup_ttl_cache(question)
        except Exception as exc:
            logger.warning("Cache lookup failed on chat: %s", exc)
            cached = None
        if isinstance(cached, dict) and "answer" in cached:
            logger.info("cache hit")
            detail_payload = {
                "tool": cached.get("tool", ""),
                "columns": cached.get("columns", []),
                "row_count": cached.get("row_count", 0),
                "agent_detail": cached.get("agent_detail", ""),
                "cache_hit": True,
            }
            response = ChatResponse(
                question=cached.get("question", req.question),
                answer=cached["answer"],
                tool=cached.get("tool", ""),
                detail=detail_payload,
                row_count=cached.get("row_count", 0),
            )
            t["output"] = {
                "status": "ok",
                "answer": response.answer,
                "tool": response.tool,
                "row_count": response.row_count,
                "cached": True,
            }
            return response

        try:
            from src.agent.intent import is_chat_greeting
            from src.agent.rewrite import rewrite_question_safe
            from src.llm.schemas import RewrittenQuestion

            if is_chat_greeting(question):
                rewritten = RewrittenQuestion(text=question, intent_hint="chat")
            else:
                rewritten = rewrite_question_safe(question)
            cache_q = rewritten.text if (rewritten and rewritten.text) else question
            out = run_agent(
                Agent_Input(question=req.question.strip(), rewritten=rewritten, user_id=req.user_id),
                parent_span=t.get("_span"),
                session_id=req.session_id,
                user_id=req.user_id,
            )
        except GuardrailViolation:
            raise
        except Exception as exc:
            friendly_msg = _format_error_message(exc)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query

        cache_data = {
            "question": out.question,
            "answer": out.answer,
            "tool": query.tool if query else "",
            "columns": query.columns if query else [],
            "rows": query.rows if query else [],
            "row_count": query.row_count if query else 0,
            "agent_detail": out.detail,
        }
        route = out.detail or getattr(out, "intent", "")
        try:
            set_ttl_cached(make_cache_key(cache_q, route=route), cache_data)
        except Exception as exc:
            logger.warning("Failed to store TTL cache on chat: %s", exc)

        detail_payload: dict[str, Any] = {
            "tool": query.tool if query else "",
            "columns": query.columns if query else [],
            "row_count": query.row_count if query else 0,
            "agent_detail": out.detail,
        }

        response = ChatResponse(
            question=out.question,
            answer=out.answer,
            tool=query.tool if query else "",
            detail=detail_payload,
            row_count=query.row_count if query else 0,
        )
        t["output"] = {
            "status": "ok",
            "answer": response.answer,
            "tool": response.tool,
            "row_count": response.row_count,
        }
        return response


@app.post("/ask", response_model=AskResponse, tags=["agent"])
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

        try:
            cached = _lookup_ttl_cache(question)
        except Exception as exc:
            logger.warning("Cache lookup failed on ask: %s", exc)
            cached = None
        if isinstance(cached, dict) and "answer" in cached:
            logger.info("cache hit")
            response = AskResponse(
                question=cached.get("question", req.question),
                answer=cached["answer"],
                tool=cached.get("tool", ""),
                columns=cached.get("columns", []),
                rows=cached.get("rows", []),
                row_count=cached.get("row_count", 0),
            )
            t["output"] = {
                "status": "ok",
                "answer": response.answer,
                "tool": response.tool,
                "row_count": response.row_count,
                "cached": True,
            }
            return response

        try:
            from src.agent.intent import is_chat_greeting
            from src.agent.rewrite import rewrite_question_safe
            from src.llm.schemas import RewrittenQuestion

            if is_chat_greeting(question):
                rewritten = RewrittenQuestion(text=question, intent_hint="chat")
            else:
                rewritten = rewrite_question_safe(question)
            cache_q = rewritten.text if (rewritten and rewritten.text) else question
            out = run_agent(Agent_Input(question=req.question.strip(), rewritten=rewritten), parent_span=t.get("_span"))
        except GuardrailViolation:
            raise
        except Exception as exc:
            friendly_msg = _format_error_message(exc)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query

        cache_data = {
            "question": out.question,
            "answer": out.answer,
            "tool": query.tool if query else "",
            "columns": query.columns if query else [],
            "rows": query.rows if query else [],
            "row_count": query.row_count if query else 0,
            "agent_detail": out.detail,
        }
        route = out.detail or getattr(out, "intent", "")
        try:
            set_ttl_cached(make_cache_key(cache_q, route=route), cache_data)
        except Exception as exc:
            logger.warning("Failed to store TTL cache on ask: %s", exc)

        response = AskResponse(
            question=out.question,
            answer=out.answer,
            tool=query.tool if query else "",
            columns=query.columns if query else [],
            rows=query.rows if query else [],
            row_count=query.row_count if query else 0,
        )
        t["output"] = {
            "status": "ok",
            "answer": response.answer,
            "tool": response.tool,
            "row_count": response.row_count,
        }
        return response


@app.exception_handler(GuardrailViolation)
def guardrail_violation_handler(request: Request, exc: GuardrailViolation) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": rejection_detail(exc.reason),
            "error": "input_rejected",
            "reason": exc.reason,
            "details": exc.details,
        },
    )


@app.post("/api/feedback", tags=["feedback"])
def submit_feedback(req: FeedbackRequest) -> dict[str, Any]:
    """Lưu trữ phản hồi người dùng (Like/Dislike kèm lý do, ảnh và agent trace)."""
    if req.rating not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="rating phải là 'positive' hoặc 'negative'.")
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question không được để trống.")
    if not req.answer or not req.answer.strip():
        raise HTTPException(status_code=400, detail="answer không được để trống.")

    from src.feedback import save_feedback_record

    try:
        record = save_feedback_record(req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": "ok",
        "feedback_id": record["id"],
        "message": "Phản hồi đã được ghi nhận thành công.",
        "record": record,
    }


@app.get("/api/feedback", tags=["feedback"])
def list_feedback() -> dict[str, Any]:
    """Danh sách phản hồi người dùng đã lưu trữ trong data/feedback.json."""
    from src.feedback import get_all_feedback

    items = get_all_feedback()
    return {"status": "ok", "total": len(items), "feedback": items}


@app.post("/api/agent/stream", tags=["agent"])
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

            try:
                cached = _lookup_ttl_cache(question)
            except Exception as exc:
                logger.warning("Cache lookup failed on stream: %s", exc)
                cached = None
            if isinstance(cached, dict) and "answer" in cached:
                t["output"] = {
                    "status": "ok",
                    "answer": cached["answer"],
                    "tool": cached.get("tool", ""),
                    "row_count": cached.get("row_count", 0),
                    "cached": True,
                }
                yield f'data: {json.dumps({"node_id": "cache", "status": "done", "input": question, "output": cached["answer"]}, ensure_ascii=False)}\n\n'

                detail_payload = {
                    "tool": cached.get("tool", ""),
                    "columns": cached.get("columns", []),
                    "row_count": cached.get("row_count", 0),
                    "agent_detail": cached.get("agent_detail", ""),
                    "cache_hit": True,
                }
                _persist_session_turn(
                    session_id=req.session_id.strip(),
                    user_id=req.user_id.strip(),
                    question=question,
                    answer=cached["answer"],
                    detail=detail_payload,
                )
                if req.stream_tokens:
                    for delta in _split_into_chunks(cached["answer"]):
                        yield f'data: {json.dumps({"node_id": "__answer__", "status": "chunk", "delta": delta}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"node_id": "__answer__", "status": "done", "output": cached["answer"], "detail": detail_payload}, ensure_ascii=False)}\n\n'
                return

            try:
                from src.agent.intent import is_chat_greeting
                from src.agent.rewrite import rewrite_question_safe
                from src.agent.graph import run_agent_stream, Agent_Input
                from src.llm.schemas import RewrittenQuestion

                if is_chat_greeting(question):
                    rewritten = RewrittenQuestion(text=question, intent_hint="chat")
                else:
                    rewritten = rewrite_question_safe(question)
                cache_q = rewritten.text if (rewritten and rewritten.text) else question
                stream_kwargs = {"parent_span": t.get("_span")}
                target_fn = getattr(run_agent_stream, "side_effect", None) or run_agent_stream
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

                for event in run_agent_stream(
                    Agent_Input(
                        question=req.question.strip(),
                        rewritten=rewritten,
                        user_id=req.user_id,
                        stream_tokens=req.stream_tokens,
                    ),
                    **stream_kwargs,
                ):
                    if "__final_result__" in event:
                        out = event["__final_result__"]
                        query = getattr(out, "query", None)

                        cache_data = {
                            "question": out.question,
                            "answer": out.answer,
                            "tool": getattr(query, "tool", "") if query else "",
                            "columns": getattr(query, "columns", []) if query else [],
                            "rows": getattr(query, "rows", []) if query else [],
                            "row_count": getattr(query, "row_count", 0) if query else 0,
                            "agent_detail": out.detail,
                        }
                        route = getattr(out, "detail", "") or getattr(out, "intent", "")
                        try:
                            set_ttl_cached(make_cache_key(cache_q, route=route), cache_data)
                        except Exception as exc:
                            logger.warning("Failed to store TTL cache on stream: %s", exc)

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

                        t["output"] = {
                            "status": "ok",
                            "answer": out.answer,
                            "tool": getattr(query, "tool", "") if query else "",
                            "row_count": getattr(query, "row_count", 0) if query else 0,
                        }
                        chart_payload = None
                        if last_chart_png or detail_payload.get("chart_spec"):
                            chart_payload = {
                                "png": last_chart_png,
                                "spec": detail_payload.get("chart_spec"),
                                "type": detail_payload.get("chart_type", "bar"),
                                "rows": detail_payload.get("chart_rows"),
                            }
                        agent_trace = _build_agent_trace(stream_trace_nodes, detail_payload)
                        _persist_session_turn(
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
                        chart_sse = _build_chart_sse_event(spec_dict, event_chart_png, last_chart_rows)
                        yield f"data: {json.dumps(chart_sse, ensure_ascii=False)}\n\n"

                    try:
                        payload = json.dumps(_sanitize_sse_event(event), ensure_ascii=False, default=str)
                    except Exception as ser_exc:
                        friendly_msg = _format_error_message(ser_exc)
                        yield f'data: {json.dumps({"node_id": "error", "status": "done", "output": friendly_msg}, ensure_ascii=False)}\n\n'
                        yield f'data: {json.dumps({"node_id": "__answer__", "status": "error", "output": friendly_msg, "detail": {"status": "error"}}, ensure_ascii=False)}\n\n'
                        break
                    yield f"data: {payload}\n\n"
            except Exception as exc:
                t["output"] = {"status": "error", "error": str(exc)}
                friendly_msg = _format_error_message(exc)
                yield f'data: {json.dumps({"node_id": "error", "status": "done", "output": friendly_msg}, ensure_ascii=False)}\n\n'
                yield f'data: {json.dumps({"node_id": "__answer__", "status": "error", "output": friendly_msg, "detail": {"status": "error"}}, ensure_ascii=False)}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount static frontend if available
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

    @app.get("/", include_in_schema=False)
    def index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "agent_ATIN v3 Backend running"}

