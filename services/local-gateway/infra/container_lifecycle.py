"""Build shell-safe docker lifecycle commands for remote SSH."""

from __future__ import annotations

import re
import shlex

ALLOWED_ACTIONS = frozenset({'start', 'stop', 'restart'})

# Docker container id: 12–64 hex chars (short or full).
_CONTAINER_ID_RE = re.compile(r'^[a-fA-F0-9]{12,64}$')
# Docker container name (roughly): letters, digits, underscore, period, hyphen.
_CONTAINER_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')


class ContainerLifecycleError(ValueError):
    """Invalid action or container identifier."""


def pick_container_ref(
    *,
    container_id: str | None,
    container_name: str | None,
) -> str:
    """Prefer container_id when valid; else container_name."""
    cid = (container_id or '').strip()
    if cid:
        if not _CONTAINER_ID_RE.fullmatch(cid):
            raise ContainerLifecycleError('Invalid container_id')
        return cid
    name = (container_name or '').strip()
    if not name:
        raise ContainerLifecycleError('container_id or container_name required')
    if not _CONTAINER_NAME_RE.fullmatch(name):
        raise ContainerLifecycleError('Invalid container_name')
    return name


def build_docker_lifecycle_command(
    action: str,
    *,
    container_id: str | None = None,
    container_name: str | None = None,
) -> str:
    """Return e.g. ``docker start 'abc123…'`` with shell-safe quoting."""
    act = (action or '').strip().lower()
    if act not in ALLOWED_ACTIONS:
        raise ContainerLifecycleError(f'Unsupported action: {action!r}')
    ref = pick_container_ref(
        container_id=container_id,
        container_name=container_name,
    )
    return f'docker {act} {shlex.quote(ref)}'
