from __future__ import annotations

from sqlalchemy.orm import Session
from storage.models import InfraAuditLog


def write_audit(
    db: Session,
    *,
    actor_user_id: str | None,
    action: str,
    success: bool,
    actor_kind: str = 'user',
    conversation_id: str | None = None,
    server_id: str | None = None,
    server_name: str | None = None,
    command_id: str | None = None,
    command_rendered: str | None = None,
    exit_code: int | None = None,
    duration_ms: int | None = None,
    error_excerpt: str | None = None,
) -> InfraAuditLog:
    excerpt = error_excerpt
    if excerpt and len(excerpt) > 500:
        excerpt = excerpt[:500]
    row = InfraAuditLog(
        actor_user_id=actor_user_id,
        actor_kind=actor_kind,
        conversation_id=conversation_id,
        server_id=server_id,
        server_name=server_name,
        action=action,
        command_id=command_id,
        command_rendered=command_rendered,
        exit_code=exit_code,
        success=success,
        duration_ms=duration_ms,
        error_excerpt=excerpt,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
