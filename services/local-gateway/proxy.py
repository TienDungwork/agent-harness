from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx
from auth.deps import require_session
from auth.session import SessionManager
from config import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from storage.credits import (
    InsufficientCredits,
    charge_credits,
    raise_http_for_credits,
    refund_credits,
)
from storage.models import User, UserConversation, UserSettingsBlob, get_db
from storage.users import (
    AuthUser,
    claim_conversation,
    list_user_conversation_ids,
    to_auth_user,
)

router = APIRouter(tags=['proxy'])

_CONV_RE = re.compile(
    r'^/api/conversations(?:/(?P<cid>[0-9a-fA-F-]{36}))?(?P<rest>/.*)?$'
)

_PUBLIC_PREFIXES = (
    '/healthz',
    '/api/auth/login',
    '/ready',
    '/alive',
    '/server_info',
    '/docs',
    '/redoc',
    '/openapi.json',
)

# Suffixes on /api/conversations/{id}/... that consume credits (agent work).
_CHARGEABLE_CONV_SUFFIXES = (
    '/events',
    '/ask_agent',
    '/run',
    '/message',
    '/start',
)


def _is_public(path: str) -> bool:
    if path in _PUBLIC_PREFIXES:
        return True
    return any(path.startswith(p + '/') for p in ('/docs',))


def _extract_conversation_id(path: str) -> str | None:
    m = _CONV_RE.match(path)
    if not m:
        return None
    return m.group('cid')


def _blob_kind_for_path(path: str) -> str | None:
    if path == '/api/settings':
        return 'settings'
    if path == '/api/settings/secrets' or path.startswith('/api/settings/secrets/'):
        return 'secrets'
    if path == '/api/profiles' or path.startswith('/api/profiles/'):
        return 'profiles'
    return None


def _is_chargeable_conversation_post(
    path: str,
) -> tuple[bool, str | None, float | None]:
    """Return (chargeable, conversation_id, cost_key).

    cost_key is 'conversation' or 'run'.
    """
    if path.rstrip('/') == '/api/conversations':
        return True, None, 'conversation'
    m = _CONV_RE.match(path)
    if not m:
        return False, None, None
    cid = m.group('cid')
    rest = m.group('rest') or ''
    for suffix in _CHARGEABLE_CONV_SUFFIXES:
        if rest == suffix or rest.startswith(suffix + '/'):
            return True, cid, 'run'
    return False, cid, None


def _get_blob(db: Session, user_id: str, kind: str) -> Any | None:
    row = (
        db.query(UserSettingsBlob)
        .filter(UserSettingsBlob.user_id == user_id, UserSettingsBlob.kind == kind)
        .one_or_none()
    )
    if row is None:
        return None
    payload = row.payload
    if isinstance(payload, (dict, list)):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {}
    return {}


def _put_blob(db: Session, user_id: str, kind: str, payload: Any) -> Any:
    row = (
        db.query(UserSettingsBlob)
        .filter(UserSettingsBlob.user_id == user_id, UserSettingsBlob.kind == kind)
        .one_or_none()
    )
    if row is None:
        row = UserSettingsBlob(user_id=user_id, kind=kind, payload=payload)
        db.add(row)
    else:
        row.payload = payload
    db.commit()
    return payload


async def _forward(
    request: Request,
    settings: Settings,
    *,
    path: str | None = None,
    body: bytes | None = None,
) -> Response:
    target_path = path or request.url.path
    url = f'{settings.agent_server_url.rstrip("/")}{target_path}'
    if request.url.query:
        url = f'{url}?{request.url.query}'

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {
            'host',
            'content-length',
            'connection',
            'cookie',
            'transfer-encoding',
        }
    }
    if settings.agent_server_api_key:
        headers['X-Session-API-Key'] = settings.agent_server_api_key

    if body is None and request.method not in ('GET', 'HEAD'):
        body = await request.body()

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )

    excluded = {'content-encoding', 'transfer-encoding', 'content-length', 'connection'}
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get('content-type'),
    )


def _filter_conversation_page(payload: Any, allowed: set[str]) -> Any:
    if not isinstance(payload, dict):
        return payload
    items = payload.get('items')
    if isinstance(items, list):
        filtered = []
        for item in items:
            cid = None
            if isinstance(item, dict):
                cid = item.get('id') or item.get('conversation_id')
            if cid is None or str(cid) in allowed:
                filtered.append(item)
        payload = {**payload, 'items': filtered}
    return payload


