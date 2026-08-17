from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncssh
from auth.session import SessionManager
from config import get_settings
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from infra.access import user_has_server_access
from infra.audit import write_audit
from infra.crypto import CryptoError, decrypt_text
from storage import models as db_models
from storage.models import InfraServer, InfraServerCredential, User

router = APIRouter(tags=['infra-ssh'])


def _session_factory():
    """Read SessionLocal at call time — init_db runs after module import."""
    return db_models.SessionLocal


def _auth_user_from_ws(websocket: WebSocket) -> User | None:
    settings = get_settings()
    raw = websocket.cookies.get(settings.session_cookie_name)
    session_factory = _session_factory()
    if not raw or session_factory is None:
        return None
    try:
        session = SessionManager(settings).load(raw)
    except PermissionError:
        return None
    db = session_factory()
    try:
        user = db.query(User).filter(User.id == session.user_id).one_or_none()
        if user is None or not user.is_active:
            return None
        db.expunge(user)
        return user
    finally:
        db.close()


@router.websocket('/api/infra/servers/{server_id}/ssh')
async def ssh_terminal_ws(websocket: WebSocket, server_id: str) -> None:
    await websocket.accept()

    user = _auth_user_from_ws(websocket)
    if user is None:
        await websocket.send_text(json.dumps({'t': 'e', 'm': 'Not authenticated'}))
        await websocket.close(code=4401)
        return

    session_factory = _session_factory()
    if session_factory is None:
        await websocket.send_text(json.dumps({'t': 'e', 'm': 'Database unavailable'}))
        await websocket.close(code=4503)
        return

    db = session_factory()
    try:
        if not user_has_server_access(
            db, user=user, server_id=server_id, required='read'
        ):
            write_audit(
                db,
                actor_user_id=user.id,
                action='access.denied',
                success=False,
                server_id=server_id,
                error_excerpt='ssh.session denied',
            )
            await websocket.send_text(json.dumps({'t': 'e', 'm': 'Forbidden'}))
            await websocket.close(code=4403)
            return

        server = db.query(InfraServer).filter(InfraServer.id == server_id).one_or_none()
        if server is None or not server.is_active:
            await websocket.send_text(json.dumps({'t': 'e', 'm': 'Server not found'}))
            await websocket.close(code=4404)
            return

        cred = (
            db.query(InfraServerCredential)
            .filter(InfraServerCredential.server_id == server.id)
            .one_or_none()
        )
        if cred is None:
            await websocket.send_text(
                json.dumps({'t': 'e', 'm': 'Server has no credentials'})
            )
            await websocket.close(code=4400)
            return

        try:
            secret = decrypt_text(cred.ciphertext)
            passphrase = (
                decrypt_text(cred.passphrase_ciphertext)
                if cred.passphrase_ciphertext
                else None
            )
        except CryptoError as exc:
            await websocket.send_text(json.dumps({'t': 'e', 'm': str(exc)}))
            await websocket.close(code=4500)
            return

        qs = websocket.query_params
        cols = max(20, min(int(qs.get('cols') or 120), 500))
        rows = max(5, min(int(qs.get('rows') or 32), 200))

        hostname = server.hostname
        port = int(server.port)
        username = server.username
        auth_type = server.auth_type
        server_name = server.name
        server_uuid = str(server.id)

        write_audit(
            db,
            actor_user_id=user.id,
            action='command.run',
            success=True,
            server_id=server_uuid,
            server_name=server_name,
            command_id='ssh_shell',
            command_rendered='interactive ssh shell',
        )
    finally:
        db.close()

    connect_kwargs: dict[str, Any] = {
        'host': hostname,
        'port': port,
        'username': username,
        'known_hosts': None,
        'login_timeout': 20,
    }
    if auth_type == 'password':
        connect_kwargs['password'] = secret
    else:
        try:
            connect_kwargs['client_keys'] = [
                asyncssh.import_private_key(secret, passphrase)
            ]
        except Exception as exc:
            await websocket.send_text(
                json.dumps({'t': 'e', 'm': f'Invalid private key: {exc}'})
            )
            await websocket.close()
            return

    try:
        async with asyncssh.connect(**connect_kwargs) as conn:
            process = await conn.create_process(
                term_type='xterm-256color',
                term_size=(cols, rows),
                encoding=None,
            )
            await websocket.send_text(
                json.dumps({'t': 'ready', 'host': f'{username}@{hostname}:{port}'})
            )

            async def ssh_to_ws() -> None:
                assert process.stdout is not None
                while True:
                    data = await process.stdout.read(8192)
                    if not data:
                        break
                    text = data.decode('utf-8', errors='replace')
                    await websocket.send_text(json.dumps({'t': 'o', 'd': text}))

            async def ws_to_ssh() -> None:
                assert process.stdin is not None
                while True:
                    raw = await websocket.receive_text()
                    msg = json.loads(raw)
                    kind = msg.get('t')
                    if kind == 'i':
                        process.stdin.write(
                            (msg.get('d') or '').encode('utf-8', errors='replace')
                        )
                    elif kind == 'r':
                        try:
                            process.change_terminal_size(
                                int(msg.get('c') or cols),
                                int(msg.get('r') or rows),
                            )
                        except Exception:
                            pass

            reader = asyncio.create_task(ssh_to_ws())
            writer = asyncio.create_task(ws_to_ssh())
            done, pending = await asyncio.wait(
                {reader, writer}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            for task in done:
                exc = task.exception()
                if exc and not isinstance(
                    exc, (WebSocketDisconnect, asyncio.CancelledError)
                ):
                    raise exc
            try:
                process.close()
                await process.wait_closed()
            except Exception:
                pass
    except asyncssh.PermissionDenied:
        await websocket.send_text(
            json.dumps({'t': 'e', 'm': 'SSH authentication failed'})
        )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({'t': 'e', 'm': str(exc)[:300]}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
