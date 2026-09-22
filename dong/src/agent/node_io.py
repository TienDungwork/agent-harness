"""Structured I/O cho graph node events — Langfuse trace + SSE stream."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def json_safe(value: Any) -> Any:
    """Chuyển object sang kiểu JSON-serializable (giữ nguyên dữ liệu thực)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)


def node_event(
    node_id: str,
    *,
    input: Any,
    output: Any,
    meta: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Tạo event chuẩn: input/output là dict hoặc primitive — không tóm tắt."""
    ev: dict[str, Any] = {
        "node_id": node_id,
        "input": json_safe(input),
        "output": json_safe(output),
        "meta": json_safe(meta or {}),
    }
    for key, val in extra.items():
        ev[key] = json_safe(val) if key not in ("chart_png_base64",) else val
    return ev