@router.api_route(
    '/beszel/{full_path:path}',
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
)
async def proxy_beszel(
    full_path: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    """Reverse-proxy Beszel hub. Requires GW session. Strips X-Frame-Options."""
    require_session(request, settings, SessionManager(settings))

    target = f'{settings.beszel_hub_url.rstrip("/")}/{full_path}'
    if request.url.query:
        target = f'{target}?{request.url.query}'

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {'host', 'content-length', 'connection', 'transfer-encoding'}
    }

    body = None
    if request.method not in ('GET', 'HEAD'):
        body = await request.body()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        upstream = await client.request(
            request.method, target, headers=headers, content=body
        )

    excluded = {
        'content-encoding',
        'transfer-encoding',
        'content-length',
        'connection',
        'x-frame-options',
        'content-security-policy',
    }
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in excluded
    }
    content: bytes = upstream.content
    media = upstream.headers.get('content-type') or ''
    if 'text/html' in media and b'</body>' in content and b'BESZEL' in content:
        inject = (
            b'<script>(function(){function goHome(e){e&&e.preventDefault();'
            b'var h=document.querySelector(\'a[aria-label="Home"]\');'
            b'if(h){h.click();return;}location.assign("/");}'
            b'function mount(){if(document.getElementById("creanova-beszel-home"))return;'
            b'var h=document.querySelector(\'a[aria-label="Home"]\');'
            b'if(!h||!h.parentElement)return;var a=document.createElement("a");'
            b'a.id="creanova-beszel-home";a.href=h.getAttribute("href")||"/";'
            b'a.setAttribute("aria-label","All Systems");a.textContent="All Systems";'
            b'a.style.cssText="display:inline-flex;align-items:center;margin-inline-end:0.75rem;'
            b'font-size:0.875rem;font-weight:500;opacity:0.9;text-decoration:none;color:inherit;'
            b'cursor:pointer;white-space:nowrap";a.addEventListener("click",goHome);'
            b'h.parentElement.insertBefore(a,h.nextSibling);}setInterval(mount,400);})();</script>'
        )
        content = content.replace(b'</body>', inject + b'</body>', 1)

    return Response(
        content=content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get('content-type'),
    )


