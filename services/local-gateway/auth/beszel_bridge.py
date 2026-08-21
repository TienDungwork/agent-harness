"""Resolve gateway User from a Beszel (PocketBase) auth token."""

from __future__ import annotations

import logging

import httpx
from config import Settings
from fastapi import HTTPException
from sqlalchemy.orm import Session
from storage.models import User
from storage.users import AuthUser, to_auth_user

logger = logging.getLogger(__name__)

_BESZEL_TOKEN_HEADER = 'X-Beszel-Token'


def _token_from_request(
    authorization: str | None, beszel_header: str | None
) -> str | None:
    raw = (beszel_header or '').strip()
    if raw:
        return raw
    auth = (authorization or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip() or None
    return None


async def resolve_auth_user_from_beszel(
    *,
    authorization: str | None,
    beszel_header: str | None,
    settings: Settings,
    db: Session,
) -> AuthUser | None:
    """Validate Beszel PB JWT and map email → gateway User.

    Returns None when no Beszel token is present (caller tries other auth).
    Raises 401 when token is present but invalid / email has no gateway user.
    """
    token = _token_from_request(authorization, beszel_header)
    if not token:
        return None

    hub = settings.beszel_hub_url.rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f'{hub}/api/collections/users/auth-refresh',
                headers={'Authorization': token},
            )
    except httpx.HTTPError as exc:
        logger.warning('Beszel auth-refresh failed: %s', exc)
        raise HTTPException(status_code=502, detail='Beszel auth unreachable') from exc

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail='Invalid Beszel token')

    body = resp.json()
    record = body.get('record') or {}
    email = (record.get('email') or '').strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail='Beszel user has no email')

    user = db.query(User).filter(User.email.isnot(None), User.is_active.is_(True)).all()
    match = next(
        (u for u in user if (u.email or '').strip().lower() == email),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=403,
            detail=(
                f'No Creanova user for email {email}. '
                'Log into Agents once or create the user in local-gateway.'
            ),
        )
    return to_auth_user(match)


def beszel_token_header_name() -> str:
    return _BESZEL_TOKEN_HEADER
