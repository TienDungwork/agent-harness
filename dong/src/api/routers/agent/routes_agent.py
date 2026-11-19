"""SSE agent stream — mỏng như vn-stock chat router; logic ở AgentTurnService."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.helpers.auth import get_access_context
from src.api.models.schemas import ChatRequest
from src.application.agent_turn import AgentTurnService
from src.domain.authz.access_context import AccessContext
from src.domain.guardrails import check_input, redact_pii

router = APIRouter(tags=["agent"])
_turn = AgentTurnService()
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _require_ids(req: ChatRequest) -> None:
    if not (req.session_id or "").strip():
        raise HTTPException(status_code=400, detail="session_id không được để trống.")
    if not (req.user_id or "").strip():
        raise HTTPException(status_code=400, detail="user_id không được để trống.")


def _uid(access: AccessContext, fallback: str) -> str:
    if access.user_id and access.user_id != "default":
        return access.user_id
    return (fallback or "default").strip()


@router.post("/api/agent/stream", tags=["agent"])
def stream_agent(
    req: ChatRequest,
    request: Request,
    access: Annotated[AccessContext, Depends(get_access_context)],
) -> StreamingResponse:
    """SSE — check_input + redact_pii (gán lại question) rồi vào graph."""
    _require_ids(req)
    q = (req.question or "").strip()
    check_input(q)
    req.question = redact_pii(q)
    request.state.user_id = req.user_id.strip()
    return StreamingResponse(
        _turn.stream_sse_frames(req, access=access, user_id=_uid(access, req.user_id)),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
