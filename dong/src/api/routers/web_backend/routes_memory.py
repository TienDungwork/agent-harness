"""Long-term memory API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.models.schemas import MemoryDeleteResponse, MemoryListResponse
from src.infra.memory.longterm import clear_long_term, recall_long_term
from src.shared.config import settings

router = APIRouter(tags=["memory"])


def _long_term_disabled_response(user_id: str) -> MemoryListResponse:
    return MemoryListResponse(status="disabled", user_id=user_id, facts=[], memories=[], total=0)


@router.get("/api/memory", response_model=MemoryListResponse)
def api_get_user_memory(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=500),
) -> MemoryListResponse:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not settings.long_term_memory_enabled:
        return _long_term_disabled_response(uid)
    facts = recall_long_term(user_id=uid, query="", k=limit)
    return MemoryListResponse(status="ok", user_id=uid, facts=facts, memories=facts, total=len(facts))


@router.delete("/api/memory", response_model=MemoryDeleteResponse)
def api_delete_user_memory(user_id: str = Query(..., min_length=1)) -> MemoryDeleteResponse:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not settings.long_term_memory_enabled:
        return MemoryDeleteResponse(
            status="disabled",
            message="Long-term memory is disabled (MEMORY_LONG_TERM_ENABLED=false).",
            user_id=uid,
            deleted=False,
        )
    clear_long_term(user_id=uid)
    return MemoryDeleteResponse(
        status="ok",
        message=f"Đã xóa toàn bộ bộ nhớ của người dùng '{uid}'.",
        user_id=uid,
        deleted=True,
    )
