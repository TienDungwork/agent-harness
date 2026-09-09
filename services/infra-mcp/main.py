"""Minimal Infra MCP HTTP bridge for agent tools (port 18120).

Calls local-gateway /api/infra/* with a session cookie or service token.
For local MVP, pass GATEWAY_COOKIE or login via username/password.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://127.0.0.1:18110').rstrip('/')
HOST = os.environ.get('HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', '18120'))

app = FastAPI(title='Creanova Infra MCP', version='0.1.0')


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = {}
    cookie: str | None = None


TOOLS = [
    {
        'name': 'infra_list_servers',
        'description': 'List servers the current user can access',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'infra_resolve_server',
        'description': (
            'Resolve a host by IP, name, or tag from the InfraServer inventory '
            '(exact-first ranking). Use before ssh/run.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string', 'description': 'IP, hostname, name, or tag'},
                'limit': {'type': 'integer', 'default': 10},
            },
            'required': ['q'],
        },
    },
    {
        'name': 'infra_run',
        'description': (
            'Run a shell command on a server via gateway SSH credentials. '
            'Destructive commands (rm/dd/…) require confirm_destructive=true '
            'after the user explicitly agrees in chat.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'server_id': {'type': 'string'},
                'command': {'type': 'string'},
                'confirm_destructive': {'type': 'boolean', 'default': False},
                'timeout_sec': {'type': 'number', 'default': 120},
            },
            'required': ['server_id', 'command'],
        },
    },
    {
        'name': 'infra_gpu_status',
        'description': 'Query GPU utilization for a server',
        'inputSchema': {
            'type': 'object',
            'properties': {'server_id': {'type': 'string'}},
            'required': ['server_id'],
        },
    },
    {
        'name': 'infra_list_services',
        'description': 'List systemd services on a server',
        'inputSchema': {
            'type': 'object',
            'properties': {'server_id': {'type': 'string'}},
            'required': ['server_id'],
        },
    },
    {
        'name': 'infra_search_pinned_containers',
        'description': (
            'Search containers the user pinned on Beszel monitor '
            '(exact-first by name/host/tag). Use to focus agent work.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {
                    'type': 'string',
                    'description': 'Container name, host, image, or tag',
                },
                'limit': {'type': 'integer', 'default': 20},
                'user_email': {
                    'type': 'string',
                    'description': 'Optional; with infra token, scope to this Creanova user',
                },
            },
            'required': ['q'],
        },
    },
    {
        'name': 'vms_summary',
        'description': (
            'VMS event counts by module/event_type for the last N days. '
            'Use for how many alerts recently. Do not write SQL.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'default': 7},
                'module': {
                    'type': 'string',
                    'description': 'FACE | PLATE | ZONE | ANOMALY | FIRE | FOOTFALL | PPE | THERMAL | HUB',
                },
            },
        },
    },
    {
        'name': 'vms_top_cameras',
        'description': (
            'Top cameras by event count. Use when the user asks which camera '
            'had the most climbing / fire / plates / etc.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'default': 30},
                'module': {'type': 'string'},
                'event_type': {
                    'type': 'string',
                    'description': 'e.g. INTRUSION_DETECTION, HIGH, IN, OUT',
                },
                'limit': {'type': 'integer', 'default': 20},
            },
        },
    },
    {
        'name': 'vms_search_plate',
        'description': 'Find license-plate sightings. Pass the plate text only.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string'},
                'days': {'type': 'integer', 'default': 180},
                'limit': {'type': 'integer', 'default': 50},
            },
            'required': ['q'],
        },
    },
    {
        'name': 'vms_search_person',
        'description': 'Find face/zone events matching a person name.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string'},
                'days': {'type': 'integer', 'default': 90},
                'limit': {'type': 'integer', 'default': 50},
            },
            'required': ['q'],
        },
    },
    {
        'name': 'vms_daily',
        'description': 'Daily trend counts (pre-aggregated).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'days': {'type': 'integer', 'default': 30},
                'module': {'type': 'string'},
            },
        },
    },
]


@app.get('/healthz')
async def healthz() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/tools')
async def list_tools() -> list[dict[str, Any]]:
    return TOOLS


@app.post('/tools/call')
async def call_tool(body: ToolCall) -> Any:
    cookie = body.cookie or os.environ.get('GATEWAY_COOKIE', '')
    token = os.environ.get('INFRA_AGENT_TOKEN', '').strip()
    headers: dict[str, str] = {}
    if cookie:
        headers['Cookie'] = cookie
    if token:
        headers['X-Creanova-Infra-Token'] = token
    if not headers:
        raise HTTPException(
            status_code=401, detail='cookie or INFRA_AGENT_TOKEN required'
        )
    async with httpx.AsyncClient(timeout=120.0) as client:
        if body.name == 'infra_list_servers':
            r = await client.get(f'{GATEWAY_URL}/api/infra/servers', headers=headers)
        elif body.name == 'infra_resolve_server':
            q = body.arguments.get('q', '')
            limit = body.arguments.get('limit', 10)
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/servers/resolve',
                headers=headers,
                params={'q': q, 'limit': limit},
            )
        elif body.name == 'infra_run':
            sid = body.arguments['server_id']
            r = await client.post(
                f'{GATEWAY_URL}/api/infra/servers/{sid}/run',
                headers=headers,
                json={
                    'command': body.arguments['command'],
                    'confirm_destructive': bool(
                        body.arguments.get('confirm_destructive', False)
                    ),
                    'timeout_sec': float(body.arguments.get('timeout_sec', 120)),
                },
            )
        elif body.name == 'infra_gpu_status':
            sid = body.arguments.get('server_id')
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/servers/{sid}/gpu', headers=headers
            )
        elif body.name == 'infra_list_services':
            sid = body.arguments.get('server_id')
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/servers/{sid}/services', headers=headers
            )
        elif body.name == 'infra_service_action':
            sid = body.arguments['server_id']
            unit = body.arguments['unit']
            r = await client.post(
                f'{GATEWAY_URL}/api/infra/servers/{sid}/services/{unit}/action',
                headers=headers,
                json={'action': body.arguments['action']},
            )
        elif body.name == 'infra_search_pinned_containers':
            params: dict[str, Any] = {
                'q': body.arguments.get('q', ''),
                'limit': body.arguments.get('limit', 20),
            }
            if body.arguments.get('user_email'):
                params['user_email'] = body.arguments['user_email']
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/pinned-containers/search',
                headers=headers,
                params=params,
            )
        elif body.name == 'vms_summary':
            params = {'days': body.arguments.get('days', 7)}
            if body.arguments.get('module'):
                params['module'] = body.arguments['module']
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/analytics/summary',
                headers=headers,
                params=params,
            )
        elif body.name == 'vms_top_cameras':
            params = {
                'days': body.arguments.get('days', 30),
                'limit': body.arguments.get('limit', 20),
            }
            if body.arguments.get('module'):
                params['module'] = body.arguments['module']
            if body.arguments.get('event_type'):
                params['event_type'] = body.arguments['event_type']
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/analytics/top-cameras',
                headers=headers,
                params=params,
            )
        elif body.name == 'vms_search_plate':
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/analytics/search-plate',
                headers=headers,
                params={
                    'q': body.arguments.get('q', ''),
                    'days': body.arguments.get('days', 180),
                    'limit': body.arguments.get('limit', 50),
                },
            )
        elif body.name == 'vms_search_person':
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/analytics/search-person',
                headers=headers,
                params={
                    'q': body.arguments.get('q', ''),
                    'days': body.arguments.get('days', 90),
                    'limit': body.arguments.get('limit', 50),
                },
            )
        elif body.name == 'vms_daily':
            params = {'days': body.arguments.get('days', 30)}
            if body.arguments.get('module'):
                params['module'] = body.arguments['module']
            r = await client.get(
                f'{GATEWAY_URL}/api/infra/analytics/daily',
                headers=headers,
                params=params,
            )
        else:
            raise HTTPException(status_code=400, detail=f'unknown tool {body.name}')
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    try:
        return r.json()
    except json.JSONDecodeError:
        return {'raw': r.text}


def main() -> None:
    import uvicorn

    uvicorn.run('main:app', host=HOST, port=PORT, reload=False)


if __name__ == '__main__':
    main()
