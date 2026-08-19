"""Register / rename Beszel systems from InfraServer rows (live, not only bootstrap)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from config import Settings
from storage.models import InfraServer

logger = logging.getLogger(__name__)


def listen_port_for_host(hostname: str, base: int) -> int:
    """Stable unique listen port from the last IPv4 octet (45000+191 → 45191)."""
    last = hostname.rsplit('.', 1)[-1]
    if last.isdigit():
        octet = int(last)
        if 0 <= octet <= 255:
            return base + octet
    return base + (sum(ord(c) for c in hostname) % 500)


def _pick_port(
    hostname: str,
    base: int,
    used: set[int],
    current: str | int | None,
) -> int:
    if current not in (None, '', '45876'):
        try:
            cur = int(current)
            if 1024 <= cur <= 65535:
                return cur
        except (TypeError, ValueError):
            pass
    candidate = listen_port_for_host(hostname, base)
    while candidate in used:
        candidate += 1
        if candidate > 65535:
            raise RuntimeError('no free Beszel agent port')
    return candidate


async def _login(settings: Settings) -> tuple[str, str]:
    """Return (pocketbase_token, user_id)."""
    url = (
        f'{settings.beszel_hub_url.rstrip("/")}'
        '/api/collections/users/auth-with-password'
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json={
                'identity': settings.beszel_user_email,
                'password': settings.beszel_user_password,
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f'Beszel auth failed: {resp.status_code} {resp.text[:200]}')
    body = resp.json()
    token = body.get('token') or ''
    user_id = (body.get('record') or {}).get('id') or ''
    if not token or not user_id:
        raise RuntimeError('Beszel auth missing token or user id')
    return token, user_id


async def _fingerprint_token(
    client: httpx.AsyncClient,
    base: str,
    headers: dict[str, str],
    system_id: str,
) -> str:
    resp = await client.get(
        f'{base}/api/collections/fingerprints/records',
        headers=headers,
        params={'filter': f"(system='{system_id}')", 'perPage': 1},
    )
    if resp.status_code != 200:
        return ''
    items = resp.json().get('items') or []
    if not items:
        return ''
    return str(items[0].get('token') or '')


async def upsert_system(server: InfraServer, settings: Settings) -> tuple[str, int]:
    """Create or patch Beszel system. Returns (agent_token, listen_port)."""
    display = (server.name or server.hostname).strip()
    host = server.hostname.strip()
    pb, user_id = await _login(settings)
    headers = {'Authorization': pb}
    base = settings.beszel_hub_url.rstrip('/')
    port_base = settings.beszel_agent_port_base

    async with httpx.AsyncClient(timeout=15) as client:
        listed = await client.get(
            f'{base}/api/collections/systems/records',
            headers=headers,
            params={'perPage': 200},
        )
        if listed.status_code != 200:
            raise RuntimeError(f'Beszel list systems failed: {listed.status_code}')
        items: list[dict[str, Any]] = listed.json().get('items') or []
        existing = next((x for x in items if x.get('host') == host), None)
        used = set()
        for x in items:
            if existing is not None and x.get('id') == existing.get('id'):
                continue
            try:
                used.add(int(x.get('port') or 0))
            except (TypeError, ValueError):
                pass
        used.discard(0)

        listen = _pick_port(
            host,
            port_base,
            used,
            existing.get('port') if existing else None,
        )

        if existing is not None:
            sys_id = str(existing['id'])
            patched = await client.patch(
                f'{base}/api/collections/systems/records/{sys_id}',
                headers=headers,
                json={'name': display, 'host': host, 'port': str(listen)},
            )
            if patched.status_code != 200:
                raise RuntimeError(
                    f'Beszel patch system failed: {patched.status_code} {patched.text[:300]}'
                )
            token = await _fingerprint_token(client, base, headers, sys_id)
            logger.info('beszel: synced %s as %s port %s', host, display, listen)
            return token, listen

        created = await client.post(
            f'{base}/api/collections/systems/records',
            headers=headers,
            json={
                'name': display,
                'host': host,
                'port': str(listen),
                'status': 'pending',
                'users': [user_id],
            },
        )
        if created.status_code not in (200, 201):
            raise RuntimeError(
                f'Beszel create system failed: {created.status_code} {created.text[:300]}'
            )
        sys_id = str(created.json().get('id') or '')
        agent_token = str(uuid.uuid4())
        fp = await client.post(
            f'{base}/api/collections/fingerprints/records',
            headers=headers,
            json={'system': sys_id, 'token': agent_token},
        )
        if fp.status_code not in (200, 201):
            raise RuntimeError(
                f'Beszel create fingerprint failed: {fp.status_code} {fp.text[:300]}'
            )
        logger.info('beszel: created %s as %s port %s', host, display, listen)
        return agent_token, listen
