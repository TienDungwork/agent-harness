"""LLM client — multi-backend (openai / self_hosted / ollama), key rotation, offline mode.

Hỗ trợ cả OpenAI Cloud (gpt-4o-mini) và Model tự host (vd. qwen3-4b tại vLLM
endpoint http://192.168.1.196:18083/v1). Cả 2 backend đều expose API chuẩn
OpenAI ChatCompletions (ChatOpenAI.bind_tools).

Đổi LLM_BACKEND trong .env ("openai" hoặc "self_hosted") là đủ để chuyển đổi
backend mà không sửa code.
"""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from src.config import settings


@dataclass(frozen=True, slots=True)
class _Backend:
    default_base_url: str  # "" = mặc định OpenAI Cloud
    requires_real_key: bool
    dummy_key: str = "not-needed"


_BACKENDS: dict[str, _Backend] = {
    "openai": _Backend(default_base_url="", requires_real_key=True),
    "self_hosted": _Backend(
        default_base_url="http://192.168.1.196:18083/v1",
        requires_real_key=False,
        dummy_key="lgw_ef6984db8f59_zSvqDWXxYzeaU-4U0pLqS7LBiD5gvOm9wI7R-L4Lpqw",
    ),
    "ollama": _Backend(
        default_base_url="http://localhost:11434/v1",
        requires_real_key=False,
        dummy_key="ollama",
    ),
}


def _get_backend(name: str | None = None) -> _Backend:
    backend_name = (name or settings.llm_backend).strip().lower()
    if backend_name not in _BACKENDS:
        raise ValueError(f"LLM_BACKEND='{backend_name}' không hợp lệ — chọn: {', '.join(_BACKENDS)}.")
    return _BACKENDS[backend_name]


class _RotatingKeyPool:
    """Round-robin nhiều API key, tự đưa key bị 429 vào cooldown."""

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("Cần ít nhất 1 OPENAI_API_KEYS khi LLM_BACKEND=openai.")
        self._keys = deque(keys)
        self._cooldown: dict[str, float] = {}

    def get_key(self) -> str:
        now = time.time()
        for _ in range(len(self._keys)):
            key = self._keys[0]
            self._keys.rotate(-1)
            if self._cooldown.get(key, 0.0) <= now:
                return key
        return self._keys[0]  # tất cả cooldown -> vẫn thử key đầu, để OpenAI SDK tự retry/raise

    def mark_limited(self, key: str, cooldown_seconds: float = 60.0) -> None:
        self._cooldown[key] = time.time() + cooldown_seconds


@lru_cache(maxsize=1)
def _pool() -> _RotatingKeyPool:
    return _RotatingKeyPool(settings.api_keys)


def use_offline_tools(backend_override: str | None = None) -> bool:
    """Không key (khi backend=openai) hoặc đang pytest: agent giả 1 tool_call."""
    if bool(os.environ.get("PYTEST_CURRENT_TEST")):
        return True
    backend_name = (backend_override or settings.llm_backend).strip().lower()
    backend = _BACKENDS.get(backend_name)
    if not backend:
        return False
    return backend.requires_real_key and not settings.api_keys


def base_llm(
    model_override: str | None = None,
    backend_override: str | None = None,
    temperature_override: float | None = None,
):
    from langchain_openai import ChatOpenAI

    backend_name = (backend_override or settings.llm_backend).strip().lower()
    backend = _get_backend(backend_name)

    if backend_name == "self_hosted":
        api_key = settings.model_api_key or backend.dummy_key
        base_url = settings.model_base_url or backend.default_base_url
        model = model_override or settings.model_name or "qwen3-4b"
    elif backend_name == "openai":
        api_key = _pool().get_key()
        base_url = settings.llm_base_url or None
        model = model_override or settings.llm_model or "gpt-4o-mini"
    else:  # ollama
        api_key = backend.dummy_key
        base_url = settings.llm_base_url or backend.default_base_url
        model = model_override or settings.llm_model or "qwen2.5:3b-instruct-q4_K_M"

    temperature = settings.llm_temperature if temperature_override is None else temperature_override

    kwargs: dict = {
        "model": model,
        "temperature": temperature,
        "api_key": api_key,
        "max_retries": settings.llm_max_retries,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def invoke_with_tools(
    messages,
    tools=None,
    model_override: str | None = None,
    backend_override: str | None = None,
):
    llm = base_llm(model_override=model_override, backend_override=backend_override)
    if tools:
        llm = llm.bind_tools(tools)
    return llm.invoke(messages)


def invoke_text(
    system_prompt: str,
    user_prompt: str,
    model_override: str | None = None,
    backend_override: str | None = None,
) -> str:
    """Lời gọi LLM đơn giản không tool — dùng cho bước Answer (diễn giải số liệu)."""
    llm = base_llm(model_override=model_override, backend_override=backend_override)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    return str(response.content or "")

