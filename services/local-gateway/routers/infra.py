from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from auth.deps import require_admin, require_session
from auth.session import SessionManager
from config import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException
from infra.access import user_has_server_access
from infra.audit import write_audit
from infra.commands import CommandDenied, render_command
from infra.crypto import CryptoError, decrypt_text, encrypt_text
from infra.gpu import is_nvidia_smi_missing, parse_nvidia_smi_csv
from infra.services import parse_systemctl_list_units
from infra.ssh_client import SSHError, run_ssh
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from storage.models import (
    InfraGpuMetric,
    InfraServer,
    InfraServerAccessGrant,
    InfraServerCredential,
    InfraServiceSnapshot,
    User,
    get_db,
)
from storage.users import AuthUser, to_auth_user

router = APIRouter(tags=['infra'])

_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{0,127}$')

# Simple in-process single-flight cache for GPU (also backed by DB freshness).
_gpu_cache: dict[str, tuple[datetime, list[dict[str, Any]]]] = {}


class ServerCreate(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str
    auth_type: str = 'key'
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    credential: str | None = None
    passphrase: str | None = None


class ServerUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    port: int | None = None
    username: str | None = None
    auth_type: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class CredentialSet(BaseModel):
    credential: str
    passphrase: str | None = None
    auth_type: str | None = None


class GrantCreate(BaseModel):
    user_id: str
    permission: str = 'read'


class ServiceAction(BaseModel):
    action: str  # restart | stop


def _current_user(
    request_user: AuthUser,
    db: Session,
) -> User:
    row = db.query(User).filter(User.id == request_user.id).one_or_none()
    if row is None or not row.is_active:
        raise HTTPException(status_code=401, detail='User not found or disabled')
    return row


from fastapi import Request  # noqa: E402


def get_auth_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthUser:
    session = require_session(request, settings, SessionManager(settings))
    row = db.query(User).filter(User.id == session.user_id).one_or_none()
    if row is None or not row.is_active:
        raise HTTPException(status_code=401, detail='User not found or disabled')
    return to_auth_user(row)


def _server_public(server: InfraServer) -> dict[str, Any]:
    return {
        'id': str(server.id),
        'name': server.name,
        'hostname': server.hostname,
        'port': server.port,
        'username': server.username,
        'auth_type': server.auth_type,
        'description': server.description,
        'tags': server.tags or [],
        'host_key_fingerprint': server.host_key_fingerprint,
        'is_active': server.is_active,
        'last_seen_at': server.last_seen_at.isoformat()
        if server.last_seen_at
        else None,
        'last_error': server.last_error,
        'created_at': server.created_at.isoformat() if server.created_at else None,
        # NEVER include credential / ciphertext
    }


async def _run_on_server(
    db: Session,
    server: InfraServer,
    command: str,
) -> Any:
    cred = (
        db.query(InfraServerCredential)
        .filter(InfraServerCredential.server_id == server.id)
        .one_or_none()
    )
    if cred is None:
        raise HTTPException(status_code=400, detail='Server has no credentials')
    try:
        secret = decrypt_text(cred.ciphertext)
        passphrase = (
            decrypt_text(cred.passphrase_ciphertext)
            if cred.passphrase_ciphertext
            else None
        )
    except CryptoError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return await run_ssh(
        hostname=server.hostname,
        port=server.port,
        username=server.username,
        auth_type=server.auth_type,
        secret=secret,
        passphrase=passphrase,
        command=command,
    )


@router.get('/api/infra/servers')
async def list_servers(
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    u = _current_user(user, db)
    q = db.query(InfraServer)
    if not u.is_admin:
        granted = {
            str(g.server_id)
            for g in db.query(InfraServerAccessGrant)
            .filter(InfraServerAccessGrant.user_id == u.id)
            .all()
        }
        if not granted:
            return []
        q = q.filter(InfraServer.id.in_(granted))
    return [_server_public(s) for s in q.order_by(InfraServer.name).all()]


@router.post('/api/infra/servers')
async def create_server(
    body: ServerCreate,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not _NAME_RE.match(body.name):
        raise HTTPException(status_code=400, detail='Invalid server name')
    if body.auth_type not in ('key', 'password', 'agent'):
        raise HTTPException(status_code=400, detail='Invalid auth_type')
    if db.query(InfraServer).filter(InfraServer.name == body.name).one_or_none():
        raise HTTPException(status_code=409, detail='Server name already exists')
    server = InfraServer(
        id=str(uuid4()),
        name=body.name,
        hostname=body.hostname,
        port=body.port,
        username=body.username,
        auth_type=body.auth_type,
        description=body.description,
        tags=body.tags,
        created_by=user.id,
    )
    db.add(server)
    db.flush()
    if body.credential:
        ct, kid = encrypt_text(body.credential)
        ppt = encrypt_text(body.passphrase)[0] if body.passphrase else None
        db.add(
            InfraServerCredential(
                server_id=server.id,
                ciphertext=ct,
                key_id=kid,
                passphrase_ciphertext=ppt,
                updated_by=user.id,
            )
        )
    write_audit(
        db,
        actor_user_id=user.id,
        action='server.create',
        success=True,
        server_id=str(server.id),
        server_name=server.name,
    )
    db.refresh(server)
    return _server_public(server)


@router.patch('/api/infra/servers/{server_id}')
async def update_server(
    server_id: str,
    body: ServerUpdate,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    for field in (
        'name',
        'hostname',
        'port',
        'username',
        'auth_type',
        'description',
        'tags',
        'is_active',
    ):
        val = getattr(body, field)
        if val is not None:
            setattr(server, field, val)
    server.row_version = int(server.row_version) + 1
    write_audit(
        db,
        actor_user_id=user.id,
        action='server.update',
        success=True,
        server_id=str(server.id),
        server_name=server.name,
    )
    db.commit()
    db.refresh(server)
    return _server_public(server)


@router.delete('/api/infra/servers/{server_id}')
async def delete_server(
    server_id: str,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    name = server.name
    db.delete(server)
    write_audit(
        db,
        actor_user_id=user.id,
        action='server.delete',
        success=True,
        server_id=server_id,
        server_name=name,
    )
    return {'ok': True}


@router.post('/api/infra/servers/{server_id}/credentials')
async def set_credentials(
    server_id: str,
    body: CredentialSet,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    if body.auth_type:
        server.auth_type = body.auth_type
    ct, kid = encrypt_text(body.credential)
    ppt = encrypt_text(body.passphrase)[0] if body.passphrase else None
    row = (
        db.query(InfraServerCredential)
        .filter(InfraServerCredential.server_id == server_id)
        .one_or_none()
    )
    if row is None:
        db.add(
            InfraServerCredential(
                server_id=server_id,
                ciphertext=ct,
                key_id=kid,
                passphrase_ciphertext=ppt,
                updated_by=user.id,
            )
        )
    else:
        row.ciphertext = ct
        row.key_id = kid
        row.passphrase_ciphertext = ppt
        row.updated_by = user.id
    write_audit(
        db,
        actor_user_id=user.id,
        action='credential.set',
        success=True,
        server_id=server_id,
        server_name=server.name,
    )
    return {'ok': True}


@router.post('/api/infra/servers/{server_id}/test')
async def test_connection(
    server_id: str,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    try:
        cmd = render_command('echo_ok')
        result = await _run_on_server(db, server, cmd)
        ok = result.exit_code == 0 and 'ok' in (result.stdout or '')
        server.last_seen_at = datetime.now(timezone.utc) if ok else server.last_seen_at
        server.last_error = None if ok else (result.stderr or result.stdout)[:500]
        write_audit(
            db,
            actor_user_id=user.id,
            action='connection.test',
            success=ok,
            server_id=server_id,
            server_name=server.name,
            command_id='echo_ok',
            command_rendered=cmd,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            error_excerpt=None if ok else result.stderr,
        )
        db.commit()
        return {
            'ok': ok,
            'exit_code': result.exit_code,
            'stdout': result.stdout.strip(),
            'duration_ms': result.duration_ms,
        }
    except (SSHError, CommandDenied, HTTPException) as exc:
        msg = str(exc)
        server.last_error = msg[:500]
        write_audit(
            db,
            actor_user_id=user.id,
            action='connection.test',
            success=False,
            server_id=server_id,
            server_name=server.name,
            command_id='echo_ok',
            error_excerpt=msg,
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=msg) from exc


@router.get('/api/infra/servers/{server_id}/gpu')
async def get_gpu(
    server_id: str,
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    u = _current_user(user, db)
    if not user_has_server_access(db, user=u, server_id=server_id, required='read'):
        write_audit(
            db,
            actor_user_id=user.id,
            action='access.denied',
            success=False,
            server_id=server_id,
            error_excerpt='gpu.query denied',
        )
        raise HTTPException(status_code=403, detail='Forbidden')
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None or not server.is_active:
        raise HTTPException(status_code=404, detail='Server not found')

    cached = _gpu_cache.get(server_id)
    if cached and datetime.now(timezone.utc) - cached[0] < timedelta(seconds=5):
        return {
            'server_id': server_id,
            'gpus': cached[1],
            'cached': True,
            'reason': None,
        }

    fresh = (
        db.query(InfraGpuMetric)
        .filter(
            InfraGpuMetric.server_id == server_id,
            InfraGpuMetric.collected_at
            > datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        .order_by(InfraGpuMetric.collected_at.desc())
        .all()
    )
    if fresh:
        by_idx: dict[int, Any] = {}
        for row in fresh:
            by_idx.setdefault(
                row.gpu_index,
                {
                    'gpu_index': row.gpu_index,
                    'gpu_uuid': row.gpu_uuid,
                    'name': row.name,
                    'mem_total_mb': row.mem_total_mb,
                    'mem_used_mb': row.mem_used_mb,
                    'util_gpu_pct': row.util_gpu_pct,
                    'util_mem_pct': row.util_mem_pct,
                    'temp_c': row.temp_c,
                    'power_w': float(row.power_w) if row.power_w is not None else None,
                    'collected_at': row.collected_at.isoformat(),
                },
            )
        gpus = list(by_idx.values())
        _gpu_cache[server_id] = (datetime.now(timezone.utc), gpus)
        return {'server_id': server_id, 'gpus': gpus, 'cached': True, 'reason': None}

    try:
        cmd = render_command('gpu_query')
        result = await _run_on_server(db, server, cmd)
    except (SSHError, HTTPException) as exc:
        write_audit(
            db,
            actor_user_id=user.id,
            action='gpu.query',
            success=False,
            server_id=server_id,
            server_name=server.name,
            command_id='gpu_query',
            error_excerpt=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if is_nvidia_smi_missing(result.stdout, result.stderr, result.exit_code):
        write_audit(
            db,
            actor_user_id=user.id,
            action='gpu.query',
            success=True,
            server_id=server_id,
            server_name=server.name,
            command_id='gpu_query',
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
        )
        return {
            'server_id': server_id,
            'gpus': [],
            'cached': False,
            'reason': 'nvidia-smi not available',
        }

    parsed = parse_nvidia_smi_csv(result.stdout)
    gpus_out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for g in parsed:
        row = InfraGpuMetric(
            server_id=server_id,
            gpu_index=g.gpu_index,
            gpu_uuid=g.gpu_uuid,
            name=g.name,
            mem_total_mb=g.mem_total_mb,
            mem_used_mb=g.mem_used_mb,
            util_gpu_pct=g.util_gpu_pct,
            util_mem_pct=g.util_mem_pct,
            temp_c=g.temp_c,
            power_w=g.power_w,
            parse_error=g.parse_error,
            collected_at=now,
            collected_by=user.id,
        )
        db.add(row)
        gpus_out.append(
            {
                'gpu_index': g.gpu_index,
                'gpu_uuid': g.gpu_uuid,
                'name': g.name,
                'mem_total_mb': g.mem_total_mb,
                'mem_used_mb': g.mem_used_mb,
                'util_gpu_pct': g.util_gpu_pct,
                'util_mem_pct': g.util_mem_pct,
                'temp_c': g.temp_c,
                'power_w': float(g.power_w) if g.power_w is not None else None,
                'parse_error': g.parse_error,
                'collected_at': now.isoformat(),
            }
        )
    write_audit(
        db,
        actor_user_id=user.id,
        action='gpu.query',
        success=True,
        server_id=server_id,
        server_name=server.name,
        command_id='gpu_query',
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )
    _gpu_cache[server_id] = (now, gpus_out)
    return {'server_id': server_id, 'gpus': gpus_out, 'cached': False, 'reason': None}


@router.get('/api/infra/servers/{server_id}/services')
async def list_services(
    server_id: str,
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    u = _current_user(user, db)
    if not user_has_server_access(db, user=u, server_id=server_id, required='read'):
        raise HTTPException(status_code=403, detail='Forbidden')
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    try:
        cmd = render_command('service_list')
        result = await _run_on_server(db, server, cmd)
    except (SSHError, HTTPException) as exc:
        write_audit(
            db,
            actor_user_id=user.id,
            action='service.list',
            success=False,
            server_id=server_id,
            server_name=server.name,
            error_excerpt=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    services = parse_systemctl_list_units(result.stdout)
    now = datetime.now(timezone.utc)
    out = []
    for s in services:
        db.add(
            InfraServiceSnapshot(
                server_id=server_id,
                unit_name=s.unit_name,
                load_state=s.load_state,
                active_state=s.active_state,
                sub_state=s.sub_state,
                description=s.description,
                collected_at=now,
            )
        )
        out.append(
            {
                'unit_name': s.unit_name,
                'load_state': s.load_state,
                'active_state': s.active_state,
                'sub_state': s.sub_state,
                'description': s.description,
            }
        )
    write_audit(
        db,
        actor_user_id=user.id,
        action='service.list',
        success=True,
        server_id=server_id,
        server_name=server.name,
        command_id='service_list',
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )
    return {'server_id': server_id, 'services': out}


@router.post('/api/infra/servers/{server_id}/services/{unit}/action')
async def service_action(
    server_id: str,
    unit: str,
    body: ServiceAction,
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    u = _current_user(user, db)
    if not user_has_server_access(db, user=u, server_id=server_id, required='operate'):
        write_audit(
            db,
            actor_user_id=user.id,
            action='access.denied',
            success=False,
            server_id=server_id,
            error_excerpt=f'service.{body.action} denied',
        )
        raise HTTPException(status_code=403, detail='Forbidden')
    if body.action not in ('restart', 'stop'):
        raise HTTPException(status_code=400, detail='action must be restart|stop')
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    command_id = f'service_{body.action}'
    try:
        cmd = render_command(command_id, unit=unit)
        result = await _run_on_server(db, server, cmd)
    except (SSHError, CommandDenied, HTTPException) as exc:
        write_audit(
            db,
            actor_user_id=user.id,
            action=f'service.{body.action}',
            success=False,
            server_id=server_id,
            server_name=server.name,
            command_id=command_id,
            error_excerpt=str(exc),
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ok = result.exit_code == 0
    write_audit(
        db,
        actor_user_id=user.id,
        action=f'service.{body.action}',
        success=ok,
        server_id=server_id,
        server_name=server.name,
        command_id=command_id,
        command_rendered=cmd,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        error_excerpt=None if ok else (result.stderr or result.stdout),
    )
    return {
        'ok': ok,
        'exit_code': result.exit_code,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'duration_ms': result.duration_ms,
    }


@router.get('/api/infra/audit')
async def list_audit(
    server_id: str | None = None,
    limit: int = 50,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    from storage.models import InfraAuditLog

    q = db.query(InfraAuditLog).order_by(InfraAuditLog.created_at.desc())
    if server_id:
        q = q.filter(InfraAuditLog.server_id == server_id)
    rows = q.limit(min(limit, 200)).all()
    return [
        {
            'id': r.id,
            'actor_user_id': r.actor_user_id,
            'actor_kind': r.actor_kind,
            'server_id': str(r.server_id) if r.server_id else None,
            'server_name': r.server_name,
            'action': r.action,
            'command_id': r.command_id,
            'exit_code': r.exit_code,
            'success': r.success,
            'duration_ms': r.duration_ms,
            'error_excerpt': r.error_excerpt,
            'created_at': r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


_BESZEL_AGENT_DEPLOY_SCRIPT = r"""
set -eu
TOKEN="$1"; KEY="$2"; PORT="${3:-45876}"

# Detect Docker availability
HAS_DOCKER=0
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && HAS_DOCKER=1

if [ "$HAS_DOCKER" = "1" ]; then
    docker rm -f beszel-agent 2>/dev/null || true
    docker run -d \
        --name beszel-agent \
        --network host \
        --restart unless-stopped \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        -e TOKEN="$TOKEN" \
        -e KEY="$KEY" \
        -e LISTEN="$PORT" \
        henrygd/beszel-agent:latest
    echo "beszel-agent: deployed via Docker on port $PORT"
    exit 0
fi

# Fallback: binary install (Linux amd64/arm64)
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64)  GOARCH=amd64 ;;
    aarch64|arm64) GOARCH=arm64 ;;
    *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# Try to find latest release URL
RELEASE_URL="https://github.com/henrygd/beszel/releases/latest/download/beszel-agent_Linux_${GOARCH}.tar.gz"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$RELEASE_URL" -o "$TMPDIR/beszel-agent.tar.gz"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TMPDIR/beszel-agent.tar.gz" "$RELEASE_URL"
else
    echo "beszel-agent: need curl or wget" >&2; exit 1
fi

tar -xzf "$TMPDIR/beszel-agent.tar.gz" -C "$TMPDIR"
install -m 755 "$TMPDIR/beszel-agent" /usr/local/bin/beszel-agent

# Write systemd unit if available, else run in background via nohup
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
    cat >/etc/systemd/system/beszel-agent.service <<EOF2
[Unit]
Description=Beszel Agent
After=network.target

[Service]
ExecStart=/usr/local/bin/beszel-agent
Restart=always
Environment=TOKEN=$TOKEN
Environment=KEY=$KEY
Environment=LISTEN=$PORT

[Install]
WantedBy=multi-user.target
EOF2
    systemctl daemon-reload
    systemctl enable --now beszel-agent
    echo "beszel-agent: deployed via systemd on port $PORT"
else
    nohup /usr/local/bin/beszel-agent \
        TOKEN="$TOKEN" KEY="$KEY" LISTEN="$PORT" \
        >/tmp/beszel-agent.log 2>&1 &
    echo "beszel-agent: deployed via nohup (pid $!) on port $PORT"
fi
"""


@router.post('/api/infra/servers/{server_id}/deploy-beszel')
async def deploy_beszel_agent(
    server_id: str,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """SSH into the server and install/start beszel-agent using hub token + pubkey."""
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')

    # Load Beszel credentials from the shared path written by beszel-bootstrap.
    beszel_shared = getattr(settings, 'beszel_shared_path', '/beszel_shared')
    token_path = f'{beszel_shared}/token'
    key_path = f'{beszel_shared}/id_ed25519.pub'
    try:
        with open(token_path) as f:
            hub_token = f.read().strip()
        with open(key_path) as f:
            hub_pubkey = f.read().strip()
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f'Beszel credentials not ready ({exc}). Run docker compose up first.',
        ) from exc

    agent_port = getattr(settings, 'beszel_agent_port', 45876)

    # Escape arguments for safe shell injection (no special chars expected in token/key).
    def _sq(s: str) -> str:
        return "'" + s.replace("'", "'\\''") + "'"

    script = (
        f"sh -s {_sq(hub_token)} {_sq(hub_pubkey)} {agent_port} <<'__DEPLOY__'\n"
        + _BESZEL_AGENT_DEPLOY_SCRIPT
        + '\n__DEPLOY__'
    )

    try:
        result = await _run_on_server(db, server, script)
    except (SSHError, HTTPException) as exc:
        write_audit(
            db,
            actor_user_id=user.id,
            action='beszel.deploy',
            success=False,
            server_id=server_id,
            server_name=server.name,
            error_excerpt=str(exc)[:500],
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ok = result.exit_code == 0
    write_audit(
        db,
        actor_user_id=user.id,
        action='beszel.deploy',
        success=ok,
        server_id=server_id,
        server_name=server.name,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        error_excerpt=None if ok else (result.stderr or result.stdout)[:500],
    )
    db.commit()

    return {
        'ok': ok,
        'exit_code': result.exit_code,
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'duration_ms': result.duration_ms,
    }


@router.post('/api/infra/servers/{server_id}/grants')
async def create_grant(
    server_id: str,
    body: GrantCreate,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if body.permission not in ('read', 'operate'):
        raise HTTPException(status_code=400, detail='permission must be read|operate')
    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None:
        raise HTTPException(status_code=404, detail='Server not found')
    target = db.query(User).filter(User.id == body.user_id).one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail='User not found')
    existing = (
        db.query(InfraServerAccessGrant)
        .filter(
            InfraServerAccessGrant.server_id == server_id,
            InfraServerAccessGrant.user_id == body.user_id,
        )
        .one_or_none()
    )
    if existing:
        existing.permission = body.permission
        existing.granted_by = user.id
    else:
        db.add(
            InfraServerAccessGrant(
                server_id=server_id,
                user_id=body.user_id,
                permission=body.permission,
                granted_by=user.id,
            )
        )
    db.commit()
    return {'ok': True, 'user_id': body.user_id, 'permission': body.permission}
