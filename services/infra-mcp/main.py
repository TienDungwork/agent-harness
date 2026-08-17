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
        'name': 'infra_service_action',
        'description': 'Restart or stop a systemd unit (operate permission required)',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'server_id': {'type': 'string'},
                'unit': {'type': 'string'},
                'action': {'type': 'string', 'enum': ['restart', 'stop']},
            },
            'required': ['server_id', 'unit', 'action'],
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
    if not cookie:
        raise HTTPException(status_code=401, detail='cookie required')
    headers = {'Cookie': cookie}
    async with httpx.AsyncClient(timeout=30.0) as client:
        if body.name == 'infra_list_servers':
            r = await client.get(f'{GATEWAY_URL}/api/infra/servers', headers=headers)
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
