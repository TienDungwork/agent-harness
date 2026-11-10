"""Langfuse-safe payload helpers: redact, slim state, LLM I/O."""

from __future__ import annotations

import re
from typing import Any, Mapping


def redact_text(text: str, *, max_chars: int = 32000) -> str:
    if not isinstance(text, str):
        text = str(text)
    out = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}", "Bearer ***", text)
    out = re.sub(r"sk-[A-Za-z0-9]{16,}", "sk-***", out)
    out = re.sub(r"(?i)password\s*[=:]\s*\S+", "password=***", out)
    if len(out) > max_chars:
        return out[:max_chars] + "…[truncated]"
    return out


def slim_state(state: Mapping[str, Any]) -> dict[str, Any]:
    rows = state["rows"] if "rows" in state and isinstance(state["rows"], list) else []
    snap: dict[str, Any] = {"row_count": len(rows)}
    for key in (
        "question",
        "intent",
        "sql",
        "error",
        "repair_count",
        "orchestrator_step_index",
        "respond_mode",
        "selected_tables",
    ):
        if key in state:
            snap[key] = state[key]
    return snap


def llm_io_payload(system: str, user: str, text: str) -> dict[str, Any]:
    return {
        "input": {
            "system": redact_text(system or ""),
            "user": redact_text(user or ""),
        },
        "output": {"text": redact_text(text or "")},
    }
