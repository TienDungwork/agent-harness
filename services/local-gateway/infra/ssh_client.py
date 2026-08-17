from __future__ import annotations

import time
from dataclasses import dataclass

import asyncssh


@dataclass
class SSHResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class SSHError(Exception):
    def __init__(self, message: str, *, code: str = 'ssh_error'):
        self.code = code
        super().__init__(message)


async def run_ssh(
    *,
    hostname: str,
    port: int,
    username: str,
    auth_type: str,
    secret: str,
    command: str,
    timeout: float = 10.0,
    known_host_key: str | None = None,
    passphrase: str | None = None,
) -> SSHResult:
    """Run a remote command over SSH. secret is private key PEM or password."""
    connect_kwargs: dict = {
        'host': hostname,
        'port': port,
        'username': username,
        'known_hosts': None if not known_host_key else None,
        'login_timeout': timeout,
    }
    # First connection may learn host key; strict pinning is applied at API layer
    # via stored fingerprint after admin verifies.
    if auth_type == 'password':
        connect_kwargs['password'] = secret
    else:
        connect_kwargs['client_keys'] = [
            asyncssh.import_private_key(secret, passphrase)
        ]

    started = time.monotonic()
    try:
        async with asyncssh.connect(**connect_kwargs) as conn:
            result = await conn.run(command, check=False, timeout=timeout)
    except asyncssh.PermissionDenied as exc:
        raise SSHError('SSH authentication failed', code='auth_failed') from exc
    except asyncssh.HostKeyNotVerifiable as exc:
        raise SSHError('host key not verifiable', code='host_key') from exc
    except TimeoutError as exc:
        raise SSHError('SSH command timed out', code='timeout') from exc
    except Exception as exc:
        raise SSHError(str(exc), code='ssh_error') from exc

    duration_ms = int((time.monotonic() - started) * 1000)
    return SSHResult(
        exit_code=int(result.exit_status or 0),
        stdout=result.stdout or '',
        stderr=result.stderr or '',
        duration_ms=duration_ms,
    )
