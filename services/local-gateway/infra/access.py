from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from storage.models import InfraServer, InfraServerAccessGrant, User


def user_has_server_access(
    db: Session,
    *,
    user: User,
    server_id: str,
    required: str = 'read',
) -> bool:
    if user.is_admin and user.is_active:
        return True
    if not user.is_active:
        return False
    grant = (
        db.query(InfraServerAccessGrant)
        .filter(
            InfraServerAccessGrant.server_id == server_id,
            InfraServerAccessGrant.user_id == user.id,
        )
        .one_or_none()
    )
    if grant is None:
        return False
    if grant.expires_at is not None and grant.expires_at < datetime.now(timezone.utc):
        return False
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None or not server.is_active:
        return False
    if required == 'read':
        return grant.permission in ('read', 'operate')
    return grant.permission == 'operate'
