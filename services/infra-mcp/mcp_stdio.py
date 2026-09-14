"""MCP stdio server: expose infra / VMS tools to Creanova agent-server.

Run (from agent-canvas container)::

    uv run --with httpx --with mcp python /opt/infra-mcp/mcp_stdio.py

Env:
  GATEWAY_URL          default http://local-gateway:18110
  INFRA_AGENT_TOKEN    preferred auth (exported by canvas entrypoint)
  INFRA_TOKEN_FILE     fallback path to token file
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://local-gateway:18110').rstrip('/')
DEFAULT_TOKEN_FILES = (
    os.environ.get('INFRA_TOKEN_FILE', '').strip(),
    '/home/openhands/.openhands/agent-canvas/infra-agent-token.txt',
    '/home/openhands/.openhands/infra-agent-token.txt',
)

mcp = FastMCP('creanova-infra')


def _auth_headers() -> dict[str, str]:
    token = os.environ.get('INFRA_AGENT_TOKEN', '').strip()
    if not token:
        for path in DEFAULT_TOKEN_FILES:
            if not path:
                continue
            try:
                with open(path, encoding='utf-8') as f:
                    token = f.read().strip()
            except OSError:
                continue
            if token:
                break
    if not token:
        raise RuntimeError('INFRA_AGENT_TOKEN missing (env or infra-agent-token.txt)')
    return {'X-Creanova-Infra-Token': token}


async def _get(path: str, params: dict[str, Any] | None = None) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f'{GATEWAY_URL}{path}',
            headers=_auth_headers(),
            params=params or {},
        )
    if r.status_code >= 400:
        return json.dumps(
            {'error': r.status_code, 'detail': r.text}, ensure_ascii=False
        )
    try:
        return json.dumps(r.json(), ensure_ascii=False)
    except json.JSONDecodeError:
        return r.text


async def _post(path: str, body: dict[str, Any], timeout: float = 120.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f'{GATEWAY_URL}{path}',
            headers={**_auth_headers(), 'Content-Type': 'application/json'},
            json=body,
        )
    if r.status_code >= 400:
        return json.dumps(
            {'error': r.status_code, 'detail': r.text}, ensure_ascii=False
        )
    try:
        return json.dumps(r.json(), ensure_ascii=False)
    except json.JSONDecodeError:
        return r.text


@mcp.tool()
async def vms_summary(days: int = 7, module: str | None = None) -> str:
    """VMS event counts by module/event_type for the last N days.

    Use for questions like how many vehicles/plates/alerts today or recently.
    module: FACE | PLATE | ZONE | ANOMALY | FIRE | FOOTFALL | PPE | THERMAL | HUB.
    For hôm nay / today + xe / phương tiện / biển số use days=1 and module=PLATE.
    Do not write SQL.
    """
    params: dict[str, Any] = {'days': days}
    if module:
        params['module'] = module
    return await _get('/api/infra/analytics/summary', params)


@mcp.tool()
async def vms_top_cameras(
    days: int = 30,
    module: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> str:
    """Top cameras by event count (climbing / fire / plates / etc.)."""
    params: dict[str, Any] = {'days': days, 'limit': limit}
    if module:
        params['module'] = module
    if event_type:
        params['event_type'] = event_type
    return await _get('/api/infra/analytics/top-cameras', params)


@mcp.tool()
async def vms_search_plate(q: str, days: int = 180, limit: int = 50) -> str:
    """Find license-plate sightings. Pass the plate text only."""
    return await _get(
        '/api/infra/analytics/search-plate',
        {'q': q, 'days': days, 'limit': limit},
    )


@mcp.tool()
async def vms_search_person(q: str, days: int = 90, limit: int = 50) -> str:
    """Find face/zone events matching a person name."""
    return await _get(
        '/api/infra/analytics/search-person',
        {'q': q, 'days': days, 'limit': limit},
    )


@mcp.tool()
async def vms_daily(days: int = 30, module: str | None = None) -> str:
    """Daily trend counts (pre-aggregated mart)."""
    params: dict[str, Any] = {'days': days}
    if module:
        params['module'] = module
    return await _get('/api/infra/analytics/daily', params)


@mcp.tool()
async def infra_resolve_server(q: str, limit: int = 10) -> str:
    """Resolve a host by IP, name, tag, or last IPv4 octet.

    On \"ssh vào 250\" call with q=\"250\", confirm name/IP/user/id in one line,
    then STOP. Do not invent follow-up commands. Only infra_run after the user
    gives an explicit command. Prefer this over the local ssh binary.
    """
    return await _get('/api/infra/servers/resolve', {'q': q, 'limit': limit})


@mcp.tool()
async def infra_run(
    server_id: str,
    command: str,
    confirm_destructive: bool = False,
    timeout_sec: int = 120,
) -> str:
    """Run a shell command on a resolved infra host via gateway SSH credentials.

    Never use local `ssh user@host`. Pass server_id UUID from infra_resolve_server
    (never a last octet like \"250\"). Only call when the user explicitly gave the
    command — do not invent ip/sudo/nginx/ls. Do not narrate or tutorialize the
    stdout unless asked. Destructive commands need confirm_destructive=true after
    the user agrees.
    """
    return await _post(
        f'/api/infra/servers/{server_id}/run',
        {
            'command': command,
            'confirm_destructive': confirm_destructive,
            'timeout_sec': timeout_sec,
        },
        timeout=float(timeout_sec) + 30.0,
    )


def main() -> None:
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
