"""Che secret / PII trước khi payload trace rời process."""

from __future__ import annotations

import re
from typing import Any

from src.domain.guardrails.pii import redact_pii

_MAX_DEPTH = 8


def redact_text(text: str, *, max_chars: int = 32000) -> str:
    """Mask Bearer / sk-… / password; cắt chuỗi quá dài."""
    if not isinstance(text, str):
        text = str(text)
    out = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}", "Bearer ***", text)
    out = re.sub(r"sk-[A-Za-z0-9]{16,}", "sk-***", out)
    out = re.sub(r"(?i)password\s*[=:]\s*\S+", "password=***", out)
    if len(out) > max_chars:
        return out[:max_chars] + "…[truncated]"
    return out


def redact_deep(value: Any, _depth: int = 0) -> Any:
    """Che PII trong chuỗi/dict/list lồng nhau (mask Langfuse)."""
    if _depth >= _MAX_DEPTH:
        return "[QUÁ SÂU — BỎ QUA]"
    if isinstance(value, str):
        return redact_pii(value)
    if isinstance(value, dict):
        return {k: redact_deep(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_deep(v, _depth + 1) for v in value]
    return value
