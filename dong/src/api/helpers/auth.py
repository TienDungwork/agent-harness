"""API auth: X-API-Key middleware + IAM AccessContext dependency."""
from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

from src.domain.authz.resolve import AccessDenied, resolve_access_context
from src.shared.config import settings

_PUBLIC_API_SUFFIXES = ('/api/health', '/api/llm/ping')


def api_access_required(request: Request) -> JSONResponse | None:
    """Trả về 401 JSONResponse nếu thiếu/sai key; None nếu cho qua."""
    path = request.url.path
    if not path.startswith('/api/'):
        return None
    if any((path == p or path.rstrip('/') == p for p in _PUBLIC_API_SUFFIXES)):
        return None
    expected = (settings.api_access_key or '').strip()
    if not expected:
        return None
    provided = (request.headers.get('x-api-key') or '').strip()
    if provided != expected:
        return JSONResponse(status_code=401, content={'detail': 'Invalid or missing X-API-Key'})
    return None


def get_access_context(
    request: Request,
    authorization: Annotated[str | None, Header()]=None,
    x_organization_id: Annotated[str | None, Header(alias='X-Organization-Id')]=None,
):
    """FastAPI Depends: Bearer + X-Organization-Id → AccessContext."""
    token = None
    if authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1].strip() or None
    org_id = None
    if x_organization_id and str(x_organization_id).strip():
        try:
            org_id = int(str(x_organization_id).strip())
        except ValueError:
            org_id = None
    try:
        ctx = resolve_access_context(token=token, requested_org_id=org_id, user_id_fallback='default')
    except AccessDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    request.state.access_context = ctx
    return ctx
