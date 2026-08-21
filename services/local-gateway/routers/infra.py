from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from auth.deps import require_admin, require_session
from auth.session import SessionManager
from config import Settings, get_settings
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from infra.access import user_has_server_access
from infra.audit import write_audit
from infra.beszel import clear_system_fingerprint as clear_beszel_fingerprint
from infra.beszel import upsert_system as upsert_beszel_system
from infra.commands import CommandDenied, render_command
from infra.crypto import CryptoError, decrypt_text, encrypt_text
from infra.destructive import destructive_reason, looks_destructive
from infra.gpu import is_nvidia_smi_missing, parse_nvidia_smi_csv
from infra.resolve import rank_servers
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

_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$')
_INFRA_TOKEN_HEADER = 'X-Creanova-Infra-Token'

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


class ServerRunBody(BaseModel):
    command: str = Field(min_length=1, max_length=32_000)
    confirm_destructive: bool = False
    timeout_sec: float = Field(default=120.0, ge=1.0, le=600.0)


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


def _auth_user_from_infra_token(
    request: Request,
    settings: Settings,
    db: Session,
) -> AuthUser | None:
    token = (request.headers.get(_INFRA_TOKEN_HEADER) or '').strip()
    expected = (settings.infra_agent_token or '').strip()
    if not token or not expected or token != expected:
        return None
    admin = (
        db.query(User)
        .filter(User.is_admin.is_(True), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .first()
    )
    if admin is None:
        raise HTTPException(status_code=503, detail='No admin user for infra token')
    return to_auth_user(admin)


def get_auth_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthUser:
    via_token = _auth_user_from_infra_token(request, settings, db)
    if via_token is not None:
        return via_token
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
    timeout: float = 10.0,
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
        timeout=timeout,
    )


def _servers_visible_to(user: User, db: Session):
    q = db.query(InfraServer).filter(InfraServer.is_active.is_(True))
    if not user.is_admin:
        granted = {
            str(g.server_id)
            for g in db.query(InfraServerAccessGrant)
            .filter(InfraServerAccessGrant.user_id == user.id)
            .all()
        }
        if not granted:
            return []
        q = q.filter(InfraServer.id.in_(granted))
    return q.all()


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


@router.get('/api/infra/servers/resolve')
async def resolve_servers(
    q: str,
    limit: int = 10,
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fast host lookup by IP / name / tag (exact-first ranking)."""
    query = (q or '').strip()
    if not query:
        raise HTTPException(status_code=400, detail='q is required')
    limit = max(1, min(int(limit or 10), 50))
    u = _current_user(user, db)
    rows = _servers_visible_to(u, db)
    ranked = rank_servers(query, rows, limit=limit)
    return {
        'query': query,
        'count': len(ranked),
        'items': [
            {
                'id': c.server_id,
                'name': c.name,
                'hostname': c.hostname,
                'port': c.port,
                'username': c.username,
                'tags': list(c.tags),
                'score': c.score,
                'match': c.match,
            }
            for c in ranked
        ],
    }


@router.post('/api/infra/servers/{server_id}/run')
async def run_on_server(
    server_id: str,
    body: ServerRunBody,
    user: AuthUser = Depends(get_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run an arbitrary remote shell command via stored SSH credentials."""
    u = _current_user(user, db)
    if not user_has_server_access(db, user=u, server_id=server_id, required='operate'):
        write_audit(
            db,
            actor_user_id=user.id,
            action='access.denied',
            success=False,
            server_id=server_id,
            error_excerpt='shell.run denied',
        )
        raise HTTPException(status_code=403, detail='Forbidden')

    server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
    if server is None or not server.is_active:
        raise HTTPException(status_code=404, detail='Server not found')

    command = body.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail='command is required')

    if looks_destructive(command) and not body.confirm_destructive:
        reason = destructive_reason(command) or 'destructive command'
        write_audit(
            db,
            actor_user_id=user.id,
            action='shell.run.blocked',
            success=False,
            server_id=server_id,
            server_name=server.name,
            command_rendered=command[:500],
            error_excerpt=reason,
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                'needs_confirmation': True,
                'reason': reason,
                'server_id': server_id,
                'server_name': server.name,
                'hostname': server.hostname,
            },
        )

    try:
        result = await _run_on_server(
            db, server, command, timeout=float(body.timeout_sec)
        )
        ok = result.exit_code == 0
        if ok:
            server.last_seen_at = datetime.now(timezone.utc)
            server.last_error = None
        else:
            server.last_error = (result.stderr or result.stdout or '')[:500]
        write_audit(
            db,
            actor_user_id=user.id,
            action='shell.run',
            success=ok,
            server_id=server_id,
            server_name=server.name,
            command_rendered=command[:2000],
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            error_excerpt=None if ok else (result.stderr or '')[:500],
        )
        db.commit()
        return {
            'ok': ok,
            'server_id': server_id,
            'server_name': server.name,
            'hostname': server.hostname,
            'exit_code': result.exit_code,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration_ms': result.duration_ms,
        }
    except (SSHError, HTTPException) as exc:
        msg = str(exc.detail if isinstance(exc, HTTPException) else exc)
        server.last_error = msg[:500]
        write_audit(
            db,
            actor_user_id=user.id,
            action='shell.run',
            success=False,
            server_id=server_id,
            server_name=server.name,
            command_rendered=command[:2000],
            error_excerpt=msg[:500],
        )
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=msg) from exc


