"""Helpers parse SSE /api/agent/stream cho product tests (thay /ask)."""

from __future__ import annotations

import json
from typing import Any


def post_stream(client, question: str, *, session_id: str = "sess-1", user_id: str = "user_1", **extra: Any):
    body = {"question": question, "session_id": session_id, "user_id": user_id, **extra}
    return client.post("/api/agent/stream", json=body)


def parse_sse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload or payload == "[DONE]":
            continue
        events.append(json.loads(payload))
    return events


def sse_answer(res) -> str:
    for ev in reversed(parse_sse_events(res.text)):
        if ev.get("node_id") == "__answer__" or ev.get("complete"):
            return str(ev.get("answer") or ev.get("output") or "")
    return ""


def sse_complete(res) -> dict[str, Any] | None:
    for ev in reversed(parse_sse_events(res.text)):
        if ev.get("complete") or ev.get("node_id") == "__answer__":
            return ev
    return None
