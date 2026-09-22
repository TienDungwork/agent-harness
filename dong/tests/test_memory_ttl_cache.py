"""Unit tests for Phase 3b: TTL Response Cache 300s."""

from __future__ import annotations

import time
import pytest

from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
    _ttl_cache,
)


def test_make_cache_key_normalization_and_different_routes():
    """make_cache_key normalizes question and generates different keys for different routes."""
    k1 = make_cache_key("  Hôm Nay Có Bao Nhiêu Xe Vào?  ")
    k2 = make_cache_key("hôm nay có bao nhiêu xe vào?")
    assert k1 == k2

    k_stat = make_cache_key("hôm nay có bao nhiêu xe vào?", route="query_data")
    k_docs = make_cache_key("hôm nay có bao nhiêu xe vào?", route="docs")
    assert k_stat != k_docs
    assert k1 != k_stat
    assert k1 != k_docs


def test_ttl_cache_hit_within_300s(monkeypatch):
    """Entry stored in TTL cache hits successfully within 300s duration."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    payload = {"question": "Hôm nay có bao nhiêu xe vào?", "answer": "Có 150 xe", "row_count": 1}
    set_ttl_cached(key, payload)

    # Fast forward to 299s (within 300s)
    current_time = 1299.0
    cached = get_ttl_cached(key)
    assert cached is not None
    assert cached["answer"] == "Có 150 xe"
    assert cached["row_count"] == 1


def test_ttl_cache_miss_after_expire(monkeypatch):
    """Entry expires after 300s and get_ttl_cached returns None and cleans up."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    payload = {"answer": "Có 150 xe"}
    set_ttl_cached(key, payload)

    assert get_ttl_cached(key) is not None

    # Advance past 300s
    current_time = 1301.0
    cached = get_ttl_cached(key)
    assert cached is None


def test_ttl_cache_disabled_cache_enabled_false(monkeypatch):
    """When CACHE_ENABLED is false, cache operations are disabled."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", False)

    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    set_ttl_cached(key, {"answer": "test"})
    assert get_ttl_cached(key) is None


def test_ttl_cache_disabled_when_memory_ttl_zero_or_negative(monkeypatch):
    """When memory_ttl_seconds <= 0, cache returns None and does not store."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 0)

    key = make_cache_key("test zero ttl")
    set_ttl_cached(key, {"answer": "val"})
    assert get_ttl_cached(key) is None


def test_ttl_cache_same_question_hits_before_graph_with_stored_route(monkeypatch):
    """When stored with route after graph, checking before graph (without route) hits cache."""
    current_time = 5000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    question = "Thống kê xe IN hôm nay"
    # Stored after graph with route="query_data"
    store_key = make_cache_key(question, route="query_data")
    data = {"question": question, "answer": "Tổng cộng 20 xe vào.", "tool": "query_traffic"}
    set_ttl_cached(store_key, data)

    # Hit before graph with make_cache_key(question) (no route)
    check_key = make_cache_key(question)
    cached = get_ttl_cached(check_key)
    assert cached is not None
    assert cached["answer"] == "Tổng cộng 20 xe vào."


def test_ttl_cache_clear():
    """clear_ttl_cache removes all entries from the store."""
    clear_ttl_cache()
    set_ttl_cached(make_cache_key("q1"), {"answer": "1"})
    set_ttl_cached(make_cache_key("q2"), {"answer": "2"})
    assert len(_ttl_cache) >= 2

    clear_ttl_cache()
    assert len(_ttl_cache) == 0
    assert get_ttl_cached(make_cache_key("q1")) is None
    assert get_ttl_cached(make_cache_key("q2")) is None


def test_ttl_cache_disabled_via_ttl_cache_enabled_property(monkeypatch):
    """Setting ttl_cache_enabled=False disables cache retrieval and setting."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.ttl_cache_enabled", False)

    key = make_cache_key("test question")
    set_ttl_cached(key, {"answer": "cached"})
    assert get_ttl_cached(key) is None


def test_chat_cache_hit_before_graph(monkeypatch):
    """Chat endpoint hits TTL cache before graph execution and sets cache_hit=True."""
    from unittest.mock import MagicMock
    from src.main import chat, ChatRequest

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    # Pre-populate cache (simulating prior graph run with route)
    q = "Hôm nay có bao nhiêu lượt xe vào?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Hôm nay có 150 lượt xe vào.",
        "tool": "query_traffic",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_run = MagicMock()
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = chat(ChatRequest(question=q))
    assert mock_run.call_count == 0
    assert resp.answer == "Hôm nay có 150 lượt xe vào."
    assert resp.detail.get("cache_hit") is True


def test_cache_hit_skips_rewrite_when_llm_fails(monkeypatch):
    """TTL hit trước rewrite — LLM lỗi vẫn trả 200, không 503."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from src.main import app, chat, ChatRequest

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào?"
    set_ttl_cached(make_cache_key(q, route="query_data"), {
        "question": q,
        "answer": "Hôm nay có 100 lượt xe vào.",
        "tool": "sql_builder",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    def boom(*_args, **_kwargs):
        raise TimeoutError("LLM gateway timeout")

    monkeypatch.setattr("src.agent.rewrite.rewrite_question", boom)
    mock_run = MagicMock()
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = chat(ChatRequest(question=q))
    assert mock_run.call_count == 0
    assert resp.answer == "Hôm nay có 100 lượt xe vào."
    assert resp.detail.get("cache_hit") is True

    client = TestClient(app)
    stream_res = client.post("/api/agent/stream", json={"question": q})
    assert stream_res.status_code == 200
    assert '"node_id": "cache"' in stream_res.text
    assert mock_run.call_count == 0


def test_stream_agent_cache_hit_before_graph(monkeypatch):
    """Stream endpoint hits TTL cache before graph execution and yields cache node."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from src.main import app

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Tổng cộng 200 lượt xe.",
        "tool": "query_traffic",
        "columns": ["total"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_stream = MagicMock()
    monkeypatch.setattr("src.agent.graph.run_agent_stream", mock_stream)

    client = TestClient(app)
    res = client.post("/api/agent/stream", json={"question": q})
    assert res.status_code == 200
    body = res.text

    assert mock_stream.call_count == 0
    assert '"node_id": "cache"' in body
    assert '"cache_hit": true' in body
    assert "Tổng cộng 200 lượt xe." in body
