"""Unit and integration tests for Sessions API and in-memory store."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.sessions.store import (
    clear_sessions_store,
    create_session,
    delete_session,
    get_session,
    list_sessions,
    update_session_meta,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure clean session store before and after each test."""
    clear_sessions_store()
    yield
    clear_sessions_store()


def test_list_sessions_empty():
    """GET /api/sessions với user_id mới trả về danh sách rỗng."""
    res = client.get("/api/sessions?user_id=user_empty")
    assert res.status_code == 200
    data = res.json()
    assert data == {"sessions": []}


def test_create_session():
    """POST /api/sessions tạo session thành công với tiêu đề tuỳ chọn."""
    res = client.post("/api/sessions", json={"user_id": "user_1", "title": "Giám sát camera"})
    assert res.status_code == 200
    sess = res.json()
    assert "id" in sess and len(sess["id"]) > 0
    assert sess["user_id"] == "user_1"
    assert sess["title"] == "Giám sát camera"
    assert sess["preview"] == ""
    assert "created_at" in sess
    assert "updated_at" in sess


def test_create_session_default_title():
    """POST /api/sessions không truyền title nhận title mặc định."""
    res = client.post("/api/sessions", json={"user_id": "user_1"})
    assert res.status_code == 200
    sess = res.json()
    assert sess["title"] == "Phiên chat mới"


def test_list_sessions_sorted():
    """GET /api/sessions trả về danh sách sắp xếp theo updated_at giảm dần."""
    res1 = client.post("/api/sessions", json={"user_id": "user_sort", "title": "Session 1"})
    assert res1.status_code == 200
    s1 = res1.json()

    res2 = client.post("/api/sessions", json={"user_id": "user_sort", "title": "Session 2"})
    assert res2.status_code == 200
    s2 = res2.json()

    # Session 2 được tạo sau nên updated_at mới hơn Session 1
    res_list = client.get("/api/sessions?user_id=user_sort")
    assert res_list.status_code == 200
    items = res_list.json()["sessions"]
    assert len(items) == 2
    assert items[0]["id"] == s2["id"]
    assert items[1]["id"] == s1["id"]

    # Cập nhật Session 1 để trở thành mới nhất
    update_session_meta(s1["id"], user_id="user_sort", title="Session 1 Updated")
    res_list2 = client.get("/api/sessions?user_id=user_sort")
    items2 = res_list2.json()["sessions"]
    assert items2[0]["id"] == s1["id"]
    assert items2[1]["id"] == s2["id"]


def test_delete_session_success():
    """DELETE /api/sessions/{id}?user_id= xóa thành công và không còn trong danh sách."""
    res_create = client.post("/api/sessions", json={"user_id": "user_del", "title": "To delete"})
    sess_id = res_create.json()["id"]

    res_del = client.delete(f"/api/sessions/{sess_id}?user_id=user_del")
    assert res_del.status_code == 200
    assert res_del.json() == {"deleted": True}

    res_list = client.get("/api/sessions?user_id=user_del")
    assert res_list.status_code == 200
    assert res_list.json()["sessions"] == []


def test_delete_session_wrong_user_404():
    """DELETE /api/sessions/{id} với user_id sai trả về 404."""
    res_create = client.post("/api/sessions", json={"user_id": "user_owner", "title": "Owner session"})
    sess_id = res_create.json()["id"]

    res_del = client.delete(f"/api/sessions/{sess_id}?user_id=other_user")
    assert res_del.status_code == 404
    assert res_del.json()["detail"] == "Session not found"


def test_delete_session_nonexistent_404():
    """DELETE /api/sessions/{id} không tồn tại trả về 404."""
    res_del = client.delete("/api/sessions/nonexistent-session-id?user_id=any_user")
    assert res_del.status_code == 404
    assert res_del.json()["detail"] == "Session not found"


def test_sessions_user_isolation():
    """Cách ly dữ liệu phiên giữa các người dùng khác nhau."""
    res_u1 = client.post("/api/sessions", json={"user_id": "user_alpha", "title": "Alpha Session"})
    res_u2 = client.post("/api/sessions", json={"user_id": "user_beta", "title": "Beta Session"})

    s1 = res_u1.json()
    s2 = res_u2.json()

    list_u1 = client.get("/api/sessions?user_id=user_alpha").json()["sessions"]
    list_u2 = client.get("/api/sessions?user_id=user_beta").json()["sessions"]

    assert len(list_u1) == 1 and list_u1[0]["id"] == s1["id"]
    assert len(list_u2) == 1 and list_u2[0]["id"] == s2["id"]

    # Xóa của user_alpha không làm mất của user_beta
    client.delete(f"/api/sessions/{s1['id']}?user_id=user_alpha")
    assert client.get("/api/sessions?user_id=user_alpha").json()["sessions"] == []
    assert len(client.get("/api/sessions?user_id=user_beta").json()["sessions"]) == 1


def test_missing_or_empty_user_id_validation():
    """GET/POST/DELETE thiếu hoặc rỗng user_id trả về 422 hoặc 400."""
    # GET missing query param
    assert client.get("/api/sessions").status_code == 422
    # GET empty query param
    assert client.get("/api/sessions?user_id=").status_code in (400, 422)
    assert client.get("/api/sessions?user_id=%20%20").status_code in (400, 422)

    # POST missing user_id
    assert client.post("/api/sessions", json={}).status_code == 422
    # POST empty user_id
    assert client.post("/api/sessions", json={"user_id": ""}).status_code in (400, 422)
    assert client.post("/api/sessions", json={"user_id": "   "}).status_code in (400, 422)

    # DELETE missing user_id
    assert client.delete("/api/sessions/some-id").status_code == 422
    assert client.delete("/api/sessions/some-id?user_id=").status_code in (400, 422)
    assert client.delete("/api/sessions/some-id?user_id=%20%20").status_code in (400, 422)


def test_session_store_direct_unit():
    """Kiểm tra trực tiếp các hàm logic trong src.sessions.store."""
    # List rỗng
    assert list_sessions("u_test") == []
    assert list_sessions("") == []

    # Tạo
    s = create_session("u_test", "Tiêu đề 1")
    assert s["user_id"] == "u_test"
    assert s["title"] == "Tiêu đề 1"

    # Lấy thông tin
    assert get_session(s["id"], "u_test") is not None
    assert get_session(s["id"]) is not None
    assert get_session("nonexistent") is None

    # Update meta
    up = update_session_meta(s["id"], "u_test", title="Tiêu đề mới", preview="Xem trước 123")
    assert up is not None
    assert up["title"] == "Tiêu đề mới"
    assert up["preview"] == "Xem trước 123"

    # Delete
    assert delete_session(s["id"], "u_test") is True
    assert delete_session(s["id"], "u_test") is False
    assert get_session(s["id"]) is None
