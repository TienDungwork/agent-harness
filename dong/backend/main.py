"""Backend FastAPI entry point — Phase 4 API Gateway & Agent Routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.config import settings
from src.agent.graph import Agent_Input, run_agent
from src.guardrails import (
    OUT_OF_SCOPE_REPLY,
    GuardrailViolation,
    check_input,
    check_output,
    in_scope,
    redact_pii,
)
from backend.monitoring.tracing import trace_answer

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


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi thống kê tự nhiên")
    model_provider: str | None = Field(default=None, description="Tùy chọn: 'openai' hoặc 'self_hosted'")
    model_override: str | None = Field(default=None, description="Tùy chọn ghi đè model name")


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


def _format_error_message(exc: Exception) -> str:
    """Định dạng thông báo lỗi thân thiện cho người dùng khi gặp sự cố DB hoặc LLM."""
    err_str = str(exc).lower()
    if any(k in err_str for k in ("database", "postgres", "psycopg2", "could not connect to server", "connection refused to server")):
        return "Lỗi kết nối cơ sở dữ liệu VMS: Hệ thống tạm thời không thể truy vấn số liệu từ Database. Vui lòng kiểm tra lại dịch vụ cơ sở dữ liệu."
    if any(k in err_str for k in ("timeout", "timed out", "connection error", "connection refused", "apiconnectionerror", "connect error")):
        return "Lỗi kết nối mô hình AI: Quá thời gian chờ (timeout) hoặc máy chủ mô hình AI không phản hồi. Vui lòng thử lại sau."
    if any(k in err_str for k in ("rate limit", "429", "quota", "too many requests")):
        return "Mô hình AI đang bận hoặc đạt giới hạn lượt gọi (Rate Limit). Vui lòng thử lại sau giây lát."
    return f"Không thể xử lý câu hỏi: {exc}"


@app.post("/api/chat", response_model=ChatResponse, tags=["agent"])
def chat(req: ChatRequest) -> ChatResponse:
    """Endpoint chính nhận câu hỏi từ Frontend UI."""
    with trace_answer("chat", req.question, metadata={"endpoint": "/api/chat", "provider": req.model_provider}) as t:
        check_input(req.question)
        if not in_scope(req.question):
            t["output"] = {"status": "out_of_scope", "answer": OUT_OF_SCOPE_REPLY}
            return ChatResponse(
                question=req.question,
                answer=OUT_OF_SCOPE_REPLY,
                detail={"status": "out_of_scope"},
                row_count=0,
            )

        question = redact_pii(req.question)
        try:
            out = run_agent(Agent_Input(question=question), parent_span=t.get("_span"))
        except Exception as exc:
            friendly_msg = _format_error_message(exc)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query
        evidence = [question] + (
            [f"{c}={v}" for row in query.rows for c, v in zip(query.columns, row)] if query else []
        )
        result = check_output(out.answer, evidence)

        detail_payload: dict[str, Any] = {
            "tool": query.tool if query else "",
            "columns": query.columns if query else [],
            "row_count": query.row_count if query else 0,
            "agent_detail": out.detail,
        }

        response = ChatResponse(
            question=out.question,
            answer=result.answer,
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
    with trace_answer("ask", req.question, metadata={"endpoint": "/ask"}) as t:
        check_input(req.question)
        if not in_scope(req.question):
            t["output"] = {"status": "out_of_scope", "answer": OUT_OF_SCOPE_REPLY}
            return AskResponse(question=req.question, answer=OUT_OF_SCOPE_REPLY)

        question = redact_pii(req.question)
        try:
            out = run_agent(Agent_Input(question=question), parent_span=t.get("_span"))
        except Exception as exc:
            friendly_msg = _format_error_message(exc)
            raise HTTPException(status_code=503, detail=friendly_msg) from exc

        query = out.query
        evidence = [question] + (
            [f"{c}={v}" for row in query.rows for c, v in zip(query.columns, row)] if query else []
        )
        result = check_output(out.answer, evidence)

        response = AskResponse(
            question=out.question,
            answer=result.answer,
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
            "detail": f"Câu hỏi bị từ chối: {exc.reason}",
            "error": "input_rejected",
            "reason": exc.reason,
            "details": exc.details,
        },
    )


# Mount static frontend if available
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

    @app.get("/", include_in_schema=False)
    def index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "agent_ATIN v3 Backend running"}

