"""A/B prompt version selection — sticky bucket theo user_id (giống vn-stock)."""

from __future__ import annotations

import hashlib
from contextvars import ContextVar, Token

_prompt_version: ContextVar[str | None] = ContextVar("prompt_version", default=None)


def pick_prompt_version(
    user_id: str,
    *,
    enabled: bool = False,
    version_a: str = "production",
    version_b: str = "v2",
    split_pct: int = 50,
) -> str:
    """Cùng user_id luôn nhận cùng variant khi A/B bật."""
    if not enabled:
        return version_a or "production"
    if split_pct <= 0:
        return version_a
    if split_pct >= 100:
        return version_b
    digest = hashlib.sha256(user_id.encode()).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return version_b if bucket < split_pct else version_a


def current_prompt_version() -> str:
    ver = _prompt_version.get()
    if ver:
        return ver
    try:
        from langgraph.runtime import get_runtime

        runtime_ver = (get_runtime().context or {}).get("prompt_version")
        if runtime_ver:
            return str(runtime_ver)
    except Exception:
        pass
    return "production"


def bind_prompt_version(version: str) -> Token:
    return _prompt_version.set(version)


def reset_prompt_version(token: Token) -> None:
    _prompt_version.reset(token)


def resolve_prompt_version(user_id: str) -> str:
    """Đọc `PROMPT_AB_*` từ settings rồi sticky-bucket theo user_id."""
    from src.shared.settings import settings

    return pick_prompt_version(
        user_id or "default",
        enabled=bool(settings.prompt_ab_enabled),
        version_a=settings.prompt_ab_version_a or "production",
        version_b=settings.prompt_ab_version_b or "v2",
        split_pct=int(settings.prompt_ab_split_pct),
    )
