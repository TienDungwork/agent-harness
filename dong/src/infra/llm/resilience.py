"""Resilience — RotatingKeyPool + retry backoff (Rate Limits & key rotation)."""

from __future__ import annotations

import random
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

from openai import RateLimitError

T = TypeVar("T")


class RotatingKeyPool:
    """Round-robin nhiều API key; đưa key bị 429 vào cooldown."""

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError(
                "RotatingKeyPool cần ≥1 API key. Đặt OPENAI_API_KEYS trong .env."
            )
        self._keys = deque(keys)
        self._cooldown: dict[str, float] = {}

    def get_key(self) -> str:
        now = time.time()
        for _ in range(len(self._keys)):
            key = self._keys[0]
            self._keys.rotate(-1)
            if self._cooldown.get(key, 0.0) <= now:
                return key
        time.sleep(1.0)
        return self.get_key()

    def mark_limited(self, key: str, cooldown_seconds: float = 60.0) -> None:
        self._cooldown[key] = time.time() + cooldown_seconds


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_retries: int = 5,
    on_rate_limit: Callable[[], None] | None = None,
) -> T:
    """Gọi `fn()` với exponential backoff + jitter khi RateLimitError."""
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError:
            if on_rate_limit is not None:
                on_rate_limit()
            if attempt == max_retries - 1:
                raise
            time.sleep((2**attempt) + random.uniform(0, 1))
    raise RuntimeError("retry_with_backoff: hết số lần thử")
