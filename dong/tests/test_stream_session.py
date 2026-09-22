"""Tests for Phase 4 — POST /api/agent/stream nhận session_id, user_id, câu hỏi."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Output
from src.main import app, _cache

client = TestClient(app)

_VALID_QUESTION = "Hôm nay có bao nhiêu lượt xe vào?"


# ---------------------------------------------------------------------------
# Helper: mock generator factory
# ---------------------------------------------------------------------------
def _make_mock_stream(answer: str = "Test answer"):
    def mock_generator(*args, **kwargs):
        yield {"node_id": "classify_node", "status": "running"}
        yield {
            "node_id": "classify_node",
            "status": "done",
            "input": "test",
            "output": "query_data",
        }
        yield {
            "__final_result__": Agent_Output(
                question=_VALID_QUESTION, answer=answer, detail="mock"
            )
        }

    return mock_generator


# ---------------------------------------------------------------------------
# 1. Stream accepts explicit session_id and user_id
# ---------------------------------------------------------------------------
def test_api_agent_stream_accepts_session_and_user_id(monkeypatch):
    """POST with explicit ids — mock run_agent_stream — assert kwargs propagated."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream") as mock_stream:
        mock_stream.side_effect = _make_mock_stream()

        res = client.post(
            "/api/agent/stream",
            json={
                "question": _VALID_QUESTION,
                "session_id": "sess-abc-123",
                "user_id": "user-xyz-456",
            },
        )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    mock_stream.assert_called_once()
    kwargs = mock_stream.call_args.kwargs
    assert kwargs.get("session_id") == "sess-abc-123", (
        f"Expected session_id='sess-abc-123', got: {kwargs}"
    )
    assert kwargs.get("user_id") == "user-xyz-456", (
        f"Expected user_id='user-xyz-456', got: {kwargs}"
    )


# ---------------------------------------------------------------------------
# 2. Reject empty session_id
# ---------------------------------------------------------------------------
def test_api_agent_stream_rejects_empty_session_id():
    """HTTP 400 khi session_id='' hoặc chỉ toàn khoảng trắng."""
    # Completely empty
    res = client.post(
        "/api/agent/stream",
        json={"question": _VALID_QUESTION, "session_id": "", "user_id": "user-1"},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    data = res.json()
    assert "session_id" in data.get("detail", "").lower()

    # Whitespace only
    res2 = client.post(
        "/api/agent/stream",
        json={"question": _VALID_QUESTION, "session_id": "   ", "user_id": "user-1"},
    )
    assert res2.status_code == 400, f"Expected 400, got {res2.status_code}: {res2.text}"
    data2 = res2.json()
    assert "session_id" in data2.get("detail", "").lower()


# ---------------------------------------------------------------------------
# 3. Reject empty user_id
# ---------------------------------------------------------------------------
def test_api_agent_stream_rejects_empty_user_id():
    """HTTP 400 khi user_id='' hoặc chỉ toàn khoảng trắng."""
    # Completely empty
    res = client.post(
        "/api/agent/stream",
        json={"question": _VALID_QUESTION, "session_id": "sess-1", "user_id": ""},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    data = res.json()
    assert "user_id" in data.get("detail", "").lower()

    # Whitespace only
    res2 = client.post(
        "/api/agent/stream",
        json={"question": _VALID_QUESTION, "session_id": "sess-1", "user_id": "  "},
    )
    assert res2.status_code == 400, f"Expected 400, got {res2.status_code}: {res2.text}"
    data2 = res2.json()
    assert "user_id" in data2.get("detail", "").lower()


# ---------------------------------------------------------------------------
# 4. Backend validates non-empty but non-UUID ids are also accepted
# ---------------------------------------------------------------------------
def test_api_agent_stream_accepts_non_uuid_ids(monkeypatch):
    """Bất kỳ string không rỗng nào đều hợp lệ — không yêu cầu UUID format."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream") as mock_stream:
        mock_stream.side_effect = _make_mock_stream()

        res = client.post(
            "/api/agent/stream",
            json={
                "question": _VALID_QUESTION,
                "session_id": "my-custom-session",
                "user_id": "admin",
            },
        )

    assert res.status_code == 200

    kwargs = mock_stream.call_args.kwargs
    assert kwargs.get("session_id") == "my-custom-session"
    assert kwargs.get("user_id") == "admin"


# ---------------------------------------------------------------------------
# 5. SSE __answer__ event contains session_id and user_id in meta
# ---------------------------------------------------------------------------
def test_api_agent_stream_sse_events_present(monkeypatch):
    """SSE response must contain graph node events and __answer__ event."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream") as mock_stream:
        mock_stream.side_effect = _make_mock_stream(answer="Có 42 lượt xe.")

        res = client.post(
            "/api/agent/stream",
            json={
                "question": _VALID_QUESTION,
                "session_id": "sess-meta-test",
                "user_id": "user-meta-test",
            },
        )

    assert res.status_code == 200
    text = res.text
    events = [
        json.loads(line.replace("data: ", ""))
        for line in text.split("\n\n")
        if line.strip() and line.strip().startswith("data: ")
    ]
    answer_events = [e for e in events if e.get("node_id") == "__answer__"]
    assert len(answer_events) == 1
    assert "Có 42 lượt xe." in answer_events[0]["output"]
