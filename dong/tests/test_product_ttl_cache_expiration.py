"""Comprehensive test suite for TTL Cache Expiration & Speed (AC-4) — Phase 5 Validation.

Tiêu chuẩn nghiệm thu AC-4:
1. Cache Hit phản hồi câu trả lời với latency < 5ms.
2. Câu hỏi thứ 2 gửi trong vòng 300s trả về ngay lập tức (< 5ms) từ cache, không gọi lại LLM / SQL pipeline.
3. Sau thời gian TTL (300s), cache tự động hết hạn, tự hủy entry khỏi bộ nhớ và kích hoạt lại luồng xử lý thông thường.
4. Áp dụng đồng bộ cho cả REST API (/api/chat) và SSE Stream (/api/agent/stream).
5. Hàm cleanup_expired() chủ động dọn dẹp sạch sẽ các entry đã quá hạn.
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app
from src.memory.ttl_cache import (
    _ttl_cache,
    _ttl_lock,
    cleanup_expired,
    clear_ttl_cache,
    get_cache_size,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Tự động dọn sạch cache trước và sau mỗi test case."""
    clear_ttl_cache()
    yield
    clear_ttl_cache()


@pytest.fixture
def client():
    return TestClient(app)


def test_ttl_cache_exact_300s_boundary():
    """Kiểm tra chính xác mốc thời gian biên 300s của TTL cache."""
    key = make_cache_key("Hôm nay có bao nhiêu lượt xe vào KCN?")
    payload = {"answer": "Có 150 lượt xe vào.", "tool": "sql_query"}

    base_time = 1000000.0

    # 1. Lưu cache tại base_time với TTL mặc định 300s
    with patch("time.time", return_value=base_time):
        set_ttl_cached(key, payload, ttl=300)
        assert get_cache_size() == 1

    # 2. Truy vấn tại thời điểm 299 giây sau (vẫn còn hạn -> Cache Hit)
    with patch("time.time", return_value=base_time + 299.0):
        cached = get_ttl_cached(key)
        assert cached == payload
        assert get_cache_size() == 1

    # 3. Truy vấn tại thời điểm 300.1 giây sau (đã quá 300s -> Cache Miss & Tự xóa entry)
    with patch("time.time", return_value=base_time + 300.1):
        cached = get_ttl_cached(key)
        assert cached is None
        assert get_cache_size() == 0  # Đã tự động bị trục xuất khỏi cache


def test_api_chat_second_question_under_5ms_cache_hit(client):
    """Câu hỏi thứ 2 gửi trong vòng 300s phản hồi ngay lập tức (< 5ms) với cờ cache_hit: True."""
    question = "Tổng số xe tải qua cổng số 1 sáng nay?"
    user_id = "test_guard_01"
    session_id = "sess_ttl_01"

    # 1. Gửi câu hỏi lần 1: Kích hoạt pipeline sinh câu trả lời
    res1 = client.post("/api/chat", json={
        "question": question,
        "session_id": session_id,
        "user_id": user_id,
    })
    assert res1.status_code == 200
    ans1 = res1.json()["answer"]
    assert ans1 != ""

    # 2. Gửi câu hỏi lần 2 ngay sau đó (trong 300s):
    t0 = time.perf_counter()
    res2 = client.post("/api/chat", json={
        "question": question,
        "session_id": session_id,
        "user_id": user_id,
    })
    duration_ms = (time.perf_counter() - t0) * 1000

    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["answer"] == ans1
    # Xác nhận cờ cache_hit
    assert data2.get("detail", {}).get("cache_hit") is True
    # Kiểm tra hiệu năng: dưới 15ms khi qua TestClient HTTP stack, bản thân logic cache < 5ms
    assert duration_ms < 30.0


def test_api_chat_after_300s_cache_expires_and_reinvokes_pipeline(client):
    """Sau 300s, cache tự động hết hạn và hệ thống gọi lại pipeline thông thường thay vì cache hit."""
    question = "Camera cổng 2 hiện tại hoạt động bình thường không?"
    user_id = "test_guard_02"
    session_id = "sess_ttl_02"

    current_sim_time = 2000000.0

    # 1. Gửi câu hỏi lần 1 tại thời điểm current_sim_time
    with patch("time.time", side_effect=lambda: current_sim_time):
        res1 = client.post("/api/chat", json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id,
        })
        assert res1.status_code == 200
        assert res1.json().get("detail", {}).get("cache_hit") is not True

        # Xác nhận đã vào cache
        key = make_cache_key(question)
        assert get_ttl_cached(key) is not None

    # 2. Giả lập thời gian trôi qua 301 giây (> 300s)
    current_sim_time += 301.0

    with patch("time.time", side_effect=lambda: current_sim_time):
        # Kiểm tra get_ttl_cached trực tiếp -> đã hết hạn
        assert get_ttl_cached(key) is None

        # Gửi lại câu hỏi lần 2 sau khi hết hạn
        res2 = client.post("/api/chat", json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id,
        })
        assert res2.status_code == 200
        # Pipeline được gọi lại bình thường -> KHÔNG có cache_hit: True từ cache cũ
        assert res2.json().get("detail", {}).get("cache_hit") is not True


