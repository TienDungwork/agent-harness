"""Tests for session message history API (short-term UI persistence)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.sessions.store import (
    append_session_messages,
    clear_sessions_store,
    create_session,
    get_session_messages,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_sessions():
    clear_sessions_store()
    yield
    clear_sessions_store()


def test_create_session_has_empty_messages():
    sess = create_session("user_a")
    assert sess.get("messages") == []


def test_append_and_get_messages_isolated_by_session():
    s1 = create_session("user_a", "Session 1")
    s2 = create_session("user_a", "Session 2")

    append_session_messages(
        s1["id"],
        "user_a",
        [
            {"role": "user", "content": "Câu A", "timestamp": "2026-09-22T10:00:00Z"},
            {"role": "assistant", "content": "Trả lời A", "timestamp": "2026-09-22T10:00:01Z"},
        ],
    )
    append_session_messages(
        s2["id"],
        "user_a",
        [
            {"role": "user", "content": "Câu B", "timestamp": "2026-09-22T11:00:00Z"},
            {"role": "assistant", "content": "Trả lời B", "timestamp": "2026-09-22T11:00:01Z"},
        ],
    )

    msgs_a = get_session_messages(s1["id"], "user_a")
    msgs_b = get_session_messages(s2["id"], "user_a")
    assert len(msgs_a) == 2
    assert len(msgs_b) == 2
    assert msgs_a[0]["content"] == "Câu A"
    assert msgs_b[0]["content"] == "Câu B"
    assert "Trả lời A" in msgs_a[1]["content"]
    assert "Trả lời B" in msgs_b[1]["content"]


def test_get_messages_api_success():
    sess = create_session("user_api", "Test")
    append_session_messages(
        sess["id"],
        "user_api",
        [
            {"role": "user", "content": "Xin chào", "timestamp": "2026-09-22T12:00:00Z"},
            {"role": "assistant", "content": "Chào bạn", "timestamp": "2026-09-22T12:00:01Z"},
        ],
    )

    res = client.get(f"/api/sessions/{sess['id']}/messages?user_id=user_api")
    assert res.status_code == 200
    data = res.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


def test_get_messages_api_wrong_user_404():
    sess = create_session("owner", "Owner session")
    res = client.get(f"/api/sessions/{sess['id']}/messages?user_id=other")
    assert res.status_code == 404


def test_get_messages_api_missing_user_422():
    sess = create_session("user_x")
    assert client.get(f"/api/sessions/{sess['id']}/messages").status_code == 422


def test_stream_persists_messages(monkeypatch):
    """Stream __answer__ lưu cặp user/assistant vào session store."""
    from src.agent.graph import Agent_Output
    from src.llm.schemas import QueryResult
    from src.main import _cache

    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    _cache.clear()

    sess = create_session("user_stream", "Stream test")
    question = "Hôm nay có bao nhiêu xe vào?"

    def _fake_stream(*_args, **_kwargs):
        yield {"node_id": "recall", "status": "done", "input": {}, "output": {}}
        out = Agent_Output(
            question=question,
            answer="Có 42 lượt xe vào.",
            query=QueryResult(tool="t", columns=["n"], rows=[[42]], row_count=1),
            detail="query_data",
        )
        yield {"__final_result__": out}

    with patch("src.agent.graph.run_agent_stream", side_effect=_fake_stream):
        res = client.post(
            "/api/agent/stream",
            json={
                "question": question,
                "session_id": sess["id"],
                "user_id": "user_stream",
            },
        )
        assert res.status_code == 200
        list(res.iter_lines())

    msgs = get_session_messages(sess["id"], "user_stream")
    assert msgs is not None
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == question
    assert msgs[1]["role"] == "assistant"
    assert "42" in msgs[1]["content"]


def test_frontend_loads_messages_from_api():
    res = client.get("/app.js")
    app_js = res.text if res.status_code == 200 else open("frontend/app.js", encoding="utf-8").read()
    assert "async function loadCurrentSessionMessages" in app_js
    assert "/api/sessions/" in app_js
    assert "/messages?user_id=" in app_js
    assert "await loadCurrentSessionMessages()" in app_js
