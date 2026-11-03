"""Human feedback API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from src.shared.feedback import get_all_feedback, save_feedback_record
from src.infra.llm.schemas import FeedbackRequest

router = APIRouter(tags=["feedback"])


@router.post("/api/feedback")
def submit_feedback(req: FeedbackRequest) -> dict[str, Any]:
    if req.rating not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="rating phải là 'positive' hoặc 'negative'.")
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question không được để trống.")
    if not req.answer or not req.answer.strip():
        raise HTTPException(status_code=400, detail="answer không được để trống.")
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


@router.get("/api/feedback")
def list_feedback() -> dict[str, Any]:
    items = get_all_feedback()
    return {"status": "ok", "total": len(items), "feedback": items}
