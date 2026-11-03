"""SSE payload helpers cho /api/agent/stream."""

from __future__ import annotations

import copy
from typing import Any

_SSE_SCHEMA_EXCERPT_MAX = 16000


def sanitize_sse_event(event: dict[str, Any]) -> dict[str, Any]:
    ev = copy.deepcopy(event)
    for side in ("input", "output"):
        payload = ev.get(side)
        if not isinstance(payload, dict):
            continue
        excerpt = payload.get("schema_excerpt")
        if isinstance(excerpt, str) and len(excerpt) > _SSE_SCHEMA_EXCERPT_MAX:
            payload["schema_excerpt"] = (
                excerpt[:_SSE_SCHEMA_EXCERPT_MAX]
                + f"\n… (cắt {len(excerpt) - _SSE_SCHEMA_EXCERPT_MAX} ký tự cho SSE; xem Langfuse để full)"
            )
    return ev


def build_chart_sse_event(
    chart_spec: dict[str, Any] | None,
    chart_png_base64: str | None,
    chart_rows: list[dict] | None = None,
) -> dict[str, Any]:
    spec = chart_spec or {}
    chart_type = spec.get("chart_type", "bar") if isinstance(spec, dict) else "bar"
    event: dict[str, Any] = {
        "node_id": "__chart__",
        "status": "done",
        "chart_type": chart_type,
        "chart_spec": spec,
        "chart_png_base64": chart_png_base64 or "",
    }
    if chart_rows is not None:
        event["chart_rows"] = chart_rows
    return event


def split_into_chunks(text: str, chunk_words: int = 3) -> list[str]:
    if not text:
        return []
    words = text.split(" ")
    chunks: list[str] = []
    for i in range(0, len(words), chunk_words):
        group = words[i : i + chunk_words]
        delta = " ".join(group)
        if i + chunk_words < len(words):
            delta += " "
        chunks.append(delta)
    return chunks
