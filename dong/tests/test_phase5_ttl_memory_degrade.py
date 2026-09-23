"""Phase 5: TTL / memory fail — degrade an toàn (vẫn trả lời được).

Tests:
- TTL get raises -> _lookup_ttl_cache returns None; /api/chat still 200 when agent mocked OK.
- TTL set raises -> response still returned with answer.
- recall_long_term raises -> recall_node returns empty memories, no exception.
- extract_and_store_memory raises -> run_store_extract returns done event with degraded output, no raise.
- Integration: stream with recall fail + agent OK -> __answer__ status done (not error); store_extract degraded OK.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Input, Agent_Output, recall_node, run_agent_stream, run_store_extract
from src.llm.schemas import QueryResult
from src.main import app, _lookup_ttl_cache
from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
    _ttl_cache,
)
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term

client = TestClient(app)


class _FailingLock:
    def __enter__(self):
        raise RuntimeError("Lock error")

    def __exit__(self, *args):
        pass


class _FailingList:
    def append(self, item):
        raise RuntimeError("Store list append failure")


@pytest.fixture(autouse=True)
def reset_stores():
    clear_ttl_cache()
    clear_long_term()
    yield
    clear_ttl_cache()
    clear_long_term()


def test_ttl_get_raises_lookup_returns_none():
    """TTL get raises -> _lookup_ttl_cache returns None (cache miss), no exception."""
    with patch("src.main.get_ttl_cached", side_effect=RuntimeError("Corrupt TTL cache state")):
        cached = _lookup_ttl_cache("Hôm nay có bao nhiêu lượt xe?")
        assert cached is None


def test_get_ttl_cached_internal_error_returns_none(monkeypatch):
    """get_ttl_cached handles internal errors gracefully, returning None."""
    monkeypatch.setattr("src.memory.ttl_cache._ttl_lock", _FailingLock())
    val = get_ttl_cached("any_key")
    assert val is None


def test_get_ttl_cached_corrupted_entry_shape_returns_none():
    """Corrupted entry in _ttl_cache does not crash get_ttl_cached."""
    key = make_cache_key("Câu hỏi kiểm tra corrupt")
    # Store invalid entry shape
    _ttl_cache[key] = "not a dict"  # type: ignore[assignment]
    assert get_ttl_cached(key) is None

    _ttl_cache[key] = {"expire_at": "invalid_time", "data": "foo"}  # type: ignore[dict-item]
    assert get_ttl_cached(key) is None


def test_ttl_get_fails_chat_still_200_when_agent_ok(monkeypatch):
    """TTL get fails -> /api/chat proceeds to agent and returns 200 with answer."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Hôm nay có bao nhiêu xe vào?",
        answer="Hôm nay có 120 xe vào cổng.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[120]], row_count=1),
        detail="query_data",
    )

    with patch("src.main.get_ttl_cached", side_effect=RuntimeError("Cache connection lost")), \
         patch("src.main.run_agent", return_value=mock_output):
        res = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu xe vào?"})

    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "Hôm nay có 120 xe vào cổng."
    assert data["row_count"] == 1


def test_ttl_set_raises_chat_and_ask_still_return_answer(monkeypatch):
    """TTL set raises -> /api/chat and /ask still return answers successfully."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Hôm nay có bao nhiêu xe vào?",
        answer="Tổng số 150 xe.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[150]], row_count=1),
        detail="query_data",
    )

    with patch("src.main.set_ttl_cached", side_effect=RuntimeError("Disk full / Cache write failed")), \
         patch("src.main.run_agent", return_value=mock_output):
        # /api/chat
        res_chat = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu xe vào?"})
        assert res_chat.status_code == 200
        assert res_chat.json()["answer"] == "Tổng số 150 xe."

        # /ask
        res_ask = client.post("/ask", json={"question": "Hôm nay có bao nhiêu xe vào?"})
        assert res_ask.status_code == 200
        assert res_ask.json()["answer"] == "Tổng số 150 xe."


def test_ttl_set_raises_in_stream_still_returns_answer(monkeypatch):
    """TTL set raises in /api/agent/stream -> SSE stream completes with __answer__ done."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Bao nhiêu xe hôm nay?",
        answer="Có 200 xe vào.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[200]], row_count=1),
        detail="query_data",
    )

    def fake_stream(*_args, **_kwargs):
        yield {"node_id": "recall", "status": "done"}
        yield {"__final_result__": mock_output}

    with patch("src.main.set_ttl_cached", side_effect=RuntimeError("Cache store error")), \
         patch("src.agent.graph.run_agent_stream", side_effect=fake_stream):
        res = client.post("/api/agent/stream", json={"question": "Bao nhiêu xe hôm nay?"})

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))

    ans = next(e for e in events if e.get("node_id") == "__answer__")
    assert ans.get("status") == "done"
    assert ans.get("output") == "Có 200 xe vào."


