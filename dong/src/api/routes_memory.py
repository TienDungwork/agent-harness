"""Long-term memory API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import MemoryDeleteResponse, MemoryListResponse
from src.memory.longterm import clear_long_term, recall_long_term

router = APIRouter(tags=["memory"])


@router.get("/api/memory", response_model=MemoryListResponse)
def api_get_user_memory(
    user_id: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=500),
) -> MemoryListResponse:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    facts = recall_long_term(user_id=uid, query="", k=limit)
    return MemoryListResponse(status="ok", user_id=uid, facts=facts, memories=facts, total=len(facts))


@router.delete("/api/memory", response_model=MemoryDeleteResponse)
def api_delete_user_memory(user_id: str = Query(..., min_length=1)) -> MemoryDeleteResponse:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    clear_long_term(user_id=uid)
    return MemoryDeleteResponse(
        status="ok",
        message=f"Đã xóa toàn bộ bộ nhớ của người dùng '{uid}'.",
        user_id=uid,
        deleted=True,
    )
