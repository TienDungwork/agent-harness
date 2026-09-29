"""Comprehensive test suite for Graceful Degradation (DB Offline) — Phase 5 Validation.

Tiêu chuẩn kiểm thử Acceptance Criteria AC-3:
1. Khi DB_HOST='invalid' hoặc ngắt kết nối PostgreSQL:
   - init_memory_db() ghi log warning, trả về False an toàn, không crash app.
   - get_checkpointer() tự động fallback sang MemorySaver() trong RAM.
   - save_to_long_term(), recall_long_term(), clear_long_term() hoạt động bình thường qua fallback store.
   - recall_memory_node và extract_memory_node trong graph thực thi trơn tru không lỗi.
   - API endpoints: GET /api/memory, DELETE /api/memory, POST /api/chat, POST /api/agent/stream,
     và GET /api/health phản hồi HTTP 200 thành công, tuyệt đối KHÔNG trả về HTTP 500.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.memory.db import init_memory_db, is_postgres_configured
from src.memory.shortterm import (
    get_checkpointer,
    is_using_postgres_checkpointer,
    reset_checkpointer,
)
from src.memory.longterm import (
    clear_long_term,
    recall_long_term,
    save_to_long_term,
)
from src.agent.graph import Agent_Input, run_agent


@pytest.fixture(autouse=True)
def cleanup_memory_state():
    """Dọn sạch state memory và reset checkpointer trước và sau mỗi test."""
    clear_long_term()
    reset_checkpointer()
    yield
    clear_long_term()
    reset_checkpointer()


@pytest.fixture
def client():
    return TestClient(app)


def test_init_memory_db_graceful_degradation_invalid_host(monkeypatch, caplog):
    """Khi DB_HOST=invalid, init_memory_db() bắt lỗi, log warning, trả về False an toàn."""
    monkeypatch.setattr("src.memory.db.settings.db_host", "invalid_postgres_host_nonexistent")
    monkeypatch.setattr("src.memory.db.settings.db_user", "postgres")

    with caplog.at_level(logging.WARNING):
        result = init_memory_db()

    assert result is False
    # Log cảnh báo nhẹ nhàng ghi nhận hệ thống sẽ dùng in-memory fallback
    assert any("in-memory fallback" in record.message.lower() or "không thể kết nối" in record.message.lower() for record in caplog.records)


def test_checkpointer_graceful_degradation_invalid_host(monkeypatch, caplog):
    """Khi DB_HOST=invalid, get_checkpointer() tự động fallback sang MemorySaver."""
    monkeypatch.setattr("src.config.settings.db_host", "invalid_postgres_host_nonexistent")
    monkeypatch.setattr("src.config.settings.db_user", "postgres")

    # Giả lập connection pool ném lỗi kết nối
    with patch("psycopg_pool.ConnectionPool", side_effect=Exception("could not translate host name")):
        with caplog.at_level(logging.WARNING):
            saver = get_checkpointer()

    assert saver is not None
    # Xác nhận checkpointer fallback đang dùng MemorySaver trong RAM chứ không phải PostgresSaver
    assert not is_using_postgres_checkpointer()
    assert saver.__class__.__name__ in ("MemorySaver", "InMemorySaver")




def test_longterm_save_and_recall_graceful_degradation_invalid_host(monkeypatch, caplog):
    """Khi DB_HOST=invalid, lưu và đọc facts tự động fallback sang in-memory store."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_broken_connection(*args, **kwargs):
        raise ConnectionError("could not translate host name 'invalid'")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_broken_connection)

    user_id = "user_deg_001"
    with caplog.at_level(logging.WARNING):
        # 1. Lưu fact trong tình trạng DB sập
        save_to_long_term(user_id, "Tôi phụ trách camera khu bến cảng", category="role")

        # 2. Đọc fact trong tình trạng DB sập
        facts = recall_long_term(user_id, "khu vực tôi phụ trách là gì", k=1)

    assert len(facts) == 1
    assert "bến cảng" in facts[0]

    # 3. Xóa fact trong tình trạng DB sập
    clear_long_term(user_id)
    after_clear = recall_long_term(user_id, "khu vực tôi phụ trách", k=1)
    assert len(after_clear) == 0


