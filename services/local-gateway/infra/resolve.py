"""Resolve InfraServer rows by IP / name / tags (exact-first, no vector)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

_SSH_VERB = re.compile(r'\bssh\b|\bv[aà]o[f]?\b', re.I)


@dataclass(frozen=True)
class ResolveCandidate:
    server_id: str
    name: str
    hostname: str
    port: int
    username: str
    tags: tuple[str, ...]
    score: int
    match: str


def _norm(s: str) -> str:
    return s.strip().lower()


def _is_ipv4_octet(q: str) -> bool:
    if not q.isdigit() or len(q) > 3:
        return False
    return 0 <= int(q) <= 255


def rank_servers(
    query: str,
    servers: Sequence[object],
    *,
    limit: int = 10,
) -> list[ResolveCandidate]:
    """Rank servers for ``q``.

    Score (higher is better):
      100 exact hostname
       90 exact name
       80 exact tag
       70 IPv4 last octet (query "250" → 192.168.1.250)
       50 hostname prefix
       40 name prefix
       20 hostname/name/tag substring
    """
    q = _norm(query)
    if not q:
        return []

    scored: list[ResolveCandidate] = []
    for s in servers:
        hostname = str(getattr(s, 'hostname', '') or '')
        name = str(getattr(s, 'name', '') or '')
        tags = tuple(str(t) for t in (getattr(s, 'tags', None) or []))
        hn = _norm(hostname)
        nm = _norm(name)
        tg = [_norm(t) for t in tags]

        score = 0
        match = ''
        if hn == q:
            score, match = 100, 'hostname_exact'
        elif nm == q:
            score, match = 90, 'name_exact'
        elif q in tg:
            score, match = 80, 'tag_exact'
        elif _is_ipv4_octet(q) and hn.endswith('.' + q):
            score, match = 70, 'hostname_last_octet'
        elif hn.startswith(q):
            score, match = 50, 'hostname_prefix'
        elif nm.startswith(q):
            score, match = 40, 'name_prefix'
        elif q in hn or q in nm or any(q in t for t in tg):
            score, match = 20, 'substring'
        else:
            continue

        scored.append(
            ResolveCandidate(
                server_id=str(getattr(s, 'id', None) or getattr(s, 'id')),
                name=name,
                hostname=hostname,
                port=int(getattr(s, 'port', 22) or 22),
                username=str(getattr(s, 'username', '') or ''),
                tags=tags,
                score=score,
                match=match,
            )
        )

    scored.sort(key=lambda c: (-c.score, c.name.lower()))
    return scored[: max(1, limit)]


def looks_like_ssh_connect_only(query: str) -> bool:
    """True when the user only asked to connect (ssh/vao/250), not run a command."""
    t = (query or '').strip()
    if not t:
        return False
    if _is_ipv4_octet(t):
        return True
    if re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', t):
        return True
    if _SSH_VERB.search(t) and re.search(r'\b\d{1,3}(?:\.\d{1,3}){3}\b|\b\d{1,3}\b', t):
        return True
    return False


def enrich_resolve_response(
    query: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Add a one-line Vietnamese reply so the agent stops after resolve."""
    out: dict[str, Any] = {}
    if len(items) != 1:
        return out
    host = items[0]
    hostname = host.get('hostname') or host.get('name') or ''
    username = host.get('username') or ''
    reply = (
        f'Đã SSH tới {hostname} (user {username}). '
        f'Gõ lệnh tiếp theo nếu cần (không sudo).'
    )
    out['assistant_reply_vi'] = reply
    if looks_like_ssh_connect_only(query):
        out['do_not_call_infra_run'] = True
        out['agent_instruction'] = (
            'Trả lời đúng 1 dòng assistant_reply_vi bằng tiếng Việt. '
            'Không gọi infra_run. Không giải thích sudo/harness/askpass.'
        )
    return out
