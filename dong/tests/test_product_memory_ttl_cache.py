"""Unit tests for TTL Response Cache (src/memory/ttl_cache.py).

Kiểm thử:
1. Băm SHA-256 chuẩn hóa câu hỏi và route (make_cache_key)
2. Cache Hit & Miss trong thời hạn TTL 300s
3. Tự động hết hạn và dọn dẹp entry quá hạn (cleanup_expired)
4. Tôn trọng cấu hình TTL_CACHE_ENABLED và MEMORY_TTL_SECONDS
5. Tra cứu prefix linh hoạt khi query không chỉ định route
6. Đảm bảo an toàn đa luồng (Thread-safety với threading.Lock)
7. Đạt chuẩn hiệu năng: Latency cache hit < 5ms (AC-4)
8. Graceful degradation: Không crash khi dữ liệu cache bị lỗi
"""
from __future__ import annotations

import concurrent.futures
import time
from unittest.mock import patch

import pytest

from src.config import settings
from src.memory.ttl_cache import (
    cleanup_expired,
    clear_ttl_cache,
    get_cache_size,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
)


@pytest.fixture(autouse=True)
def clean_cache():
    """Tự động dọn sạch cache trước và sau mỗi ca kiểm thử."""
    clear_ttl_cache()
    yield
    clear_ttl_cache()


def test_make_cache_key_normalization():
    """Chuẩn hóa khoảng trắng, chữ hoa/thường để tạo cùng 1 mã hash SHA-256."""
    k1 = make_cache_key("  Hôm nay có bao nhiêu xe?  ")
    k2 = make_cache_key("hôm nay có bao nhiêu xe?")
    assert k1 == k2
    assert len(k1) == 64  # SHA-256 hex length

    # Khác câu hỏi -> khác key
    k3 = make_cache_key("Camera cổng số 1 ở đâu?")
    assert k1 != k3


def test_make_cache_key_with_route():
    """Khi có route, sinh key dạng q_hash:r_hash."""
    k_no_route = make_cache_key("Báo cáo giao thông")
    k_route = make_cache_key("Báo cáo giao thông", route="query_data")
    assert ":" in k_route
    assert k_route.startswith(k_no_route)


def test_ttl_cache_hit_and_miss():
    """Lưu và lấy lại dữ liệu khi còn hạn (Hit), lấy key chưa có (Miss)."""
    key = make_cache_key("Hôm nay có bao nhiêu lượt xe?")
    data = {"answer": "Có 120 lượt xe.", "chart": None}

    set_ttl_cached(key, data, ttl=300)
    assert get_cache_size() == 1

    # Cache Hit
    cached = get_ttl_cached(key)
    assert cached == data

    # Cache Miss
    miss_key = make_cache_key("Câu hỏi chưa từng hỏi")
    assert get_ttl_cached(miss_key) is None


def test_ttl_cache_expires_after_ttl():
    """Cache tự động hết hạn và xóa entry sau thời gian TTL."""
    key = make_cache_key("Thời tiết KCN")
    data = {"answer": "Nhiệt độ 28 độ C."}

    # Set TTL ngắn 0.1s
    set_ttl_cached(key, data, ttl=0.1)
    assert get_ttl_cached(key) == data

    # Đợi hết hạn
    time.sleep(0.15)
    assert get_ttl_cached(key) is None
    assert get_cache_size() == 0


def test_cleanup_expired_sweeps_stale_entries():
    """cleanup_expired chủ động quét và xóa sạch các entry hết hạn."""
    k1 = make_cache_key("Câu 1")
    k2 = make_cache_key("Câu 2")

    set_ttl_cached(k1, {"a": 1}, ttl=0.1)
    set_ttl_cached(k2, {"a": 2}, ttl=300)

    time.sleep(0.15)
    removed = cleanup_expired()
    assert removed == 1
    assert get_cache_size() == 1
    assert get_ttl_cached(k2) == {"a": 2}


def test_ttl_cache_disabled_when_flag_false(monkeypatch):
    """Khi ttl_cache_enabled=False, get trả về None và set là no-op."""
    monkeypatch.setattr(settings, "memory_enabled", False)
    key = make_cache_key("Test disabled")
    set_ttl_cached(key, {"answer": "X"})
    assert get_ttl_cached(key) is None
    assert get_cache_size() == 0


def test_ttl_cache_disabled_when_ttl_zero_or_negative(monkeypatch):
    """Khi memory_ttl_seconds <= 0, cache tự động vô hiệu hóa."""
    monkeypatch.setattr(settings, "memory_ttl_seconds", 0)
    key = make_cache_key("Test 0s")
    set_ttl_cached(key, {"answer": "X"})
    assert get_ttl_cached(key) is None


def test_prefix_lookup_without_route():
    """Nếu lưu kèm route, khi tra cứu chỉ bằng câu hỏi vẫn match prefix."""
    key_with_route = make_cache_key("Tra cứu camera", route="query_data")
    key_question_only = make_cache_key("Tra cứu camera")

    set_ttl_cached(key_with_route, {"answer": "Cam 01 active"}, ttl=300)

    # Tra cứu bằng question_only key
    result = get_ttl_cached(key_question_only)
    assert result == {"answer": "Cam 01 active"}


def test_thread_safety_concurrent_access():
    """An toàn đa luồng khi nhiều thread đọc/ghi đồng thời với threading.Lock."""
    key = make_cache_key("Concurrent Key")
    set_ttl_cached(key, {"count": 0}, ttl=300)

    def worker(idx: int):
        k = make_cache_key(f"Question {idx % 5}")
        set_ttl_cached(k, {"val": idx}, ttl=300)
        return get_ttl_cached(k)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(40)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 40
    assert all(r is not None for r in results)


def test_ttl_cache_latency_under_5ms():
    """Xác nhận độ trễ Cache Hit < 5ms tuân thủ tiêu chuẩn AC-4."""
    key = make_cache_key("Đo độ trễ phản hồi")
    data = {"answer": "Nội dung phản hồi siêu tốc", "items": list(range(100))}
    set_ttl_cached(key, data, ttl=300)

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = get_ttl_cached(key)
        t1 = time.perf_counter()
        assert res is not None
        latencies.append((t1 - t0) * 1000)  # ms

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    assert avg_latency < 1.0  # Thông thường < 0.1ms trên RAM
    assert max_latency < 5.0  # Tuyệt đối < 5ms theo AC-4


def test_ttl_cache_graceful_degradation_corrupted_entry():
    """Khi cấu trúc entry trong cache bị sai lệch, không crash mà fallback miss an toàn."""
    from src.memory.ttl_cache import _ttl_cache, _ttl_lock

    with _ttl_lock:
        _ttl_cache["bad_key"] = "not_a_dict"  # Sai kiểu dữ liệu

    res = get_ttl_cached("bad_key")
    assert res is None
