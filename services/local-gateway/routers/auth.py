from __future__ import annotations

import time

from auth.deps import get_session_manager, require_user
from auth.keycloak import KeycloakClient
from auth.session import SessionManager, SessionPayload
from config import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from storage.models import get_db
from storage.users import (
    AuthUser,
    authenticate_local,
    to_auth_user,
    upsert_user_from_claims,
)

router = APIRouter(prefix='/api/auth', tags=['auth'])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    id: str
    username: str
    email: str | None
    is_admin: bool
    credit_balance: float


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path='/',
    )


def _issue_cookie(
    *,
    response: Response,
    settings: Settings,
    sessions: SessionManager,
    user,
    access_token: str = 'local',
    refresh_token: str | None = None,
) -> MeResponse:
    cookie = sessions.issue(
        SessionPayload(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            access_token=access_token,
            refresh_token=refresh_token,
            issued_at=int(time.time()),
        )
    )
    _set_session_cookie(response, settings, cookie)
    auth_user = to_auth_user(user)
    return MeResponse(
        id=auth_user.id,
        username=auth_user.username,
        email=auth_user.email,
        is_admin=auth_user.is_admin,
        credit_balance=auth_user.credit_balance,
    )


@router.post('/login', response_model=MeResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_session_manager),
) -> MeResponse:
    backend = (settings.auth_backend or 'local').strip().lower()

    if backend == 'local':
        try:
            user = authenticate_local(
                db, username=body.username, password=body.password
            )
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return _issue_cookie(
            response=response, settings=settings, sessions=sessions, user=user
        )

    if backend != 'keycloak':
        raise HTTPException(
            status_code=500,
            detail=f'Unsupported AUTH_BACKEND={settings.auth_backend!r}',
        )

    kc = KeycloakClient(settings)
    try:
        tokens = await kc.password_grant(body.username, body.password)
        info = await kc.userinfo(tokens.access_token)
        roles = await kc.decode_roles_from_access_token(tokens.access_token)
        if not roles:
            roles = info.roles
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    is_admin = 'admin' in roles
    try:
        user = upsert_user_from_claims(
            db,
            keycloak_sub=info.sub,
            username=info.username,
            email=info.email,
            is_admin=is_admin,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return _issue_cookie(
        response=response,
        settings=settings,
        sessions=sessions,
        user=user,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post('/logout')
async def logout(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    response.delete_cookie(settings.session_cookie_name, path='/')
    return {'ok': True}


@router.get('/me', response_model=MeResponse)
async def me(user: AuthUser = Depends(require_user)) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        credit_balance=user.credit_balance,
    )