def test_api_memory_get_and_delete_no_500_when_db_down(client, monkeypatch):
    """Endpoint GET & DELETE /api/memory phản hồi 200 (không trả về 500) khi PostgreSQL offline."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_broken_connection(*args, **kwargs):
        raise ConnectionError("PostgreSQL connection refused on port 5432")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_broken_connection)

    user_id = "user_api_fallback_test"
    save_to_long_term(user_id, "Thông tin cá nhân lưu trong fallback")

    # 1. GET /api/memory
    res_get = client.get(f"/api/memory?user_id={user_id}")
    assert res_get.status_code == 200, f"Kỳ vọng 200 nhưng nhận {res_get.status_code}: {res_get.text}"
    data_get = res_get.json()
    assert data_get["status"] == "ok"
    assert data_get["total"] == 1
    assert "Thông tin cá nhân lưu trong fallback" in data_get["facts"]

    # 2. DELETE /api/memory
    res_del = client.delete(f"/api/memory?user_id={user_id}")
    assert res_del.status_code == 200, f"Kỳ vọng 200 nhưng nhận {res_del.status_code}: {res_del.text}"
    data_del = res_del.json()
    assert data_del["status"] == "ok"
    assert data_del["deleted"] is True

    # 3. GET sau khi DELETE
    res_after = client.get(f"/api/memory?user_id={user_id}")
    assert res_after.status_code == 200
    assert res_after.json()["total"] == 0


def test_api_chat_no_500_when_db_down(client, monkeypatch):
    """Endpoint /api/chat không trả về HTTP 500 khi DB memory offline."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_broken_connection(*args, **kwargs):
        raise ConnectionError("PostgreSQL connection refused")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_broken_connection)

    payload = {
        "question": "Chào bạn, tôi tên là Hoàng",
        "session_id": "test_deg_chat_sess",
        "user_id": "user_deg_chat",
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200, f"Kỳ vọng 200 nhưng nhận {res.status_code}: {res.text}"
    data = res.json()
    assert "answer" in data
    assert len(data["answer"]) > 0


def test_api_agent_stream_no_500_when_db_down(client, monkeypatch):
    """Endpoint /api/agent/stream chạy bình thường và phát sự kiện __answer__ khi DB offline."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_broken_connection(*args, **kwargs):
        raise ConnectionError("PostgreSQL connection refused")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_broken_connection)

    payload = {
        "question": "Chào bạn",
        "session_id": "test_deg_stream_sess",
        "user_id": "user_deg_stream",
    }
    res = client.post("/api/agent/stream", json=payload)
    assert res.status_code == 200, f"Kỳ vọng 200 nhưng nhận {res.status_code}: {res.text}"
    # Xác nhận stream có chứa sự kiện trả lời hoàn tất
    stream_content = res.text
    assert "__answer__" in stream_content


def test_agent_graph_pipeline_execution_when_db_down(monkeypatch):
    """Toàn bộ pipeline Agent Graph chạy thành công khi DB offline."""
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_broken_connection(*args, **kwargs):
        raise ConnectionError("DB host unreachable")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_broken_connection)

    inp = Agent_Input(question="Chào bạn, tôi phụ trách an ninh cổng 1")
    out = run_agent(inp, session_id="deg_sess_01", user_id="user_deg_graph")

    assert out is not None
    assert out.answer is not None
    assert len(out.answer) > 0


def test_health_endpoint_healthy_when_db_down(client, monkeypatch):
    """Endpoint /api/health trả về 200 và phản hồi cấu hình bình thường khi DB offline."""
    monkeypatch.setattr("src.config.settings.db_host", "invalid_host")
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
