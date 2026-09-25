from __future__ import annotations

from contextvars import ContextVar, Token

from agent.llm.profiles import LlmProfile, resolve_profile

_current_profile: ContextVar[LlmProfile | None] = ContextVar("llm_profile", default=None)


def set_llm_profile(profile: LlmProfile) -> Token:
    return _current_profile.set(profile)


def reset_llm_profile(token: Token) -> None:
    try:
        _current_profile.reset(token)
    except ValueError:
        # SSE/thread có thể đổi Context — bỏ qua nếu token không thuộc context hiện tại.
        _current_profile.set(None)


def get_llm_profile() -> LlmProfile:
    current = _current_profile.get()
    if current is not None:
        return current
    return resolve_profile(None)
