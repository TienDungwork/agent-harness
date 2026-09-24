"""Unit tests cho Human Feedback API & Streaming (dong v8 Phase 3).

Kiểm tra:
- AC-3: Gửi feedback Like (rating: positive) lưu vào data/feedback.json.
- AC-4: Gửi feedback Dislike (rating: negative) kèm reason, image base64, agent_trace.
- AC-5: File data/feedback.json hợp lệ, mã hóa UTF-8 tiếng Việt, an toàn ghi đè.
- AC-6: Stream chunks SSE qua POST /api/agent/stream với stream_tokens=True.
- Validation: Chặn rating sai giá trị, question/answer rỗng.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from src.main import app
from src.feedback import FEEDBACK_FILE, ATTACHMENTS_DIR, get_all_feedback

client = TestClient(app)

# 1x1 transparent PNG in base64
TINY_PNG_B64 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_submit_positive_feedback_ac3(tmp_path, monkeypatch):
    """AC-3: Đánh giá Like (rating: positive) được lưu đầy đủ vào data/feedback.json."""
    custom_fb_file = tmp_path / "feedback.json"
    custom_attach_dir = tmp_path / "attachments"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.ATTACHMENTS_DIR", custom_attach_dir)

    payload = {
        "session_id": "sess_test_1",
        "user_id": "user_alice",
        "question": "Hôm nay có bao nhiêu xe vào?",
        "answer": "Có 120 xe vào hôm nay.",
        "rating": "positive",
        "agent_trace": {"nodes": [{"node_id": "execute_sql", "duration_ms": 12.5}]},
    }

    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["feedback_id"].startswith("fb_")

    records = get_all_feedback()
    assert len(records) == 1
    rec = records[0]
    assert rec["rating"] == "positive"
    assert rec["question"] == "Hôm nay có bao nhiêu xe vào?"
    assert rec["answer"] == "Có 120 xe vào hôm nay."
    assert rec["attachment_path"] is None
    assert rec["agent_trace"]["nodes"][0]["node_id"] == "execute_sql"


def test_submit_negative_feedback_with_image_ac4(tmp_path, monkeypatch):
    """AC-4: Đánh giá Dislike kèm lý do và ảnh được giải mã lưu file và đính kèm đường dẫn."""
    custom_fb_file = tmp_path / "feedback.json"
    custom_attach_dir = tmp_path / "attachments"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.ATTACHMENTS_DIR", custom_attach_dir)

    payload = {
        "session_id": "sess_test_2",
        "user_id": "user_bob",
        "question": "Hiện có bao nhiêu camera đang hoạt động?",
        "answer": "6 camera đang hoạt động...",
        "rating": "negative",
        "feedback_reason": "Hệ thống trả lời 6 camera là thiếu 4 camera vùng cấm và cháy khói",
        "image_base64": TINY_PNG_B64,
        "agent_trace": {
            "sql": "SELECT COUNT(DISTINCT camera_name) FROM plate_event",
            "nodes": [{"node_id": "respond", "duration_ms": 45.2}],
        },
    }

    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    fb_id = data["feedback_id"]

    records = get_all_feedback()
    assert len(records) == 1
    rec = records[0]
    assert rec["rating"] == "negative"
    assert "thiếu 4 camera" in rec["feedback_reason"]
    assert rec["attachment_path"] == f"data/feedback/attachments/{fb_id}.png"

    # Xác nhận file ảnh thực tế đã được lưu trên đĩa
    saved_img = custom_attach_dir / f"{fb_id}.png"
    assert saved_img.exists()
    assert len(saved_img.read_bytes()) > 0


def test_feedback_data_integrity_ac5(tmp_path, monkeypatch):
    """AC-5: File feedback.json là mảng JSON hợp lệ, giữ nguyên ký tự tiếng Việt có dấu."""
    custom_fb_file = tmp_path / "feedback.json"
    custom_attach_dir = tmp_path / "attachments"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.ATTACHMENTS_DIR", custom_attach_dir)

    # Gửi nhiều feedback liên tiếp
    for i in range(3):
        res = client.post(
            "/api/feedback",
            json={
                "session_id": f"sess_{i}",
                "user_id": "tester",
                "question": f"Câu hỏi kiểm tra tiếng Việt có dấu #{i}",
                "answer": f"Trả lời kiểm tra số lượng phương tiện #{i}",
                "rating": "positive" if i % 2 == 0 else "negative",
                "feedback_reason": f"Lý do phản hồi tiếng Việt #{i}" if i % 2 != 0 else None,
            },
        )
        assert res.status_code == 200

    content = custom_fb_file.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert isinstance(parsed, list)
    assert len(parsed) == 3
    assert "tiếng Việt có dấu" in parsed[0]["question"]


def test_feedback_validation_errors():
    """Kiểm tra validation cho các trường dữ liệu sai hoặc rỗng."""
    # Rating sai giá trị
    res1 = client.post(
        "/api/feedback",
        json={
            "session_id": "s1",
            "question": "q",
            "answer": "a",
            "rating": "neutral",  # chỉ cho phép positive hoặc negative
        },
    )
    assert res1.status_code in (400, 422)

    # Question rỗng
    res2 = client.post(
        "/api/feedback",
        json={
            "session_id": "s1",
            "question": "   ",
            "answer": "a",
            "rating": "positive",
        },
    )
    assert res2.status_code in (400, 422)

    # Answer rỗng
    res3 = client.post(
        "/api/feedback",
        json={
            "session_id": "s1",
            "question": "Câu hỏi",
            "answer": "   ",
            "rating": "positive",
        },
    )
    assert res3.status_code in (400, 422)

    # Base64 hỏng
    res4 = client.post(
        "/api/feedback",
        json={
            "session_id": "s1",
            "question": "Câu hỏi",
            "answer": "Trả lời",
            "rating": "negative",
            "image_base64": "invalid_base64_!@#$%",
        },
    )
    assert res4.status_code in (400, 422)

    # Ảnh vượt quá 5MB
    large_bytes = b"X" * (5 * 1024 * 1024 + 1024)
    large_b64 = base64.b64encode(large_bytes).decode("ascii")
    res5 = client.post(
        "/api/feedback",
        json={
            "session_id": "s1",
            "question": "Câu hỏi",
            "answer": "Trả lời",
            "rating": "negative",
            "image_base64": large_b64,
        },
    )
    assert res5.status_code in (400, 422)


def test_stream_chunks_with_stream_tokens_ac6():
    """AC-6: Khi gọi stream với stream_tokens=True, nhận các chunk events trước event done."""
    req_payload = {
        "question": "Chào bạn",
        "session_id": "test_stream_chunks",
        "user_id": "stream_user",
        "stream_tokens": True,
    }

    res = client.post("/api/agent/stream", json=req_payload)
    assert res.status_code == 200

    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    chunk_events = [e for e in events if e.get("node_id") == "__answer__" and e.get("status") == "chunk"]
    done_events = [e for e in events if e.get("node_id") == "__answer__" and e.get("status") == "done"]

    assert len(chunk_events) > 0, f"Expected chunk events, got {events}"
    assert len(done_events) == 1
    assert done_events[0]["output"] != ""
    assert "delta" in chunk_events[0]


def test_feedback_image_save_failure_returns_422(tmp_path, monkeypatch):
    """Khi có image_base64 hợp lệ nhưng ghi file thất bại, API trả 422 (không lưu im lặng)."""
    custom_fb_file = tmp_path / "feedback.json"
    custom_attach_dir = tmp_path / "attachments"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.ATTACHMENTS_DIR", custom_attach_dir)

    def _fail_write(_self, _data):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.write_bytes", _fail_write)

    payload = {
        "session_id": "sess_img_fail",
        "question": "Câu hỏi",
        "answer": "Trả lời",
        "rating": "negative",
        "feedback_reason": "Lỗi ảnh",
        "image_base64": TINY_PNG_B64,
    }
    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 422
    assert not custom_fb_file.exists() or get_all_feedback() == []


def test_submit_negative_feedback_with_custom_image_filename(tmp_path, monkeypatch):
    """Kiểm tra lưu file ảnh với filename tùy chỉnh do người dùng upload."""
    custom_fb_file = tmp_path / "feedback.json"
    custom_attach_dir = tmp_path / "attachments"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.ATTACHMENTS_DIR", custom_attach_dir)

    payload = {
        "session_id": "sess_test_custom_fn",
        "question": "Hỏi câu hỏi",
        "answer": "Trả lời",
        "rating": "negative",
        "feedback_reason": "Ảnh lỗi",
        "image_base64": TINY_PNG_B64,
        "image_filename": "screenshot_dashboard.png",
    }
    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200
    fb_id = res.json()["feedback_id"]

    saved_img = custom_attach_dir / f"{fb_id}_screenshot_dashboard.png"
    assert saved_img.exists()
    records = get_all_feedback()
    assert records[0]["attachment_path"] == f"data/feedback/attachments/{fb_id}_screenshot_dashboard.png"


def test_feedback_sqlite_direct_query(tmp_path, monkeypatch):
    """Kiểm tra dữ liệu feedback được lưu chuẩn xác vào database SQLite (feedback.db)."""
    import sqlite3
    custom_fb_file = tmp_path / "feedback.json"
    custom_db_file = tmp_path / "feedback.db"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.FEEDBACK_DB", custom_db_file)

    payload = {
        "session_id": "sess_sqlite_1",
        "user_id": "sqlite_user",
        "question": "Kiểm tra lưu SQLite",
        "answer": "Trả lời từ SQLite",
        "rating": "positive",
        "agent_trace": {"nodes": [{"node_id": "test_node"}]},
    }
    res = client.post("/api/feedback", json=payload)
    assert res.status_code == 200

    # Kiểm tra file .db được tạo ra
    assert custom_db_file.exists()

    # Truy vấn trực tiếp bằng sqlite3
    conn = sqlite3.connect(str(custom_db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT id, rating, question, answer, agent_trace FROM feedback")
    rows = cursor.fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row[1] == "positive"
    assert row[2] == "Kiểm tra lưu SQLite"
    assert row[3] == "Trả lời từ SQLite"
    trace = json.loads(row[4])
    assert trace["nodes"][0]["node_id"] == "test_node"
    conn.close()


def test_feedback_sqlite_auto_migration(tmp_path, monkeypatch):
    """Kiểm tra tính năng tự động migrate dữ liệu từ feedback.json cũ sang SQLite."""
    import sqlite3
    custom_fb_file = tmp_path / "feedback.json"
    custom_db_file = tmp_path / "feedback.db"
    monkeypatch.setattr("src.feedback.FEEDBACK_FILE", custom_fb_file)
    monkeypatch.setattr("src.feedback.FEEDBACK_DB", custom_db_file)

    # Giả lập file feedback.json cũ có sẵn dữ liệu
    legacy_data = [
        {
            "id": "fb_legacy_001",
            "timestamp": "2026-09-24T00:00:00Z",
            "session_id": "sess_legacy",
            "user_id": "user_legacy",
            "rating": "positive",
            "feedback_reason": None,
            "attachment_path": None,
            "question": "Câu hỏi cũ",
            "answer": "Câu trả lời cũ",
            "agent_trace": {"nodes": []},
        }
    ]
    custom_fb_file.write_text(json.dumps(legacy_data, ensure_ascii=False), encoding="utf-8")

    # Gọi get_all_feedback để kích hoạt _ensure_dirs và _migrate_json_to_sqlite
    records = get_all_feedback()
    assert len(records) == 1
    assert records[0]["id"] == "fb_legacy_001"

    # Xác nhận dữ liệu đã được nạp vào SQLite
    conn = sqlite3.connect(str(custom_db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT id, question FROM feedback WHERE id = 'fb_legacy_001'")
    row = cursor.fetchone()
    assert row is not None
    assert row[1] == "Câu hỏi cũ"
    conn.close()


