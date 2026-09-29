"""Unit tests for Short-Term Memory Checkpointer (src/memory/shortterm.py).

Kiểm thử:
1. Trạng thái bật/tắt (settings.short_term_memory_enabled)
2. Singleton pattern và thread-safety
3. Graceful degradation: Fallback MemorySaver khi DB chưa cấu hình hoặc ngắt kết nối
4. PostgresSaver checkpointer khi PostgreSQL sẵn sàng
5. Reset checkpointer và giải phóng tài nguyên
6. Đảm bảo cô lập dữ liệu theo thread_id / session_id
"""
from __future__ import annotations

import concurrent.futures
from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver, empty_checkpoint
from langgraph.checkpoint.memory import MemorySaver

from src.config import settings
from src.memory.shortterm import (
    get_checkpointer,
    is_using_postgres_checkpointer,
    reset_checkpointer,
)


@pytest.fixture(autouse=True)
def clean_checkpointer():
    """Tự động dọn dẹp và reset checkpointer trước và sau mỗi ca test."""
    reset_checkpointer()
    yield
    reset_checkpointer()


def test_get_checkpointer_disabled(monkeypatch):
    """Khi short_term_memory_enabled=False, get_checkpointer trả về None."""
    monkeypatch.setattr(settings, "memory_enabled", False)
    assert settings.short_term_memory_enabled is False
    assert get_checkpointer() is None


def test_get_checkpointer_memory_saver_singleton_when_db_not_configured(monkeypatch):
    """Khi PostgreSQL không cấu hình, get_checkpointer trả về MemorySaver singleton."""
    monkeypatch.setattr(settings, "db_host", "")
    cp1 = get_checkpointer()
    cp2 = get_checkpointer()

    assert cp1 is not None
    assert cp1 is cp2
    assert isinstance(cp1, MemorySaver)
    assert isinstance(cp1, BaseCheckpointSaver)
    assert is_using_postgres_checkpointer() is False


def test_get_checkpointer_fallback_on_db_exception(monkeypatch):
    """Khi kết nối PostgreSQL bị lỗi (timeout/network down), tự động fallback MemorySaver an toàn."""
    monkeypatch.setattr(settings, "db_host", "192.0.2.1")
    monkeypatch.setattr(settings, "db_user", "postgres")

    with patch("src.memory.shortterm._create_postgres_checkpointer", side_effect=Exception("Database down")):
        cp = get_checkpointer()
        assert cp is not None
        assert isinstance(cp, MemorySaver)
        assert is_using_postgres_checkpointer() is False


def test_get_checkpointer_postgres_success(monkeypatch):
    """Khi PostgreSQL kết nối thành công, PostgresSaver được khởi tạo và chạy .setup()."""
    monkeypatch.setattr(settings, "db_host", "localhost")
    monkeypatch.setattr(settings, "db_user", "postgres")

    mock_pool = MagicMock()
    mock_saver = MagicMock()
    mock_saver.setup = MagicMock()

    class FakePostgresSaver(BaseCheckpointSaver):
        pass

    FakePostgresSaver.__name__ = "PostgresSaver"
    mock_saver.__class__ = FakePostgresSaver

    with patch("psycopg_pool.ConnectionPool", return_value=mock_pool), \
         patch("langgraph.checkpoint.postgres.PostgresSaver", return_value=mock_saver):

        cp = get_checkpointer()
        assert cp is mock_saver
        mock_saver.setup.assert_called_once()
        assert is_using_postgres_checkpointer() is True


def test_reset_checkpointer_closes_pool_and_resets():
    """reset_checkpointer đóng pool kết nối và dọn sạch singleton."""
    mock_pool = MagicMock()
    with patch("src.memory.shortterm._pool_instance", mock_pool):
        reset_checkpointer()
        mock_pool.close.assert_called_once()

    # Sau khi reset, gọi lại tạo instance mới
    cp_new = get_checkpointer()
    assert cp_new is not None


def test_thread_safety_checkpointer_singleton(monkeypatch):
    """Nhiều thread gọi get_checkpointer đồng thời phải nhận về cùng 1 singleton."""
    monkeypatch.setattr(settings, "db_host", "")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(get_checkpointer) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    assert len(results) == 20
    first = results[0]
    for cp in results:
        assert cp is first


def test_checkpoint_state_persistence_and_isolation(monkeypatch):
    """Kiểm tra lưu trữ và nạp checkpoint giữa các thread_id khác nhau."""
    monkeypatch.setattr(settings, "db_host", "")
    cp = get_checkpointer()
    assert cp is not None

    config_1 = {"configurable": {"thread_id": "session_user_1", "checkpoint_ns": ""}}
    config_2 = {"configurable": {"thread_id": "session_user_2", "checkpoint_ns": ""}}

    cp1_val = empty_checkpoint()
    cp1_val["channel_values"] = {"messages": ["Xin chào từ user 1"]}
    cp1_val["channel_versions"] = {"messages": 1}

    cp2_val = empty_checkpoint()
    cp2_val["channel_values"] = {"messages": ["Xin chào từ user 2"]}
    cp2_val["channel_versions"] = {"messages": 1}

    # Lưu checkpoint
    new_cfg_1 = cp.put(config_1, cp1_val, {"source": "update"}, new_versions={"messages": 1})
    new_cfg_2 = cp.put(config_2, cp2_val, {"source": "update"}, new_versions={"messages": 1})

    # Nạp lại checkpoint
    loaded_1 = cp.get_tuple(new_cfg_1)
    loaded_2 = cp.get_tuple(new_cfg_2)

    assert loaded_1 is not None
    assert loaded_1.checkpoint["channel_values"]["messages"] == ["Xin chào từ user 1"]

    assert loaded_2 is not None
    assert loaded_2.checkpoint["channel_values"]["messages"] == ["Xin chào từ user 2"]