async def _sync_and_maybe_deploy_beszel(
    server_id: str,
    settings: Settings,
    *,
    deploy: bool,
    actor_user_id: str | None = None,
) -> None:
    """Register/rename the host in Beszel; optionally SSH-install the agent."""
    import asyncio

    from storage.models import SessionLocal

    await asyncio.sleep(1)
    if SessionLocal is None:
        return
    db = SessionLocal()
    try:
        server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
        if server is None:
            return
        try:
            await upsert_beszel_system(server, settings)
            write_audit(
                db,
                actor_user_id=actor_user_id,
                action='beszel.sync',
                success=True,
                server_id=str(server.id),
                server_name=server.name,
            )
            db.commit()
        except Exception as exc:
            write_audit(
                db,
                actor_user_id=actor_user_id,
                action='beszel.sync',
                success=False,
                server_id=str(server.id),
                server_name=server.name,
                error_excerpt=str(exc)[:500],
            )
            db.commit()
            if not deploy:
                return
        if not deploy:
            return
        cred = (
            db.query(InfraServerCredential)
            .filter(InfraServerCredential.server_id == server_id)
            .one_or_none()
        )
        if cred is None:
            return
        try:
            await _do_deploy_beszel(server, db, settings, actor_user_id=actor_user_id)
        except Exception as exc:
            write_audit(
                db,
                actor_user_id=actor_user_id,
                action='beszel.deploy',
                success=False,
                server_id=str(server.id),
                server_name=server.name,
                error_excerpt=str(exc)[:500],
            )
            db.commit()
    finally:
        db.close()


