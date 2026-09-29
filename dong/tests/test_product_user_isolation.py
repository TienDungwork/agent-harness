"""Comprehensive test suite for User Isolation (AC-2) — Phase 5 Validation.

Tiêu chuẩn nghiệm thu AC-2:
1. Mọi thao tác bộ nhớ phải cô lập theo user_id. Không bao giờ để rò rỉ fact của user này sang context của user khác.
2. Hai phiên chat song song với 2 user_id khác nhau: thông tin cá nhân của User A (tên, vai trò, ca trực, khu vực phụ trách)
   tuyệt đối không xuất hiện trong phản hồi hay ngữ cảnh của User B.
3. TTL Cache không cache các câu hỏi danh tính người dùng nhằm ngăn ngừa rò rỉ chéo giữa các user.
4. Reset Memory (DELETE /api/memory) của User A chỉ xóa dữ liệu của User A, không tác động đến User B.
5. Lịch sử hội thoại của User A được bảo vệ, User B không thể đọc được.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.agent.graph import Agent_Input, recall_node, run_agent
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term
from src.memory.ttl_cache import clear_ttl_cache, make_cache_key, get_ttl_cached
from src.sessions import create_session, append_session_messages


@pytest.fixture(autouse=True)
def cleanup_isolation_environment():
    """Dọn sạch bộ nhớ dài hạn và TTL cache trước và sau mỗi test case."""
    clear_long_term()
    clear_ttl_cache()
    yield
    clear_long_term()
    clear_ttl_cache()


@pytest.fixture
def client():
    return TestClient(app)


def test_two_users_chat_isolation_identity_not_leaked(client):
    """Kịch bản chính AC-2: User A và User B chat trong 2 phiên riêng biệt.
    
    Thông tin của User A tuyệt đối không bao giờ rò rỉ sang User B.
    """
    user_a = "user_alpha_an"
    user_b = "user_beta_binh"
    sess_a = "session_alpha_01"
    sess_b = "session_beta_01"

    # 1. User A giới thiệu tên và vai trò trong phiên của mình
    save_to_long_term(user_a, "Tôi tên là Nguyễn Văn An", category="identity")
    save_to_long_term(user_a, "Tôi phụ trách giám sát an ninh ca đêm khu vực cổng 1", category="role")

    # 2. User B (chưa giới thiệu bản thân) hỏi "Tôi là ai?"
    res_b1 = client.post("/api/chat", json={
        "question": "Tôi là ai?",
        "session_id": sess_b,
        "user_id": user_b,
    })
    assert res_b1.status_code == 200
    ans_b1 = res_b1.json()["answer"]
    # Xác nhận câu trả lời cho User B TUYỆT ĐỐI KHÔNG chứa danh tính của User A
    assert "Nguyễn Văn An" not in ans_b1
    assert "nguyen van an" not in ans_b1.lower()
    assert "cổng 1" not in ans_b1

    # 3. User B giới thiệu bản thân
    save_to_long_term(user_b, "Tôi tên là Trần Thị Bình", category="identity")
    save_to_long_term(user_b, "Tôi là ca trưởng ca sáng", category="role")

    # 4. User A hỏi lại "Tôi là ai?"
    res_a = client.post("/api/chat", json={
        "question": "Tôi là ai?",
        "session_id": sess_a,
        "user_id": user_a,
    })
    assert res_a.status_code == 200
    ans_a = res_a.json()["answer"]
    # User A nhận đúng thông tin của An, không có thông tin của Bình
    assert "Nguyễn Văn An" in ans_a or "cổng 1" in ans_a
    assert "Trần Thị Bình" not in ans_a
    assert "ca sáng" not in ans_a

    # 5. User B hỏi "Tôi là ai?"
    res_b2 = client.post("/api/chat", json={
        "question": "Tôi là ai?",
        "session_id": sess_b,
        "user_id": user_b,
    })
    assert res_b2.status_code == 200
    ans_b2 = res_b2.json()["answer"]
    # User B nhận đúng thông tin của Bình, không có thông tin của An
    assert "Trần Thị Bình" in ans_b2 or "ca sáng" in ans_b2
    assert "Nguyễn Văn An" not in ans_b2
    assert "cổng 1" not in ans_b2


def test_graph_recall_node_context_strictly_isolated():
    """Node recall_memory_node chỉ nạp facts của đúng user_id vào state context."""
    user_a = "user_guard_alpha"
    user_b = "user_guard_beta"

    save_to_long_term(user_a, "Tôi chuyên theo dõi camera nhiệt cổng 3")
    save_to_long_term(user_b, "Tôi chuyên xử lý cảnh báo xâm nhập hàng rào điện tử")

    # Chạy recall cho user A
    state_a = {"question": "tôi phụ trách gì", "user_id": user_a, "session_id": "s_a"}
    res_a = recall_node(state_a)
    memories_a = res_a.get("recalled_memories", [])

    assert any("cổng 3" in m for m in memories_a)
    assert not any("hàng rào" in m for m in memories_a)

    # Chạy recall cho user B
    state_b = {"question": "tôi phụ trách gì", "user_id": user_b, "session_id": "s_b"}
    res_b = recall_node(state_b)
    memories_b = res_b.get("recalled_memories", [])

    assert any("hàng rào" in m for m in memories_b)
    assert not any("cổng 3" in m for m in memories_b)


def test_ttl_cache_does_not_leak_identity_between_users(client):
    """TTL Cache bỏ qua câu hỏi danh tính cá nhân để tránh user_B trúng cache câu trả lời của user_A."""
    user_a = "user_alpha_vip"
    user_b = "user_beta_guest"
    save_to_long_term(user_a, "Tôi tên là Đỗ Minh Quân, Giám đốc an ninh")

    # User A hỏi "Tôi là ai?"
    res_a = client.post("/api/chat", json={
        "question": "Tôi là ai?",
        "session_id": "sess_a",
        "user_id": user_a,
    })
    assert res_a.status_code == 200
    assert "Đỗ Minh Quân" in res_a.json()["answer"]

    # Kiểm tra TTL Cache không lưu key này
    cache_key = make_cache_key("Tôi là ai?")
    assert get_ttl_cached(cache_key) is None

    # User B hỏi ngay sau đó cùng câu "Tôi là ai?"
    res_b = client.post("/api/chat", json={
        "question": "Tôi là ai?",
        "session_id": "sess_b",
        "user_id": user_b,
    })
    assert res_b.status_code == 200
    ans_b = res_b.json()["answer"]
    # User B không bị cache câu trả lời của User A
    assert "Đỗ Minh Quân" not in ans_b
    assert "Giám đốc an ninh" not in ans_b


def test_memory_api_isolation_and_delete_independence(client):
    """API GET và DELETE /api/memory chỉ tác động đến đúng user_id được chỉ định."""
    u1 = "operator_1"
    u2 = "operator_2"

    save_to_long_term(u1, "Fact của Operator 1: Trực camera số 5")
    save_to_long_term(u2, "Fact của Operator 2: Trực camera số 9")

    # GET u1 và u2
    resp_u1 = client.get(f"/api/memory?user_id={u1}").json()
    resp_u2 = client.get(f"/api/memory?user_id={u2}").json()

    assert resp_u1["total"] == 1
    assert "camera số 5" in resp_u1["facts"][0]
    assert resp_u2["total"] == 1
    assert "camera số 9" in resp_u2["facts"][0]

    # Reset memory của u1
    del_u1 = client.delete(f"/api/memory?user_id={u1}")
    assert del_u1.status_code == 200

    # Kiểm tra lại: u1 bị xóa, u2 vẫn còn nguyên
    after_u1 = client.get(f"/api/memory?user_id={u1}").json()
    assert after_u1["total"] == 0
    assert after_u1["facts"] == []

    after_u2 = client.get(f"/api/memory?user_id={u2}").json()
    assert after_u2["total"] == 1
    assert "camera số 9" in after_u2["facts"][0]


def test_sessions_message_history_user_isolation(client):
    """User B không thể truy cập hoặc đọc trộm tin nhắn từ session của User A."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    user_a = "user_owner_a"
    user_b = "user_intruder_b"

    # Tạo session cho User A
    sess_a = create_session(user_id=user_a, title="Phiên bảo mật của User A")
    sid_a = sess_a["id"]

    append_session_messages(sid_a, user_a, [
        {"role": "user", "content": "Khu vực bí mật là phòng máy chủ", "timestamp": now},
        {"role": "assistant", "content": "Đã ghi nhận khu vực phòng máy chủ.", "timestamp": now},
    ])

    # User A đọc thành công (200)
    res_a = client.get(f"/api/sessions/{sid_a}/messages?user_id={user_a}")
    assert res_a.status_code == 200
    assert len(res_a.json()["messages"]) == 2

    # User B cố tình đọc session của User A -> Bị từ chối (404 Not Found)
    res_b = client.get(f"/api/sessions/{sid_a}/messages?user_id={user_b}")
    assert res_b.status_code == 404

