"""Unit & Integration test suite for Memory Management API (GET /api/memory, DELETE /api/memory).

Tương thích kiến trúc Memory & Context Engineering (v9):
1. GET /api/memory?user_id=...: Trả về danh sách facts của người dùng.
2. DELETE /api/memory?user_id=...: Xóa toàn bộ facts khi người dùng bấm Reset Memory.
3. User Isolation: Thao tác của User A không làm ảnh hưởng User B.
4. Input Validation: Yêu cầu bắt buộc user_id hợp lệ (không rỗng/khoảng trắng).
5. Graceful Degradation: Hoạt động bền bỉ, an toàn kể cả khi DB không khả dụng.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term


@pytest.fixture(autouse=True)
def clean_memory_fixture():
    """Tự động dọn dẹp bộ nhớ trước và sau mỗi test case."""
    clear_long_term()
    yield
    clear_long_term()


@pytest.fixture
def client():
    return TestClient(app)


def test_get_memory_empty_for_new_user(client):
    """User mới chưa có facts nào thì GET /api/memory trả về mảng rỗng."""
    resp = client.get("/api/memory?user_id=fresh_user_001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["user_id"] == "fresh_user_001"
    assert data["facts"] == []
    assert data["memories"] == []
    assert data["total"] == 0


def test_get_memory_with_facts(client):
    """User đã lưu facts thì GET /api/memory trả về đúng danh sách."""
    uid = "test_user_inspector"
    save_to_long_term(uid, "Tôi tên là Nguyễn Văn Tuấn", category="identity")
    save_to_long_term(uid, "Tôi phụ trách giám sát an ninh ca đêm", category="role")

    resp = client.get(f"/api/memory?user_id={uid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["user_id"] == uid
    assert data["total"] == 2
    assert "Tôi tên là Nguyễn Văn Tuấn" in data["facts"]
    assert "Tôi phụ trách giám sát an ninh ca đêm" in data["facts"]
    assert data["memories"] == data["facts"]


def test_get_memory_with_limit(client):
    """Hỗ trợ phân trang/giới hạn số lượng facts trả về qua tham số limit."""
    uid = "user_multi_facts"
    for i in range(5):
        save_to_long_term(uid, f"Sự thật số {i+1} về công việc của tôi")

    resp = client.get(f"/api/memory?user_id={uid}&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["facts"]) == 2
    assert data["total"] == 2


def test_get_memory_missing_or_empty_user_id(client):
    """Thiếu hoặc rỗng user_id trả về lỗi 422 hoặc 400 Bad Request."""
    # Thiếu query param
    resp1 = client.get("/api/memory")
    assert resp1.status_code in (400, 422)

    # Rỗng hoặc chỉ có khoảng trắng
    resp2 = client.get("/api/memory?user_id=")
    assert resp2.status_code in (400, 422)

    resp3 = client.get("/api/memory?user_id=%20%20")
    assert resp3.status_code == 400
    assert "user_id is required" in resp3.json()["detail"]


def test_delete_memory_clears_user_facts(client):
    """DELETE /api/memory xóa sạch toàn bộ facts của user chỉ định."""
    uid = "user_to_be_reset"
    save_to_long_term(uid, "Tôi thích xem camera cổng chính")
    save_to_long_term(uid, "Tôi là ca trưởng ca chiều")

    # Kiểm tra trước khi xóa
    before_resp = client.get(f"/api/memory?user_id={uid}")
    assert before_resp.json()["total"] == 2

    # Gọi API Reset Memory
    del_resp = client.delete(f"/api/memory?user_id={uid}")
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["status"] == "ok"
    assert del_data["user_id"] == uid
    assert del_data["deleted"] is True
    assert uid in del_data["message"]

    # Kiểm tra sau khi xóa
    after_resp = client.get(f"/api/memory?user_id={uid}")
    assert after_resp.status_code == 200
    assert after_resp.json()["total"] == 0
    assert after_resp.json()["facts"] == []


def test_delete_memory_missing_or_empty_user_id(client):
    """DELETE không truyền user_id hoặc truyền rỗng trả về mã lỗi thích hợp."""
    resp1 = client.delete("/api/memory")
    assert resp1.status_code in (400, 422)

    resp2 = client.delete("/api/memory?user_id=")
    assert resp2.status_code in (400, 422)

    resp3 = client.delete("/api/memory?user_id=%20")
    assert resp3.status_code == 400
    assert "user_id is required" in resp3.json()["detail"]


def test_user_isolation_on_get_and_delete(client):
    """User Isolation (AC-2): Thao tác xóa hoặc đọc của User A không tác động User B."""
    user_a = "guard_alpha"
    user_b = "guard_beta"

    save_to_long_term(user_a, "Alpha phụ trách trạm cân")
    save_to_long_term(user_b, "Beta phụ trách hàng rào điện tử")

    # Xác nhận hai user độc lập
    resp_a = client.get(f"/api/memory?user_id={user_a}")
    assert resp_a.json()["total"] == 1
    assert "Alpha phụ trách trạm cân" in resp_a.json()["facts"]

    resp_b = client.get(f"/api/memory?user_id={user_b}")
    assert resp_b.json()["total"] == 1
    assert "Beta phụ trách hàng rào điện tử" in resp_b.json()["facts"]

    # Reset memory của user A
    del_a = client.delete(f"/api/memory?user_id={user_a}")
    assert del_a.status_code == 200

    # User A bị xóa sạch
    check_a = client.get(f"/api/memory?user_id={user_a}")
    assert check_a.json()["total"] == 0
    assert check_a.json()["facts"] == []

    # User B vẫn nguyên vẹn
    check_b = client.get(f"/api/memory?user_id={user_b}")
    assert check_b.json()["total"] == 1
    assert "Beta phụ trách hàng rào điện tử" in check_b.json()["facts"]


def test_graceful_degradation_endpoints_when_db_down(client, monkeypatch):
    """Graceful Degradation (AC-3): Giả lập DB lỗi, API vẫn hoạt động qua fallback."""
    from unittest.mock import MagicMock

    # Giả lập is_postgres_configured=True nhưng connection pool lỗi
    monkeypatch.setattr("src.memory.longterm.is_postgres_configured", lambda: True)

    def mock_get_conn(*args, **kwargs):
        raise ConnectionError("Simulated PostgreSQL connection failure")

    monkeypatch.setattr("src.memory.longterm.get_memory_connection", mock_get_conn)

    uid = "fallback_user"
    # Lưu và truy xuất qua fallback
    save_to_long_term(uid, "Thông tin lưu trong tình huống DB offline")

    # GET vẫn thành công (200), không trả 500
    resp_get = client.get(f"/api/memory?user_id={uid}")
    assert resp_get.status_code == 200
    assert resp_get.json()["status"] == "ok"
    assert "Thông tin lưu trong tình huống DB offline" in resp_get.json()["facts"]

    # DELETE vẫn thành công (200), không trả 500
    resp_del = client.delete(f"/api/memory?user_id={uid}")
    assert resp_del.status_code == 200
    assert resp_del.json()["status"] == "ok"

    # Sau khi xóa
    resp_after = client.get(f"/api/memory?user_id={uid}")
    assert resp_after.status_code == 200
    assert resp_after.json()["total"] == 0
