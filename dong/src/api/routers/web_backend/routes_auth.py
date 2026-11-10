"""Auth proxy — FE gọi dong, dong gọi IAM (tránh CORS)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.domain.authz.resolve import access_context_from_user_ctx
from src.infra.auth.iam_client import IamError, fetch_auth_me, login
from src.shared.config import settings

router = APIRouter(tags=['auth'])


class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember: bool = True


def _public_user(user_ctx: dict) -> dict:
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=None)
    org = ctx.effective_org_id
    if org is None and 'organization_id' in user_ctx and user_ctx['organization_id'] is not None:
        org = user_ctx['organization_id']
    full_name = user_ctx['full_name'] if 'full_name' in user_ctx and user_ctx['full_name'] else ctx.user_id
    return {
        'user_id': ctx.user_id,
        'role_group': ctx.role_group,
        'organization_id': org,
        'full_name': full_name,
        'dashboard_tabs': list(ctx.dashboard_tabs),
        'scope': {
            'site_ids': list(ctx.scope.site_ids),
            'area_ids': list(ctx.scope.area_ids),
            'zone_ids': list(ctx.scope.zone_ids),
            'unrestricted': ctx.scope.unrestricted,
        },
    }


@router.post('/api/auth/login')
def auth_login(body: LoginBody):
    """Proxy IAM login — trả access_token + user tóm tắt cho demo FE."""
    if not (settings.iam_base_url or '').strip():
        raise HTTPException(status_code=503, detail='IAM_BASE_URL chưa cấu hình')
    try:
        tokens = login(body.username.strip(), body.password, remember=body.remember)
        user_ctx = fetch_auth_me(str(tokens['access_token']))
    except IamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    out = {
        'access_token': tokens['access_token'],
        'user': _public_user(user_ctx),
    }
    if 'refresh_token' in tokens:
        out['refresh_token'] = tokens['refresh_token']
    if 'expires_in' in tokens:
        out['expires_in'] = tokens['expires_in']
    return out


@router.get('/api/auth/me')
def auth_me(authorization: str | None=Header(default=None)):
    """Proxy IAM /auth/me — cần Bearer."""
    if not authorization or not authorization.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Thiếu Authorization Bearer token')
    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail='Thiếu Authorization Bearer token')
    try:
        user_ctx = fetch_auth_me(token)
    except IamError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _public_user(user_ctx)