@router.api_route(
    '/api/{full_path:path}',
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
)
async def proxy_api(
    full_path: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    path = f'/api/{full_path}'

    if (
        path.startswith('/api/auth/')
        or path.startswith('/api/credits/')
        or path.startswith('/api/admin/')
        or path.startswith('/api/infra/')
    ):
        raise HTTPException(status_code=404, detail='Not found')

    user: AuthUser | None = None
    if not _is_public(path):
        try:
            session = require_session(request, settings, SessionManager(settings))
        except HTTPException:
            raise
        row = db.query(User).filter(User.id == session.user_id).one_or_none()
        if row is None or not row.is_active:
            raise HTTPException(status_code=401, detail='User not found or disabled')
        user = to_auth_user(row)

    assert user is not None or _is_public(path)

    # Per-user opaque blobs for settings / secrets / profiles.
    blob_kind = _blob_kind_for_path(path) if user is not None else None
    if blob_kind and user is not None:
        # Only intercept collection-level reads/writes for secrets/profiles;
        # nested paths still forward but we keep ownership via cookie gate.
        collection_only = path in (
            '/api/settings',
            '/api/settings/secrets',
            '/api/profiles',
        )
        if collection_only and request.method == 'GET':
            blob = _get_blob(db, user.id, blob_kind)
            if blob is not None:
                return Response(
                    content=json.dumps(blob),
                    media_type='application/json',
                    status_code=200,
                )
            resp = await _forward(request, settings)
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.body)
                    _put_blob(db, user.id, blob_kind, data)
                except Exception:
                    pass
            return resp
        if collection_only and request.method in ('PUT', 'POST', 'PATCH'):
            body = await request.body()
            try:
                data = json.loads(body.decode('utf-8') or '{}')
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail='Invalid JSON') from exc
            _put_blob(db, user.id, blob_kind, data)
            return await _forward(request, settings, body=body)

    # Conversation ownership + credits
    if user is not None and path.startswith('/api/conversations'):
        cid = _extract_conversation_id(path)
        allowed = list_user_conversation_ids(db, user.id)

        if cid and request.method != 'POST':
            if cid not in allowed:
                row = (
                    db.query(UserConversation)
                    .filter(UserConversation.conversation_id == cid)
                    .one_or_none()
                )
                if row is None:
                    try:
                        claim_conversation(db, user.id, cid)
                        allowed.add(cid)
                    except PermissionError as exc:
                        raise HTTPException(status_code=403, detail=str(exc)) from exc
                elif row.user_id != user.id:
                    raise HTTPException(
                        status_code=403, detail='Conversation forbidden'
                    )

        if request.method == 'POST':
            chargeable, charge_cid, cost_key = _is_chargeable_conversation_post(path)
            reserved_run_id: str | None = None
            reserved_cost = 0.0

            if chargeable and cost_key:
                reserved_cost = (
                    settings.credit_cost_per_conversation
                    if cost_key == 'conversation'
                    else settings.credit_cost_per_run
                )
                reserved_run_id = (
                    f'create:{uuid.uuid4()}'
                    if cost_key == 'conversation'
                    else f'run:{charge_cid}:{uuid.uuid4()}'
                )
                try:
                    charge_credits(
                        db,
                        user_id=user.id,
                        cost=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                        usage_type=(
                            'conversation_create'
                            if cost_key == 'conversation'
                            else 'llm_run'
                        ),
                    )
                except InsufficientCredits as exc:
                    raise_http_for_credits(exc)

            if path.rstrip('/') == '/api/conversations':
                resp = await _forward(request, settings)
                if 200 <= resp.status_code < 300:
                    try:
                        data = json.loads(resp.body)
                        new_id = data.get('id') or data.get('conversation_id')
                        if new_id:
                            from storage.conversations import (
                                touch_conversation,
                                upsert_conversation_tool,
                            )

                            title = data.get('title')
                            touch_conversation(
                                db,
                                conversation_id=str(new_id),
                                user_id=user.id,
                                title=title if isinstance(title, str) else None,
                                llm_model=(
                                    data.get('model')
                                    if isinstance(data.get('model'), str)
                                    else None
                                ),
                            )
                            # Record tools hinted in create response / agent config.
                            tools = data.get('tools') or data.get('enabled_tools') or []
                            if isinstance(tools, list):
                                for t in tools:
                                    if isinstance(t, str):
                                        upsert_conversation_tool(
                                            db,
                                            conversation_id=str(new_id),
                                            user_id=user.id,
                                            tool_kind='builtin',
                                            tool_name=t,
                                        )
                                    elif isinstance(t, dict) and t.get('name'):
                                        upsert_conversation_tool(
                                            db,
                                            conversation_id=str(new_id),
                                            user_id=user.id,
                                            tool_kind=str(t.get('kind') or 'builtin'),
                                            tool_name=str(t['name']),
                                            tool_version=(
                                                str(t['version'])
                                                if t.get('version')
                                                else None
                                            ),
                                        )
                    except Exception:
                        pass
                elif reserved_cost > 0 and reserved_run_id:
                    refund_credits(
                        db,
                        user_id=user.id,
                        amount=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                    )
                return resp

            if chargeable and cost_key == 'run':
                resp = await _forward(request, settings)
                if (
                    not (200 <= resp.status_code < 300)
                    and reserved_cost > 0
                    and reserved_run_id
                ):
                    refund_credits(
                        db,
                        user_id=user.id,
                        amount=reserved_cost,
                        conversation_id=charge_cid,
                        run_id=reserved_run_id,
                    )
                return resp

        if (
            path.rstrip('/')
            in (
                '/api/conversations/search',
                '/api/conversations',
            )
            and request.method == 'GET'
        ):
            resp = await _forward(request, settings)
            if resp.status_code == 200:
                try:
                    data = json.loads(resp.body)
                    filtered = _filter_conversation_page(data, allowed)
                    return Response(
                        content=json.dumps(filtered),
                        status_code=200,
                        media_type='application/json',
                    )
                except Exception:
                    return resp
            return resp

        if path.endswith('/batch') and request.method == 'POST':
            body = await request.body()
            try:
                payload = json.loads(body.decode('utf-8') or '[]')
            except json.JSONDecodeError:
                payload = []
            if isinstance(payload, list):
                payload = [x for x in payload if str(x) in allowed]
                body = json.dumps(payload).encode('utf-8')
            return await _forward(request, settings, body=body)

    return await _forward(request, settings)
