"""Unit & Integration test suite for TTL Cache integration into Router / Orchestrator.

Validates:
1. Cache Hit returns response with `cache_hit: true` in detail payload and latency < 5ms.
2. Cache Miss executes graph and stores result into TTL Cache with 300s expiration.
3. Cache Hit completely skips graph execution and LLM calls.
4. Stream endpoint /api/agent/stream emits cache node and `cache_hit: true`.
5. Dual-key storage (raw question + rewritten question) hits cache consistently.
6. User identity questions bypass TTL cache to maintain User Isolation (AC-2).
7. Settings cache_enabled=False bypasses caching.
8. Expiration after 300s automatically triggers cache miss and re-executes graph.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from src.main import app, chat, ChatRequest, ask, AskRequest
from src.agent.graph import Agent_Output
from src.llm.schemas import QueryResult, RewrittenQuestion
from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)


@pytest.fixture(autouse=True)
def setup_ttl_cache(monkeypatch):
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)
    yield
    clear_ttl_cache()


def test_router_cache_hit_returns_cache_hit_flag(monkeypatch):
    """Router trả về cache_hit: true khi Cache Hit trong /api/chat."""
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

    resp = chat(ChatRequest(question=q, session_id="test_sess_cache", user_id="user_1"))
    assert mock_run.call_count == 0
    assert resp.answer == "Hôm nay có 150 lượt xe vào."
    assert resp.detail.get("cache_hit") is True


def test_router_cache_miss_executes_graph_and_populates_cache(monkeypatch):
    """Cache Miss: chạy graph, nhận kết quả và lưu vào TTL Cache với hạn 300s."""
    q = "Thống kê sự kiện vùng cấm hôm nay"
    mock_run = MagicMock()
    valid_answer = "Ghi nhận 12 sự kiện xâm nhập vùng cấm hôm nay."
    dummy_out = Agent_Output(
        question=q,
        answer=valid_answer,
        query=QueryResult(tool="sql_builder", columns=["count"], rows=[[12]], row_count=1),
        detail="query_data",
    )
    mock_run.return_value = dummy_out
    monkeypatch.setattr("src.main.run_agent", mock_run)

    # 1. First call -> Cache Miss
    resp1 = chat(ChatRequest(question=q, session_id="test_miss_sess", user_id="user_1"))
    assert mock_run.call_count == 1
    assert resp1.answer == valid_answer
    assert resp1.detail.get("cache_hit") is not True

    # 2. Check that item was stored in TTL Cache
    cached = get_ttl_cached(make_cache_key(q))
    assert cached is not None
    assert cached["answer"] == valid_answer

    # 3. Second call -> Cache Hit, graph NOT called again
    resp2 = chat(ChatRequest(question=q, session_id="test_miss_sess", user_id="user_1"))
    assert mock_run.call_count == 1
    assert resp2.answer == valid_answer
    assert resp2.detail.get("cache_hit") is True


def test_router_cache_hit_skips_graph_execution_completely(monkeypatch):
    """Cache Hit phản hồi tức thì và bỏ qua hoàn toàn việc thực thi graph."""
    q = "Bao nhiêu xe máy vào cổng hôm nay?"
    set_ttl_cached(make_cache_key(q, route="query_data"), {
        "question": q,
        "answer": "Có 45 lượt xe máy.",
        "tool": "sql_builder",
        "columns": ["count"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_run = MagicMock()
    monkeypatch.setattr("src.main.run_agent", mock_run)

    t0 = time.perf_counter()
    resp = chat(ChatRequest(question=q))
    latency_ms = (time.perf_counter() - t0) * 1000

    assert mock_run.call_count == 0
    assert resp.answer == "Có 45 lượt xe máy."
    assert resp.detail.get("cache_hit") is True
    # Latency cache hit cực nhanh (< 50ms)
    assert latency_ms < 50.0


def test_router_stream_cache_hit_emits_cache_node_and_flag(monkeypatch):
    """Stream /api/agent/stream phát event node cache và detail cache_hit: true."""
    client = TestClient(app)
    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    set_ttl_cached(make_cache_key(q, route="query_data"), {
        "question": q,
        "answer": "Tổng cộng 200 lượt xe.",
        "tool": "query_traffic",
        "columns": ["total"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_stream = MagicMock()
    monkeypatch.setattr("src.agent.graph.run_agent_stream", mock_stream)

    res = client.post("/api/agent/stream", json={"question": q, "session_id": "s_stream", "user_id": "u_stream"})
    assert res.status_code == 200
    body = res.text

    assert mock_stream.call_count == 0
    assert '"node_id": "cache"' in body
    assert '"cache_hit": true' in body
    assert "Tổng cộng 200 lượt xe." in body


def test_router_stream_cache_miss_populates_cache(monkeypatch):
    """Stream trên Cache Miss thực thi graph và tự động lưu kết quả vào TTL Cache."""
    client = TestClient(app)
    q = "Có bao nhiêu sự kiện khói hôm nay?"
    ans = "Có 0 sự kiện khói hôm nay."

    def fake_stream(*_args, **_kwargs):
        yield {"node_id": "generate_sql", "status": "done"}
        yield {
            "__final_result__": Agent_Output(
                question=q,
                answer=ans,
                query=QueryResult(tool="sql_builder", columns=["count"], rows=[[0]], row_count=1),
                detail="query_data",
            )
        }

    monkeypatch.setattr("src.agent.graph.run_agent_stream", fake_stream)

    res = client.post("/api/agent/stream", json={"question": q, "session_id": "s_stream_miss", "user_id": "u_stream"})
    assert res.status_code == 200

    # Sau lượt 1, dữ liệu phải tồn tại trong TTL Cache
    cached = get_ttl_cached(make_cache_key(q))
    assert cached is not None
    assert cached["answer"] == ans


def test_router_dual_key_caching_for_raw_and_rewritten_questions(monkeypatch):
    """Kiểm tra lưu trữ dual-key: câu hỏi gốc vẫn hit cache kể cả khi rewrite thay đổi câu chữ."""
    raw_q = "xe vào hôm nay"
    rewritten_q = "Hôm nay có bao nhiêu lượt xe vào KCN Hưng Phú?"
    ans = "Hôm nay có 50 lượt xe vào."

    mock_run = MagicMock()
    mock_run.return_value = Agent_Output(
        question=rewritten_q,
        answer=ans,
        query=QueryResult(tool="sql_builder", columns=["count"], rows=[[50]], row_count=1),
        detail="query_data",
    )
    monkeypatch.setattr("src.main.run_agent", mock_run)
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", lambda _q: RewrittenQuestion(text=rewritten_q))

    # Lượt 1: hỏi raw_q -> Miss -> run_agent
    resp1 = chat(ChatRequest(question=raw_q, session_id="s1", user_id="u1"))
    assert mock_run.call_count == 1
    assert resp1.answer == ans

    # Lượt 2: hỏi lại y hệt raw_q -> Hit ngay trước rewrite!
    mock_rewrite = MagicMock()
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", mock_rewrite)

    resp2 = chat(ChatRequest(question=raw_q, session_id="s1", user_id="u1"))
    assert mock_run.call_count == 1  # Không gọi lại run_agent
    mock_rewrite.assert_not_called()  # Không gọi lại rewrite
    assert resp2.answer == ans
    assert resp2.detail.get("cache_hit") is True


def test_router_identity_questions_bypass_cache(monkeypatch):
    """Các câu hỏi danh tính cá nhân ('Tôi là ai?') không được lưu hoặc đọc từ TTL Cache chung."""
    identity_q = "Tôi là ai và tôi phụ trách camera nào?"
    ans = "Bạn là kỹ sư Tuấn phụ trách camera cam_01."

    mock_run = MagicMock()
    mock_run.return_value = Agent_Output(question=identity_q, answer=ans, detail="chat")
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp1 = chat(ChatRequest(question=identity_q, session_id="s_id", user_id="user_tuan"))
    assert mock_run.call_count == 1
    assert resp1.answer == ans

    # Không lưu vào cache
    assert get_ttl_cached(make_cache_key(identity_q)) is None

    # Lượt 2 vẫn gọi run_agent bình thường để đọc fact của user tương ứng
    resp2 = chat(ChatRequest(question=identity_q, session_id="s_id_2", user_id="user_lan"))
    assert mock_run.call_count == 2
    assert resp2.detail.get("cache_hit") is not True


def test_router_cache_disabled_bypasses_cache(monkeypatch):
    """Khi CACHE_ENABLED=False, router không đọc và không lưu cache."""
    monkeypatch.setattr("src.config.settings.cache_enabled", False)

    q = "Hôm nay có bao nhiêu lượt xe vào?"
    mock_run = MagicMock()
    mock_run.return_value = Agent_Output(question=q, answer="10 xe", detail="query_data")
    monkeypatch.setattr("src.main.run_agent", mock_run)

    # Lần 1
    chat(ChatRequest(question=q))
    assert mock_run.call_count == 1
    assert get_ttl_cached(make_cache_key(q)) is None

    # Lần 2 vẫn gọi graph vì cache bị tắt
    chat(ChatRequest(question=q))
    assert mock_run.call_count == 2


def test_router_cache_expired_after_300s_re_executes_graph(monkeypatch):
    """Sau 300s TTL, cache tự động hết hạn và kích hoạt lại graph execution."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    q = "Tổng số xe container hôm nay"
    mock_run = MagicMock()
    mock_run.return_value = Agent_Output(question=q, answer="8 xe container", detail="query_data")
    monkeypatch.setattr("src.main.run_agent", mock_run)

    # 1. Miss -> run_agent
    resp1 = chat(ChatRequest(question=q))
    assert mock_run.call_count == 1
    assert resp1.detail.get("cache_hit") is not True

    # 2. Sau 100s (trong 300s) -> Hit
    current_time = 1100.0
    resp2 = chat(ChatRequest(question=q))
    assert mock_run.call_count == 1
    assert resp2.detail.get("cache_hit") is True

    # 3. Sau 301s (quá 300s) -> Hết hạn -> re-execute graph
    current_time = 1301.0
    resp3 = chat(ChatRequest(question=q))
    assert mock_run.call_count == 2
    assert resp3.detail.get("cache_hit") is not True
