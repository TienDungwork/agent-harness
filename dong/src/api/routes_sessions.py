"""Sessions CRUD + messages."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.sessions import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionItem,
    SessionListResponse,
    SessionMessagesResponse,
    create_session,
    delete_session,
    get_session_messages,
    list_sessions,
)

router = APIRouter(tags=["sessions"])


@router.get("/api/sessions", response_model=SessionListResponse)
def api_list_sessions(user_id: str = Query(..., min_length=1)) -> SessionListResponse:
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    return SessionListResponse(sessions=list_sessions(user_id=uid))


@router.post("/api/sessions", response_model=SessionItem)
def api_create_session(req: CreateSessionRequest) -> SessionItem:
    if not req.user_id or not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    sess = create_session(user_id=req.user_id.strip(), title=req.title)
    return SessionItem(**sess)


@router.delete("/api/sessions/{session_id}", response_model=DeleteSessionResponse)
def api_delete_session(session_id: str, user_id: str = Query(..., min_length=1)) -> DeleteSessionResponse:
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not delete_session(session_id=session_id, user_id=uid):
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteSessionResponse(deleted=True)


@router.get("/api/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def api_get_session_messages(
    session_id: str,
    user_id: str = Query(..., min_length=1),
) -> SessionMessagesResponse:
    uid = user_id.strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    messages = get_session_messages(session_id=session_id, user_id=uid)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionMessagesResponse(messages=messages)