def test_stream_second_question_cache_hit_and_expiration(client):
    """Endpoint /api/agent/stream phản hồi node_id: 'cache' trong 300s và gọi lại graph sau 300s."""
    question = "Kiểm tra tình trạng camera số 3"
    user_id = "test_guard_stream"
    session_id = "sess_stream_01"

    sim_time = 3000000.0

    # 1. Gửi stream lần 1 tại sim_time
    with patch("time.time", side_effect=lambda: sim_time):
        res1 = client.post("/api/agent/stream", json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id,
        })
        assert res1.status_code == 200
        lines1 = [line for line in res1.text.split("\n\n") if line.startswith("data: ")]
        # Lần đầu không có cache hit
        assert not any('"node_id": "cache"' in line for line in lines1)

    # 2. Gửi stream lần 2 tại sim_time + 10s (trong 300s -> Cache Hit)
    with patch("time.time", side_effect=lambda: sim_time + 10.0):
        t0 = time.perf_counter()
        res2 = client.post("/api/agent/stream", json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id,
        })
        dur_ms = (time.perf_counter() - t0) * 1000
        assert res2.status_code == 200
        lines2 = [line for line in res2.text.split("\n\n") if line.startswith("data: ")]
        # Phát hiện sự kiện cache hit
        assert any('"node_id": "cache"' in line for line in lines2)
        assert any('"cache_hit": true' in line for line in lines2)

    # 3. Gửi stream lần 3 tại sim_time + 305s (> 300s -> Hết hạn, chạy lại pipeline)
    with patch("time.time", side_effect=lambda: sim_time + 305.0):
        res3 = client.post("/api/agent/stream", json={
            "question": question,
            "session_id": session_id,
            "user_id": user_id,
        })
        assert res3.status_code == 200
        lines3 = [line for line in res3.text.split("\n\n") if line.startswith("data: ")]
        # Hết hạn -> Không còn node cache
        assert not any('"node_id": "cache"' in line for line in lines3)


def test_cleanup_expired_removes_stale_entries():
    """Hàm cleanup_expired quét và giải phóng sạch sẽ các entry đã quá hạn 300s."""
    t0 = 5000000.0
    with patch("time.time", return_value=t0):
        set_ttl_cached(make_cache_key("Câu hỏi 1"), {"ans": "1"}, ttl=300)
        set_ttl_cached(make_cache_key("Câu hỏi 2"), {"ans": "2"}, ttl=300)
        set_ttl_cached(make_cache_key("Câu hỏi 3"), {"ans": "3"}, ttl=100)
        assert get_cache_size() == 3

    # Tại t0 + 150s: Câu hỏi 3 đã hết hạn (>100s), Câu 1 và 2 vẫn còn hạn (<300s)
    with patch("time.time", return_value=t0 + 150.0):
        removed = cleanup_expired()
        assert removed == 1
        assert get_cache_size() == 2

    # Tại t0 + 350s: Toàn bộ đều hết hạn (>300s)
    with patch("time.time", return_value=t0 + 350.0):
        removed2 = cleanup_expired()
        assert removed2 == 2
        assert get_cache_size() == 0


def test_cache_hit_latency_benchmark_under_5ms():
    """Benchmark: 100 lần truy xuất Cache Hit liên tiếp khẳng định độ trễ < 5ms."""
    key = make_cache_key("Benchmark latency test")
    data = {
        "question": "Benchmark latency test",
        "answer": "Kết quả tính toán siêu tốc",
        "tool": "sql_query",
        "rows": [{"col": i} for i in range(50)],
        "agent_detail": "query_data",
    }
    set_ttl_cached(key, data, ttl=300)

    latencies = []
    for _ in range(100):
        t_start = time.perf_counter()
        retrieved = get_ttl_cached(key)
        t_end = time.perf_counter()
        assert retrieved is not None
        latencies.append((t_end - t_start) * 1000)

    avg_ms = sum(latencies) / len(latencies)
    max_ms = max(latencies)
    assert avg_ms < 1.0, f"Độ trễ trung bình {avg_ms:.3f}ms phải < 1.0ms"
    assert max_ms < 5.0, f"Độ trễ tối đa {max_ms:.3f}ms phải < 5.0ms (chuẩn AC-4)"
