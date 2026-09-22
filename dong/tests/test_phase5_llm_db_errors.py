"""Phase 5 — Lỗi LLM/DB: message ngắn trên UI, stream không crash."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import USER_ERROR_MAX_LEN, _format_error_message, _short_user_error, app

client = TestClient(app)


def test_short_user_error_truncates():
    long_msg = "x" * 300
    out = _short_user_error(long_msg)
    assert len(out) <= USER_ERROR_MAX_LEN
    assert out.endswith("…")


def test_format_error_message_no_stack_or_sql_leak():
    exc = RuntimeError("Traceback (most recent call last): SELECT * FROM secret_table")
    msg = _format_error_message(exc)
    assert "traceback" not in msg.lower()
    assert "select *" not in msg.lower()
    assert len(msg) <= USER_ERROR_MAX_LEN


@pytest.mark.parametrize(
    "exc,keyword",
    [
        (RuntimeError("clickhouse connect error: refused"), "clickhouse"),
        (RuntimeError("psycopg2.OperationalError: connection refused"), "database"),
        (TimeoutError("Request timed out"), "thời gian"),
        (RuntimeError("openai.RateLimitError: 429"), "rate limit"),
    ],
)
def test_format_error_messages_short_vietnamese(exc, keyword):
    msg = _format_error_message(exc)
    assert keyword.lower() in msg.lower()
    assert len(msg) <= USER_ERROR_MAX_LEN


def test_stream_db_error_yields_answer_not_crash(monkeypatch):
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()
    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=RuntimeError("clickhouse connect error: connection refused"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu lượt xe vào?"},
        )
    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))
    answer = next(ev for ev in events if ev.get("node_id") == "__answer__")
    assert answer.get("status") == "error"
    assert "clickhouse" in str(answer.get("output", "")).lower()
    assert "traceback" not in str(answer.get("output", "")).lower()


def test_stream_graph_thread_error_yields_friendly_answer(monkeypatch):
    """Lỗi trong graph thread → __answer__ error, không crash generator."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()

    def _boom(*_args, **_kwargs):
        yield {"node_id": "recall", "status": "running"}
        raise RuntimeError("LLM API timeout after 30s")

    with patch("src.agent.graph.run_agent_stream", side_effect=_boom):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu xe vào?"},
        )
    assert res.status_code == 200
    assert "__answer__" in res.text
    assert "mô hình ai" in res.text.lower() or "thời gian" in res.text.lower()


def test_frontend_stream_error_handling_wiring():
    res = client.get("/app.js")
    js = res.text if res.status_code == 200 else open("frontend/app.js", encoding="utf-8").read()
    assert "lastStreamError" in js
    assert "event.status === 'error'" in js or "event.status === \"error\"" in js
    assert "event.node_id === 'error'" in js or 'event.node_id === "error"' in js
