"""FastAPI entry — mount routers; re-export symbols cho tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.domain.agents.graph import Agent_Input
from src.shared.config import settings


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if settings.memory_enabled:
        from src.infra.memory.db import init_agent_storage
        from src.infra.memory.shortterm import get_checkpointer
        from src.infra.session.store import ensure_session_storage

        init_agent_storage()
        ensure_session_storage()
        from src.shared.feedback import load_legacy_feedback_for_migration
        from src.infra.feedback.store import ensure_feedback_storage

        ensure_feedback_storage(load_legacy_feedback_for_migration)
        if settings.short_term_memory_enabled:
            get_checkpointer()
    yield


def run_agent(inp, parent_span=None, session_id: str = "default", user_id: str | None = None):
    from src.domain.agents.graph import run_agent as _graph_run_agent

    return _graph_run_agent(inp, parent_span=parent_span, session_id=session_id, user_id=user_id)


def run_agent_stream(inp, parent_span=None, session_id: str = "default", user_id: str | None = None):
    from src.domain.agents.graph import run_agent_stream as _graph_run_agent_stream

    return _graph_run_agent_stream(inp, parent_span=parent_span, session_id=session_id, user_id=user_id)


from src.api.helpers.errors import (
    USER_ERROR_MAX_LEN,
    format_error_message as _format_error_message,
    short_user_error as _short_user_error,
)
from src.api.routers.routes_agent import ask, chat, router as agent_router, stream_agent
from src.api.routers.routes_feedback import router as feedback_router
from src.api.routers.routes_memory import router as memory_router
from src.api.routers.routes_meta import router as meta_router
from src.api.routers.routes_sessions import router as sessions_router
from src.api.models.schemas import AskRequest, AskResponse, ChatRequest, ChatResponse
from src.api.helpers.sse_helpers import build_chart_sse_event as _build_chart_sse_event
from src.shared.guardrails import GuardrailViolation, rejection_detail
app = FastAPI(
    title="agent_ATIN v3 API",
    description="Backend API Gateway cho hệ thống VMS KCN Hưng Phú",
    version="3.0.0",
    lifespan=_lifespan,
)

_cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta_router)
app.include_router(sessions_router)
app.include_router(memory_router)
app.include_router(feedback_router)
app.include_router(agent_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.middleware("http")
async def _api_access_middleware(request: Request, call_next):
    from src.api.helpers.auth import api_access_required

    denied = api_access_required(request)
    if denied is not None:
        return denied
    return await call_next(request)


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


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend_static")

    @app.get("/", include_in_schema=False)
    def index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "agent_ATIN v3 Backend running"}
