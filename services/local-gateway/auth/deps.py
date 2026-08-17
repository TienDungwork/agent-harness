from __future__ import annotations

from config import Settings, get_settings
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from storage.models import User, get_db
from storage.users import AuthUser, to_auth_user

from auth.session import SessionManager, SessionPayload


def get_session_manager(settings: Settings = Depends(get_settings)) -> SessionManager:
    return SessionManager(settings)


def _read_session_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def require_session(
    request: Request,
    settings: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_session_manager),
) -> SessionPayload:
    raw = _read_session_cookie(request, settings)
    if not raw:
        raise HTTPException(status_code=401, detail='Not authenticated')
    try:
        return sessions.load(raw)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_user(
    session: SessionPayload = Depends(require_session),
    db: Session = Depends(get_db),
) -> AuthUser:
    user = db.query(User).filter(User.id == session.user_id).one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail='User not found or disabled')
    return to_auth_user(user)


def require_admin(user: AuthUser = Depends(require_user)) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='Admin required')
    return user
