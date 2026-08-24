"""Resolve InfraServer rows by IP / name / tags (exact-first, no vector)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


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
