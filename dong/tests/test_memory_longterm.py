"""Unit tests for Phase 3b long-term memory store by user_id."""
from __future__ import annotations

import pytest

from src.memory import clear_long_term, recall_long_term, save_to_long_term


@pytest.fixture(autouse=True)
def clean_store():
    """Ensure in-memory long-term store is clean before and after each test."""
    clear_long_term()
    yield
    clear_long_term()


def test_save_and_recall_long_term_fact():
    """Save fact for user 'u1', recall with related query returns fact."""
    fact = "Người dùng ưu tiên theo dõi số lượng xe tải vào cổng chính"
    save_to_long_term("u1", fact)

    results = recall_long_term("u1", "xe tải cổng chính", k=3)
    assert len(results) >= 1
    assert results[0] == fact


def test_same_user_different_sessions_concept():
    """Same user_id, different session concept: recall still works (no session_id in longterm API)."""
    # Session 1: user configures a preference
    session_1_id = "session-login-day-1"  # simulated session concept
    save_to_long_term("u1", "Người dùng thích biểu đồ hình tròn khi xem tỷ lệ xe")

    # Session 2: new conversation session, same user
    session_2_id = "session-login-day-2"  # simulated another session concept
    recalled = recall_long_term("u1", "biểu đồ hình tròn")

    assert len(recalled) == 1
    assert "biểu đồ hình tròn" in recalled[0]


def test_user_isolation_u2_does_not_see_u1_facts():
    """User 'u2' does NOT see u1 facts."""
    save_to_long_term("u1", "Ghi chú bảo mật riêng của u1: trạm cân số 2")
    save_to_long_term("u2", "Ghi chú riêng của u2: cổng số 4")

    # u2 tries to query terms from u1's note
    u2_results = recall_long_term("u2", "bảo mật trạm cân số 2")
    for r in u2_results:
        assert "u1" not in r
        assert "trạm cân số 2" not in r

    # u1 tries to query terms from u2's note
    u1_results = recall_long_term("u1", "cổng số 4")
    for r in u1_results:
        assert "u2" not in r
        assert "cổng số 4" not in r


def test_empty_user_id_noop_or_empty():
    """Empty user_id -> save/recall no-op or empty list."""
    save_to_long_term("", "Dữ liệu không có user")
    save_to_long_term("   ", "Dữ liệu khoảng trắng user")

    assert recall_long_term("", "Dữ liệu") == []
    assert recall_long_term("   ", "Dữ liệu") == []


def test_empty_or_whitespace_fact_noop():
    """Empty or whitespace fact is skipped."""
    save_to_long_term("u1", "")
    save_to_long_term("u1", "   ")
    assert recall_long_term("u1", "anything") == []


def test_keyword_overlap_ranking():
    """Facts with higher keyword overlap with the query rank higher."""
    save_to_long_term("u1", "Cảnh báo hàng rào ảo khu vực kho A")
    save_to_long_term("u1", "Cảnh báo cháy nổ và khói tại bãi đỗ xe")

    # Query relates specifically to fire/smoke at parking
    results = recall_long_term("u1", "cháy nổ bãi đỗ xe", k=2)
    assert len(results) == 2
    assert "cháy nổ" in results[0]
