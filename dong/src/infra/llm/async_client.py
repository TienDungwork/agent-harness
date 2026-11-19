"""Async LLM client — AsyncOpenAI + semaphore backpressure + retry jitter.

Không gọi SDK sync trong endpoint async (block event loop). Tái dùng key rotation
từ `client._api_key_for_backend`.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from src.infra.llm.backends import get_backend
from src.infra.llm.client import _api_key_for_backend, _resolve_base_url
from src.infra.llm.params import GenerationParams
from src.shared.settings import settings

_LLM_SEMAPHORE = asyncio.Semaphore(settings.llm_max_concurrency or 5)


def semaphore_state() -> dict[str, int]:
    return {
        "limit": settings.llm_max_concurrency or 5,
        "available": _LLM_SEMAPHORE._value,  # noqa: SLF001
    }


def get_async_client() -> AsyncOpenAI:
    """AsyncOpenAI — song song `client.get_client()`. max_retries=0 để tự quản backoff."""
    name = settings.llm_backend.strip().lower()
    backend = get_backend(name)
    return AsyncOpenAI(
        api_key=_api_key_for_backend(name),
        base_url=_resolve_base_url(backend.default_base_url, name),
        timeout=settings.llm_request_timeout_s,
        max_retries=0,
    )


async def acall_with_retry(
    fn: Callable[[], Awaitable[Any]],
    *,
    max_retries: int | None = None,
) -> Any:
    attempts = settings.llm_max_retries if max_retries is None else max_retries
    for attempt in range(attempts):
        try:
            return await fn()
        except (RateLimitError, APITimeoutError):
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(min(2**attempt, 16) + random.uniform(0, 1))
    raise RuntimeError("acall_with_retry: hết số lần thử")


async def astream_chat(
    messages: list[dict],
    params: GenerationParams | None = None,
) -> AsyncIterator[str]:
    """Stream token async, giữ semaphore suốt stream."""
    params = params or GenerationParams()
    name = settings.llm_backend.strip().lower()
    if name == "self_hosted":
        from src.infra.llm.gateway import resolve_self_hosted_model

        model = resolve_self_hosted_model()
    else:
        model = settings.llm_model or "gpt-4o-mini"

    async with _LLM_SEMAPHORE:
        client = get_async_client()

        async def _open():
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **params.to_openai_kwargs(),
            )

        stream = await acall_with_retry(_open)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
