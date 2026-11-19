"""OpenAI / LangChain client factory — sync.

Phần còn lại chỉ gọi `get_client()` / `base_llm()`; không cần biết cloud hay self_hosted.
Key rotation chỉ khi backend cần key thật (OpenAI Cloud).
"""

from __future__ import annotations

from openai import OpenAI
from langchain_openai import ChatOpenAI

from src.infra.llm.backends import get_backend
from src.infra.llm.params import BALANCED, GenerationParams
from src.infra.llm.resilience import RotatingKeyPool
from src.shared.settings import settings

_pool_instance: RotatingKeyPool | None = None


def _get_pool() -> RotatingKeyPool:
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = RotatingKeyPool(settings.api_keys)
    return _pool_instance


def clear_key_pool() -> None:
    """Reset pool (tests / đổi OPENAI_API_KEYS runtime)."""
    global _pool_instance
    _pool_instance = None


class _PoolAccessor:
    """Giữ API cũ `_pool()` + `_pool.cache_clear()` cho test."""

    def __call__(self) -> RotatingKeyPool:
        return _get_pool()

    def cache_clear(self) -> None:
        clear_key_pool()


_pool = _PoolAccessor()


def _resolve_base_url(default_base_url: str, backend_name: str) -> str | None:
    if backend_name == "self_hosted":
        return settings.model_base_url or default_base_url or None
    if settings.llm_base_url:
        return settings.llm_base_url
    return default_base_url or None


def _api_key_for_backend(backend_name: str) -> str:
    backend = get_backend(backend_name)
    if backend.requires_real_key:
        return _get_pool().get_key()
    if backend_name == "self_hosted":
        return settings.model_api_key or backend.dummy_key
    return backend.dummy_key


def get_client() -> OpenAI:
    """OpenAI SDK client trỏ backend đang cấu hình."""
    name = settings.llm_backend.strip().lower()
    backend = get_backend(name)
    return OpenAI(
        api_key=_api_key_for_backend(name),
        base_url=_resolve_base_url(backend.default_base_url, name),
    )


def mark_current_key_limited(client: OpenAI, cooldown_seconds: float = 60.0) -> None:
    backend = get_backend(settings.llm_backend)
    if backend.requires_real_key and client.api_key:
        _get_pool().mark_limited(client.api_key, cooldown_seconds)


class SafeChatOpenAI(ChatOpenAI):
    """Giữ max_tokens cho endpoint OpenAI-compatible (đổi max_completion_tokens → max_tokens)."""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        return payload


def base_llm(
    model_override: str | None = None,
    backend_override: str | None = None,
    temperature_override: float | None = None,
    max_tokens_override: int | None = None,
    params: GenerationParams | None = None,
) -> ChatOpenAI:
    """LangChain ChatOpenAI — cùng backend/settings với `get_client()`."""
    name = (backend_override or settings.llm_backend).strip().lower()
    backend = get_backend(name)
    gen = params or BALANCED
    mt = max_tokens_override if max_tokens_override is not None else gen.max_tokens
    if name == "self_hosted":
        from src.infra.llm.gateway import cap_output_tokens, resolve_self_hosted_model

        model = resolve_self_hosted_model(model_override)
        mt = cap_output_tokens(mt)
    else:
        model = model_override or settings.llm_model or "gpt-4o-mini"
    kw = gen.to_langchain_kwargs()
    if temperature_override is not None:
        kw["temperature"] = temperature_override
    if mt is not None:
        kw["max_tokens"] = mt
    out: dict = {
        "model": model,
        "api_key": _api_key_for_backend(name),
        "max_retries": settings.llm_max_retries,
        "request_timeout": settings.llm_request_timeout_s,
        **kw,
    }
    base_url = _resolve_base_url(backend.default_base_url, name)
    if base_url:
        out["base_url"] = base_url
    return SafeChatOpenAI(**out)


def llm_model_label(backend_override: str | None = None) -> str:
    name = (backend_override or settings.llm_backend).strip().lower()
    if name == "self_hosted":
        from src.infra.llm.gateway import resolve_self_hosted_model

        return resolve_self_hosted_model()
    return settings.llm_model or "gpt-4o-mini"


# Alias cũ (structured / tests).
_llm_model_label = llm_model_label


def use_offline_tools(backend_override: str | None = None) -> bool:
    """Đã bỏ offline — luôn gọi LLM/DB thật."""
    return False


def ping() -> str:
    """Kiểm tra LLM backend sẵn sàng."""
    name = (settings.llm_backend or "").strip().lower()
    if name == "openai":
        if not (settings.api_keys or settings.llm_api_key):
            raise RuntimeError("LLM_BACKEND=openai nhưng thiếu OPENAI_API_KEYS / LLM_API_KEY")
        return "OK"
    from src.infra.llm.gateway import fetch_gateway_catalog

    data = fetch_gateway_catalog()
    err = data.get("error")
    if err:
        base = settings.effective_base_url or "http://192.168.1.198:18083/v1"
        raise RuntimeError(f"Lỗi kết nối tới LLM tại {base.rstrip('/')}/models: {err}")
    return "OK"


# Re-export completion helpers — `from src.infra.llm.client import invoke_text` vẫn chạy.
def __getattr__(name: str):
    if name in ("invoke_text", "invoke_with_tools", "chat_stream"):
        from src.infra.llm import completion as _completion

        return getattr(_completion, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
