from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.config.logging import setup_logging
from agent.llm.profiles import default_profile_id, profiles_public, resolve_profile

setup_logging()

app = FastAPI(title="Duy Data Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_origin_regex=r"http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model_id: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    intent: str | None = None
    intent_reason: str | None = None
    sql: str | None = None
    database: str | None = None
    row_count: int | None = None
    error: str | None = None
    doc_card_id: str | None = None
    doc_card_title: str | None = None
    chart_png_base64: str | None = None
    chart_meta: str | None = None
    web_sources: list[dict[str, str]] | None = None
    llm_model_id: str | None = None
    llm_model_label: str | None = None


def _to_response(question: str, result: dict) -> AskResponse:
    qr = result.get("query_result") or {}
    sql = (result.get("sql") or "").strip() or None
    chart = (result.get("chart_png_base64") or "").strip() or None
    return AskResponse(
        question=str(result.get("question") or question),
        answer=str(result.get("answer") or ""),
        intent=result.get("intent") or None,
        intent_reason=result.get("intent_reason") or None,
        sql=sql,
        database=qr.get("database"),
        row_count=qr.get("row_count"),
        error=result.get("error") or None,
        doc_card_id=(result.get("doc_card_id") or None) or None,
        doc_card_title=(result.get("doc_card_title") or None) or None,
        chart_png_base64=chart,
        chart_meta=(result.get("chart_meta") or None) or None,
        web_sources=result.get("web_sources") or None,
        llm_model_id=(result.get("llm_model_id") or None) or None,
        llm_model_label=(result.get("llm_model_label") or None) or None,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/models")
def models_endpoint() -> dict:
    return {
        "default_id": default_profile_id(),
        "models": profiles_public(),
    }


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(body: AskRequest) -> AskResponse:
    from agent.graph.graph import ask

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi trống")

    try:
        resolve_profile(body.model_id)
        result = ask(question, model_id=body.model_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _to_response(question, result)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@app.post("/ask/stream")
def ask_stream_endpoint(body: AskRequest) -> StreamingResponse:
    from agent.graph.graph import ask_events

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Câu hỏi trống")

    try:
        resolve_profile(body.model_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def generate():
        try:
            for event in ask_events(question, model_id=body.model_id):
                yield _sse(event)
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