def test_set_ttl_cached_direct_swallows_exception(monkeypatch):
    """set_ttl_cached swallows internal exceptions and does not raise."""
    monkeypatch.setattr("src.memory.ttl_cache._ttl_lock", _FailingLock())
    # Must not raise
    set_ttl_cached("k", {"ans": "1"})


def test_recall_long_term_raises_recall_node_returns_empty_memories(monkeypatch):
    """recall_long_term raises -> recall_node returns empty memories, no exception, with degraded flag."""
    with patch("src.memory.longterm.recall_long_term", side_effect=RuntimeError("Qdrant cluster unavailable")):
        state = {
            "question": "Tôi phụ trách cổng số 1",
            "user_id": "u_test_degrade",
            "session_id": "sess_test",
        }
        res = recall_node(state)

    assert res["recalled_memories"] == []
    assert len(res["events"]) == 1
    ev = res["events"][0]
    assert ev["node_id"] == "recall"
    assert ev["output"]["recalled_memories"] == []
    assert ev["output"]["degraded"] is True
    assert "Qdrant" in ev["output"]["error"]


def test_recall_long_term_direct_hardened_against_exceptions():
    """recall_long_term itself catches unexpected exceptions and returns []."""
    with patch("src.memory.longterm._tokenize", side_effect=RuntimeError("Tokenize failure")):
        save_to_long_term("u1", "Some fact")
        res = recall_long_term("u1", "fact")
        assert res == []


def test_save_to_long_term_direct_hardened_against_exceptions(monkeypatch):
    """save_to_long_term catches unexpected exceptions and does not raise."""
    monkeypatch.setattr("src.memory.longterm._LONG_TERM_STORE", _FailingList())
    # Must not raise
    save_to_long_term("u1", "Fact")


def test_extract_and_store_memory_raises_run_store_extract_degraded():
    """extract_and_store_memory raises -> run_store_extract returns done event with degraded output, no raise."""
    with patch(
        "src.memory.extract.extract_and_store_memory",
        side_effect=RuntimeError("Database write deadlock"),
    ):
        events = run_store_extract(
            user_id="u_degrade",
            session_id="s_degrade",
            question="Tôi tên là Nam",
            result=Agent_Output(question="Tôi tên là Nam", answer="Chào Nam!"),
        )

    assert isinstance(events, list)
    assert len(events) >= 2
    done_ev = next(e for e in events if e.get("node_id") == "store_extract" and e.get("status") == "done")
    assert done_ev["output"]["extracted_memories"] == []
    assert done_ev["output"]["degraded"] is True
    assert "deadlock" in done_ev["output"]["error"].lower()


def test_stream_integration_recall_fail_agent_ok_store_extract_degraded(monkeypatch):
    """Integration: stream with recall fail + extract fail + agent OK -> answer status done, store degraded."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    with patch("src.memory.longterm.recall_long_term", side_effect=RuntimeError("Vector DB unavailable")), \
         patch("src.memory.extract.extract_and_store_memory", side_effect=RuntimeError("Store DB full")):
        res = client.post("/api/agent/stream", json={"question": "Hôm nay có bao nhiêu lượt xe vào?"})

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))

    # Graph executed and emitted __answer__
    answer_event = next((e for e in events if e.get("node_id") == "__answer__"), None)
    assert answer_event is not None
    assert answer_event.get("status") == "done"
    assert answer_event.get("output") != ""

    # Recall event had degraded output
    recall_event = next((e for e in events if e.get("node_id") == "recall" and e.get("status") == "done"), None)
    assert recall_event is not None
    assert recall_event.get("output", {}).get("degraded") is True
    assert recall_event.get("output", {}).get("recalled_memories") == []

    # Store extract had degraded output
    store_event = next((e for e in events if e.get("node_id") == "store_extract" and e.get("status") == "done"), None)
    assert store_event is not None
    assert store_event.get("output", {}).get("degraded") is True
    assert store_event.get("output", {}).get("extracted_memories") == []
