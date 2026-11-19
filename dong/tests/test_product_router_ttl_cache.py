"""Unit & Integration test suite for TTL Cache integration into Router / Orchestrator."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.domain.agents.graph import Agent_Output
from src.infra.llm.schemas import QueryResult
from src.infra.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)
from src.main import app
from tests.helpers_stream import post_stream, sse_answer


@pytest.fixture(autouse=True)
def setup_ttl_cache(monkeypatch):
    clear_ttl_cache()
    monkeypatch.setattr("src.shared.settings.settings.cache_enabled", True)
    monkeypatch.setattr("src.shared.settings.settings.memory_ttl_seconds", 300)
    monkeypatch.setattr("src.shared.settings.settings.iam_required", False)
    monkeypatch.setattr("src.shared.settings.settings.api_access_key", "")
    yield
    clear_ttl_cache()


@pytest.fixture
def client():
    return TestClient(app)


def _fake_final(q: str, answer: str, *, detail: str = "query_data", query=None):
    def fake_stream(*_args, **_kwargs):
        yield {"node_id": "generate_sql", "status": "done"}
        yield {
            "__final_result__": Agent_Output(
                question=q,
                answer=answer,
                query=query,
                detail=detail,
            )
        }

    return fake_stream


def test_router_cache_hit_skips_graph(monkeypatch, client):
    """Cache Hit: stream không gọi graph."""
    q = "Hôm nay có bao nhiêu lượt xe vào?"
    set_ttl_cached(
        make_cache_key(q, route="query_data"),
        {
            "question": q,
            "answer": "Hôm nay có 150 lượt xe vào.",
            "tool": "query_traffic",
            "columns": ["so_luot"],
            "row_count": 1,
            "agent_detail": "query_data",
        },
    )
    mock_stream = MagicMock()
    monkeypatch.setattr("src.main.run_agent_stream", mock_stream)
    res = post_stream(client, q)
    assert res.status_code == 200
    assert mock_stream.call_count == 0
    assert sse_answer(res) == "Hôm nay có 150 lượt xe vào."


def test_router_cache_miss_executes_graph_and_populates_cache(monkeypatch, client):
    q = "Thống kê sự kiện vùng cấm hôm nay"
    valid_answer = "Ghi nhận 12 sự kiện xâm nhập vùng cấm hôm nay."
    monkeypatch.setattr(
        "src.main.run_agent_stream",
        _fake_final(
            q,
            valid_answer,
            query=QueryResult(tool="sql_builder", columns=["count"], rows=[[12]], row_count=1),
        ),
    )

    res1 = post_stream(client, q)
    assert res1.status_code == 200
    assert sse_answer(res1) == valid_answer
    cached = get_ttl_cached(make_cache_key(q))
    assert cached is not None
    assert cached["answer"] == valid_answer

    mock_stream = MagicMock()
    monkeypatch.setattr("src.main.run_agent_stream", mock_stream)
    res2 = post_stream(client, q)
    assert mock_stream.call_count == 0
    assert sse_answer(res2) == valid_answer


def test_router_cache_hit_skips_graph_execution_completely(monkeypatch, client):
    monkeypatch.setattr("src.application.agent_turn.persist_session_turn", lambda **_: None)
    q = "Bao nhiêu xe máy vào cổng hôm nay?"
    set_ttl_cached(
        make_cache_key(q, route="query_data"),
        {
            "question": q,
            "answer": "Có 45 lượt xe máy.",
            "tool": "sql_builder",
            "columns": ["count"],
            "row_count": 1,
            "agent_detail": "query_data",
        },
    )
    mock_stream = MagicMock()
    monkeypatch.setattr("src.main.run_agent_stream", mock_stream)
    t0 = time.perf_counter()
    res = post_stream(client, q, user_id="u_fast")
    latency_ms = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    assert mock_stream.call_count == 0
    assert sse_answer(res) == "Có 45 lượt xe máy."
    assert latency_ms < 50.0


def test_router_stream_cache_hit_emits_cache_node_and_flag(monkeypatch, client):
    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    set_ttl_cached(
        make_cache_key(q, route="query_data"),
        {
            "question": q,
            "answer": "Tổng cộng 200 lượt xe.",
            "tool": "query_traffic",
            "columns": ["total"],
            "row_count": 1,
            "agent_detail": "query_data",
        },
    )
    mock_stream = MagicMock()
    monkeypatch.setattr("src.domain.agents.graph.run_agent_stream", mock_stream)
    res = post_stream(client, q, session_id="s_stream", user_id="u_stream")
    assert res.status_code == 200
    body = res.text
    assert mock_stream.call_count == 0
    assert '"node_id": "cache"' in body
    assert '"cache_hit": true' in body
    assert "Tổng cộng 200 lượt xe." in body


def test_router_stream_cache_miss_populates_cache(monkeypatch, client):
    q = "Có bao nhiêu sự kiện khói hôm nay?"
    ans = "Có 0 sự kiện khói hôm nay."
    monkeypatch.setattr(
        "src.domain.agents.graph.run_agent_stream",
        _fake_final(
            q,
            ans,
            query=QueryResult(tool="sql_builder", columns=["count"], rows=[[0]], row_count=1),
        ),
    )
    res = post_stream(client, q, session_id="s_stream_miss", user_id="u_stream")
    assert res.status_code == 200
    cached = get_ttl_cached(make_cache_key(q))
    assert cached is not None
    assert cached["answer"] == ans


def test_router_dual_key_caching_for_raw_and_rewritten_questions(monkeypatch, client):
    raw_q = "xe vào hôm nay"
    rewritten_q = "Hôm nay có bao nhiêu lượt xe vào KCN Hưng Phú?"
    ans = "Hôm nay có 50 lượt xe vào."

    def fake_stream(*_args, **_kwargs):
        yield {
            "__final_result__": Agent_Output(
                question=rewritten_q,
                answer=ans,
                query=QueryResult(tool="sql_builder", columns=["count"], rows=[[50]], row_count=1),
                detail="query_data",
            )
        }

    mock_stream = MagicMock(side_effect=fake_stream)
    monkeypatch.setattr("src.main.run_agent_stream", mock_stream)
    res1 = post_stream(client, raw_q)
    assert mock_stream.call_count == 1
    assert sse_answer(res1) == ans

    mock_stream2 = MagicMock()
    monkeypatch.setattr("src.main.run_agent_stream", mock_stream2)
    res2 = post_stream(client, raw_q)
    assert mock_stream2.call_count == 0
    assert sse_answer(res2) == ans


def test_router_identity_questions_bypass_cache(monkeypatch, client):
    identity_q = "Tôi là ai và tôi phụ trách camera nào?"
    ans = "Bạn là kỹ sư Tuấn phụ trách camera cam_01."
    calls = {"n": 0}

    def fake_stream(*_args, **_kwargs):
        calls["n"] += 1
        yield {"__final_result__": Agent_Output(question=identity_q, answer=ans, detail="chat")}

    monkeypatch.setattr("src.main.run_agent_stream", fake_stream)
    res1 = post_stream(client, identity_q, user_id="user_tuan")
    assert calls["n"] == 1
    assert sse_answer(res1) == ans
    assert get_ttl_cached(make_cache_key(identity_q)) is None
    res2 = post_stream(client, identity_q, user_id="user_lan")
    assert calls["n"] == 2
    assert sse_answer(res2) == ans


def test_router_cache_disabled_bypasses_cache(monkeypatch, client):
    monkeypatch.setattr("src.shared.settings.settings.cache_enabled", False)
    q = "Hôm nay có bao nhiêu lượt xe vào?"
    calls = {"n": 0}

    def fake_stream(*_args, **_kwargs):
        calls["n"] += 1
        yield {"__final_result__": Agent_Output(question=q, answer="10 xe", detail="query_data")}

    monkeypatch.setattr("src.main.run_agent_stream", fake_stream)
    post_stream(client, q)
    assert calls["n"] == 1
    assert get_ttl_cached(make_cache_key(q)) is None
    post_stream(client, q)
    assert calls["n"] == 2


def test_router_cache_expired_after_300s_re_executes_graph(monkeypatch, client):
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    q = "Tổng số xe container hôm nay"
    calls = {"n": 0}

    def fake_stream(*_args, **_kwargs):
        calls["n"] += 1
        yield {
            "__final_result__": Agent_Output(
                question=q, answer="8 xe container", detail="query_data"
            )
        }

    monkeypatch.setattr("src.main.run_agent_stream", fake_stream)
    res1 = post_stream(client, q)
    assert calls["n"] == 1
    current_time = 1100.0
    res2 = post_stream(client, q)
    assert calls["n"] == 1
    assert sse_answer(res2) == sse_answer(res1)
    current_time = 1301.0
    post_stream(client, q)
    assert calls["n"] == 2
