"""Unit tests for Phase 1: PostgreSQL Memory DB initialization & connection management."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.memory.db import (
    DDL_CREATE_USER_MEMORIES,
    get_memory_connection,
    init_memory_db,
    is_postgres_configured,
)


def test_is_postgres_configured(monkeypatch):
    """is_postgres_configured returns True only when both DB_HOST and DB_USER are present."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "localhost")
    monkeypatch.setattr("src.memory.db.settings.db_user", "postgres")
    assert is_postgres_configured() is True

    monkeypatch.setattr("src.memory.db.settings.db_host", "")
    assert is_postgres_configured() is False


def test_get_memory_connection_unconfigured_raises(monkeypatch):
    """get_memory_connection raises RuntimeError if PostgreSQL is not configured."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "")
    monkeypatch.setattr("src.memory.db.settings.db_user", "")

    with pytest.raises(RuntimeError, match="PostgreSQL chưa được cấu hình"):
        with get_memory_connection():
            pass


def test_init_memory_db_unconfigured_returns_false(monkeypatch):
    """When PostgreSQL is unconfigured, init_memory_db logs info and returns False safely."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "")
    monkeypatch.setattr("src.memory.db.settings.db_user", "")

    result = init_memory_db()
    assert result is False


def test_init_memory_db_connect_error_returns_false_safely(monkeypatch):
    """When connection raises an error, init_memory_db catches it, logs warning, returns False."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "invalid_host")
    monkeypatch.setattr("src.memory.db.settings.db_user", "postgres")

    with patch("psycopg2.connect", side_effect=Exception("Connection refused")):
        result = init_memory_db()
        assert result is False


def test_init_memory_db_success(monkeypatch):
    """When DB is available, init_memory_db executes DDL and returns True."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "localhost")
    monkeypatch.setattr("src.memory.db.settings.db_user", "postgres")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg2.connect", return_value=mock_conn):
        result = init_memory_db()
        assert result is True
        mock_cursor.execute.assert_called_once_with(DDL_CREATE_USER_MEMORIES)


# ── Long-Term Memory & Persistence Tests (Phase 3) ──────────────────────────
from datetime import datetime, timezone
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term


def test_save_and_recall_long_term_postgres(monkeypatch):
    """When PostgreSQL is configured and active, save_to_long_term inserts to DB and recall queries DB."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock DB return row: (fact, created_at)
    now_dt = datetime.now(timezone.utc)
    mock_cursor.fetchall.return_value = [
        ("Tôi thích giám sát camera cổng số 1", now_dt),
        ("Tôi phụ trách an ninh ca đêm", now_dt),
    ]

    with patch("src.memory.longterm.get_memory_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        save_to_long_term("user_123", "Tôi thích giám sát camera cổng số 1", category="preference")
        assert mock_cursor.execute.called

        recalled = recall_long_term("user_123", "hôm nay xem camera cổng 1 nhé", k=1)
        assert len(recalled) == 1
        assert "cổng số 1" in recalled[0]


def test_user_isolation_strictly_enforced_in_memory(monkeypatch):
    """Facts of user_A must never be leaked or visible to user_B in memory store."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: False)
    clear_long_term()

    save_to_long_term("user_A", "Tôi tên là Nguyễn Văn An")
    save_to_long_term("user_B", "Tôi tên là Trần Thị Bình")

    res_a = recall_long_term("user_A", "tôi tên là gì")
    assert any("Nguyễn Văn An" in f for f in res_a)
    assert not any("Trần Thị Bình" in f for f in res_a)

    res_b = recall_long_term("user_B", "tôi tên là gì")
    assert any("Trần Thị Bình" in f for f in res_b)
    assert not any("Nguyễn Văn An" in f for f in res_b)


def test_fallback_to_in_memory_when_db_down(monkeypatch):
    """When PostgreSQL raises a connection error, save and recall gracefully fallback to in-memory without raising."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)
    clear_long_term()

    with patch("src.memory.longterm.get_memory_connection", side_effect=Exception("DB Connection timeout")):
        # Must not raise exception
        save_to_long_term("user_fb", "Người dùng ưu tiên xem camera ngã tư")
        facts = recall_long_term("user_fb", "ưu tiên camera gì")
        assert len(facts) >= 1
        assert "ngã tư" in facts[0]


def test_clear_long_term_by_user_postgres(monkeypatch):
    """clear_long_term deletes from DB by user_id or all when user_id is None."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.memory.longterm.get_memory_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        clear_long_term("user_123")
        assert any("DELETE FROM user_memories WHERE user_id = %s" in str(call) for call in mock_cursor.execute.call_args_list)

        mock_cursor.reset_mock()
        clear_long_term(None)
        assert any("DELETE FROM user_memories;" in str(call) for call in mock_cursor.execute.call_args_list)


def test_clean_code_no_qdrant_or_vector():
    """Verify that legacy Qdrant imports and dummy vector=[0.0] are completely eliminated."""
    import inspect
    import src.memory.longterm as lt_mod

    source = inspect.getsource(lt_mod)
    assert "vector=[0.0]" not in source
    assert "qdrant" not in source.lower()

