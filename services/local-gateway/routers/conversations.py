from __future__ import annotations

from auth.deps import require_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from storage.conversations import list_conversation_tools
from storage.models import UserConversation, get_db
from storage.users import AuthUser

router = APIRouter(tags=['conversations'])


@router.get('/api/conversations/{conversation_id}/tools')
async def get_conversation_tools(
    conversation_id: str,
    user: AuthUser = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    row = (
        db.query(UserConversation)
        .filter(UserConversation.conversation_id == conversation_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    if row.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail='Forbidden')
    tools = list_conversation_tools(db, conversation_id)
    return [
        {
            'tool_kind': t.tool_kind,
            'tool_name': t.tool_name,
            'tool_version': t.tool_version,
            'source': t.source,
            'enabled': t.enabled,
            'installed_at': t.installed_at.isoformat() if t.installed_at else None,
            'last_used_at': t.last_used_at.isoformat() if t.last_used_at else None,
        }
        for t in tools
    ]
