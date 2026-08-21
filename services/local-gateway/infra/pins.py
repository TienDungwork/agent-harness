"""Rank pinned containers for agent search (exact-first, no vector)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PinCandidate:
    pin_id: str
    user_id: str
    host: str
    container_name: str
    container_id: str | None
    image: str | None
    tags: tuple[str, ...]
    note: str | None
    server_id: str | None
    score: int
    match: str


def _norm(s: str) -> str:
    return s.strip().lower()


def rank_pins(
    query: str,
    pins: Sequence[object],
    *,
    limit: int = 20,
) -> list[PinCandidate]:
    """Rank pins for ``q``.

    Score (higher is better):
      100 exact container_name
       95 exact container_id
       90 exact host
       80 exact tag
       50 container_name prefix
       40 host prefix
       30 image substring
       20 note/tag/host/name substring
    """
    q = _norm(query)
    if not q:
        return []

    scored: list[PinCandidate] = []
    for p in pins:
        name = str(getattr(p, 'container_name', '') or '')
        cid = str(getattr(p, 'container_id', '') or '')
        host = str(getattr(p, 'host', '') or '')
        image = str(getattr(p, 'image', '') or '')
        note = str(getattr(p, 'note', '') or '')
        tags = tuple(str(t) for t in (getattr(p, 'tags', None) or []))
        nm, hn, im, nt = _norm(name), _norm(host), _norm(image), _norm(note)
        tg = [_norm(t) for t in tags]
        cid_n = _norm(cid)

        score = 0
        match = ''
        if nm == q:
            score, match = 100, 'container_exact'
        elif cid_n and (cid_n == q or cid_n.startswith(q)):
            score, match = 95, 'container_id'
        elif hn == q:
            score, match = 90, 'host_exact'
        elif q in tg:
            score, match = 80, 'tag_exact'
        elif nm.startswith(q):
            score, match = 50, 'container_prefix'
        elif hn.startswith(q):
            score, match = 40, 'host_prefix'
        elif q in im:
            score, match = 30, 'image_substring'
        elif q in nm or q in hn or q in nt or any(q in t for t in tg):
            score, match = 20, 'substring'
        else:
            continue

        scored.append(
            PinCandidate(
                pin_id=str(getattr(p, 'id')),
                user_id=str(getattr(p, 'user_id')),
                host=host,
                container_name=name,
                container_id=cid or None,
                image=image or None,
                tags=tags,
                note=note or None,
                server_id=str(getattr(p, 'server_id') or '') or None,
                score=score,
                match=match,
            )
        )

    scored.sort(key=lambda c: (-c.score, c.container_name.lower()))
    return scored[: max(1, min(int(limit or 20), 50))]