@router.post('/api/infra/servers')
async def create_server(
    body: ServerCreate,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    db.commit()
    db.refresh(server)
    background_tasks.add_task(
        _sync_and_maybe_deploy_beszel,
        str(server.id),
        settings,
        deploy=bool(body.credential),
        actor_user_id=user.id,
    )
    return _server_public(server)


@router.patch('/api/infra/servers/{server_id}')
async def update_server(
    server_id: str,
    body: ServerUpdate,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    if body.name is not None or body.hostname is not None:
        background_tasks.add_task(
            _sync_and_maybe_deploy_beszel,
            str(server.id),
            settings,
            deploy=False,
            actor_user_id=user.id,
        )
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
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
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
    db.commit()
    background_tasks.add_task(
        _sync_and_maybe_deploy_beszel,
        server_id,
        settings,
        deploy=True,
        actor_user_id=user.id,
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
TOKEN="$1"; KEY="$2"; PORT="$3"; HUB="$4"; NAME="$5"

HAS_DOCKER=0
command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && HAS_DOCKER=1
# Prefer common NVIDIA paths even when SSH login PATH is minimal.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
HAS_NVIDIA=0
if command -v nvidia-smi >/dev/null 2>&1; then
    HAS_NVIDIA=1
fi

_run_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo "$@"
    else
        return 1
    fi
}

# S.M.A.R.T. (Beszel-native): smartctl + caps / device access.
# Docs: https://beszel.dev/guide/smart-data
ensure_smartctl() {
    if command -v smartctl >/dev/null 2>&1; then
        return 0
    fi
    if _run_root sh -c 'command -v apt-get >/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y smartmontools'; then
        :
    elif _run_root sh -c 'command -v dnf >/dev/null && dnf install -y smartmontools'; then
        :
    elif _run_root sh -c 'command -v pacman >/dev/null && pacman -Sy --noconfirm smartmontools'; then
        :
    else
        echo "beszel-agent: smartctl missing — install smartmontools for S.M.A.R.T." >&2
        return 1
    fi
    command -v smartctl >/dev/null 2>&1
}

# Non-root agents need RAWIO/SYS_ADMIN on smartctl and group access to NVMe char nodes.
ensure_smart_permissions() {
    ensure_smartctl || return 0
    SMARTCTL_BIN="$(command -v smartctl)"
    if [ "$(id -u)" != "0" ]; then
        _run_root setcap cap_sys_rawio,cap_sys_admin+ep "$SMARTCTL_BIN" 2>/dev/null || \
            echo "beszel-agent: could not setcap smartctl (S.M.A.R.T. may need root)" >&2
        if getent group disk >/dev/null 2>&1; then
            _run_root usermod -aG disk "$(id -un)" 2>/dev/null || true
        fi
        # Many distros ship /dev/nvmeN as 600 root:root; Beszel docs recommend disk:0660.
        if [ ! -f /etc/udev/rules.d/99-beszel-smart.rules ]; then
            _run_root tee /etc/udev/rules.d/99-beszel-smart.rules >/dev/null <<'UDEV' || true
KERNEL=="nvme[0-9]*", GROUP="disk", MODE="0660"
UDEV
            _run_root udevadm control --reload-rules 2>/dev/null || true
            _run_root udevadm trigger 2>/dev/null || true
        fi
    fi
}

# Disk controller nodes for Docker --device (not partitions).
smart_device_args() {
    for d in /dev/nvme[0-9] /dev/sd[a-z]; do
        if [ -e "$d" ]; then
            printf ' --device=%s:%s' "$d" "$d"
        fi
    done
}

systemd_device_allow_lines() {
    for d in /dev/nvme[0-9] /dev/sd[a-z]; do
        if [ -e "$d" ]; then
            printf 'DeviceAllow=%s r\n' "$d"
        fi
    done
}

# NVIDIA: official Docker scratch agent cannot use NVML/nvidia-smi (no glibc).
# Prefer host binary + systemd so nvidia-smi on the host works.
install_binary() {
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64)  GOARCH=amd64 ;;
        aarch64|arm64) GOARCH=arm64 ;;
        *) echo "unsupported arch: $ARCH" >&2; return 1 ;;
    esac

    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT

    RELEASE_URL="https://github.com/henrygd/beszel/releases/latest/download/beszel-agent_Linux_${GOARCH}.tar.gz"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$RELEASE_URL" -o "$TMPDIR/beszel-agent.tar.gz"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$TMPDIR/beszel-agent.tar.gz" "$RELEASE_URL"
    else
        echo "beszel-agent: need curl or wget" >&2; return 1
    fi

    tar -xzf "$TMPDIR/beszel-agent.tar.gz" -C "$TMPDIR"
    if [ -w /usr/local/bin ] || [ "$(id -u)" = "0" ]; then
        install -m 755 "$TMPDIR/beszel-agent" /usr/local/bin/beszel-agent
        BIN=/usr/local/bin/beszel-agent
        UNIT_DIR=/etc/systemd/system
        SYSTEMCTL="systemctl"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        sudo install -m 755 "$TMPDIR/beszel-agent" /usr/local/bin/beszel-agent
        BIN=/usr/local/bin/beszel-agent
        UNIT_DIR=/etc/systemd/system
        SYSTEMCTL="sudo systemctl"
    else
        mkdir -p "$HOME/.local/bin"
        install -m 755 "$TMPDIR/beszel-agent" "$HOME/.local/bin/beszel-agent"
        BIN="$HOME/.local/bin/beszel-agent"
        UNIT_DIR=""
        SYSTEMCTL=""
    fi

    ensure_smart_permissions || true

    if [ "$HAS_DOCKER" = "1" ]; then
        docker rm -f "$NAME" 2>/dev/null || true
    fi
    if [ -n "$SYSTEMCTL" ]; then
        $SYSTEMCTL stop "$NAME" 2>/dev/null || true
    fi

    if [ -n "$UNIT_DIR" ] && [ -d "$UNIT_DIR" ]; then
        UNIT_FILE="$UNIT_DIR/${NAME}.service"
        DEVICE_ALLOW="$(systemd_device_allow_lines)"
        UNIT_BODY=$(cat <<EOF2
[Unit]
Description=Beszel Agent ($NAME)
After=network.target

[Service]
ExecStart=$BIN
Restart=always
Environment=TOKEN=$TOKEN
Environment=KEY=$KEY
Environment=LISTEN=$PORT
Environment=HUB_URL=$HUB
AmbientCapabilities=CAP_SYS_RAWIO CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_SYS_RAWIO CAP_SYS_ADMIN
$DEVICE_ALLOW
[Install]
WantedBy=multi-user.target
EOF2
)
        if [ "$(id -u)" = "0" ] || [ -w "$UNIT_DIR" ]; then
            printf '%s\n' "$UNIT_BODY" >"$UNIT_FILE"
        else
            printf '%s\n' "$UNIT_BODY" | sudo tee "$UNIT_FILE" >/dev/null
        fi
        $SYSTEMCTL daemon-reload
        $SYSTEMCTL enable --now "$NAME"
        echo "beszel-agent: systemd $NAME listening $PORT hub $HUB${HAS_NVIDIA:+ (nvidia-smi)}"
        return 0
    fi

    # Stop previous nohup agent bound to this port (LISTEN is env-only, not argv).
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${PORT}/tcp" 2>/dev/null || true
    elif command -v ss >/dev/null 2>&1; then
        OLD_PIDS=$(ss -lptn "sport = :$PORT" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u)
        for pid in $OLD_PIDS; do kill "$pid" 2>/dev/null || true; done
    fi
    sleep 1
    nohup env TOKEN="$TOKEN" KEY="$KEY" LISTEN="$PORT" HUB_URL="$HUB" \
        "$BIN" >/tmp/${NAME}.log 2>&1 &
    echo "beszel-agent: nohup $NAME (pid $!) listening $PORT hub $HUB${HAS_NVIDIA:+ (nvidia-smi)}"
    return 0
}

if [ "$HAS_NVIDIA" = "1" ]; then
    install_binary
    exit $?
fi

if [ "$HAS_DOCKER" = "1" ]; then
    docker rm -f "$NAME" 2>/dev/null || true
    # :alpine includes smartmontools; scratch image cannot do S.M.A.R.T.
    IMAGE=henrygd/beszel-agent:alpine
    DEVICE_ARGS="$(smart_device_args)"
    # shellcheck disable=SC2086
    docker run -d \
        --name "$NAME" \
        --network host \
        --restart unless-stopped \
        --cap-add SYS_RAWIO \
        --cap-add SYS_ADMIN \
        $DEVICE_ARGS \
        -v /var/run/docker.sock:/var/run/docker.sock:ro \
        -e TOKEN="$TOKEN" \
        -e KEY="$KEY" \
        -e LISTEN="$PORT" \
        -e HUB_URL="$HUB" \
        "$IMAGE"
    echo "beszel-agent: $NAME listening $PORT hub $HUB (docker $IMAGE)"
    exit 0
fi

install_binary
exit $?
"""


async def _do_deploy_beszel(
    server: InfraServer,
    db: Session,
    settings: Settings,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Core deploy logic — SSH into server and install beszel-agent."""
    try:
        hub_token, listen_port = await upsert_beszel_system(server, settings)
        # Allow agent rebind after Docker ↔ host-binary switch.
        await clear_beszel_fingerprint(server, settings)
        if not hub_token:
            with open(f'{settings.beszel_shared_path}/token') as f:
                hub_token = f.read().strip()
        with open(f'{settings.beszel_shared_path}/id_ed25519.pub') as f:
            hub_pubkey = f.read().strip()
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f'Beszel credentials not ready ({exc}). Run docker compose up first.',
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def _sq(s: str) -> str:
        return "'" + s.replace("'", "'\\''") + "'"

    octet = server.hostname.rsplit('.', 1)[-1]
    cname = f'beszel-agent-{octet}' if octet.isdigit() else 'beszel-agent-host'
    hub_public = settings.beszel_hub_public_url.rstrip('/')

    script = (
        f'sh -s {_sq(hub_token)} {_sq(hub_pubkey)} {listen_port} '
        f"{_sq(hub_public)} {_sq(cname)} <<'__DEPLOY__'\n"
        + _BESZEL_AGENT_DEPLOY_SCRIPT
        + '\n__DEPLOY__'
    )

    try:
        result = await _run_on_server(db, server, script, timeout=180.0)
    except (SSHError, HTTPException) as exc:
        write_audit(
            db,
            actor_user_id=actor_user_id,
            action='beszel.deploy',
            success=False,
            server_id=str(server.id),
            server_name=server.name,
            error_excerpt=str(exc)[:500],
        )
        db.commit()
        raise

    ok = result.exit_code == 0
    write_audit(
        db,
        actor_user_id=actor_user_id,
        action='beszel.deploy',
        success=ok,
        server_id=str(server.id),
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
    await upsert_beszel_system(server, settings)
    return await _do_deploy_beszel(server, db, settings, actor_user_id=user.id)


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
