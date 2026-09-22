"""Unit and integration tests for Phase 7 Smoke Manual Checklist and Production Smoke Script."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.memory.ttl_cache import clear_ttl_cache, make_cache_key, set_ttl_cached

client = TestClient(app)

DONG_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = DONG_ROOT / "scripts"
SPECS_DIR = DONG_ROOT / "specs"


# ------------------------------------------------------------------------------
# Test 1: scripts/smoke-production.sh exists, executable, and contains 7 cases
# ------------------------------------------------------------------------------
def test_smoke_production_script_structure_and_cases():
    """scripts/smoke-production.sh phải tồn tại, có quyền execute và bao gồm đủ 7 cases."""
    script_path = SCRIPTS_DIR / "smoke-production.sh"
    assert script_path.exists(), "scripts/smoke-production.sh phải tồn tại"
    assert os.access(script_path, os.X_OK), "scripts/smoke-production.sh phải có quyền thực thi (executable)"

    content = script_path.read_text(encoding="utf-8")

    # Environment variables
    assert "BACKEND_PORT" in content
    assert "BASE_URL" in content
    assert "SMOKE_USER_ID" in content
    assert "TIMEOUT_SECONDS" in content

    # Precondition check
    assert "verify-docker-self-hosted.sh" in content

    # Case 1: Session API
    assert "/api/sessions" in content
    assert "messages" in content

    # Case 2: Short-term memory
    assert "Tên tôi là An." in content
    assert "Tên tôi là gì?" in content

    # Case 3: TTL Cache
    assert "Hôm nay có bao nhiêu lượt xe vào?" in content
    assert "has_cache" in content or "cache_hit" in content

    # Case 4: Bar chart
    assert "Vẽ biểu đồ cột lượt xe theo loại hôm nay" in content
    assert "bar" in content

    # Case 5: Pie chart
    assert "Vẽ biểu đồ tròn tỷ lệ loại xe" in content
    assert "pie" in content

    # Case 6: Fire warning
    assert "Hôm nay có cảnh báo cháy hoặc khói không?" in content

    # Case 7: AIOC Docs
    assert "Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?" in content
    assert "aioc" in content.lower()
    assert "camera" in content.lower()
    assert "thiết bị" in content.lower()

    # Pass / Fail summary
    assert "PASSED_COUNT" in content
    assert "FAILED_COUNT" in content
    assert "exit 0" in content
    assert "exit 1" in content


# ------------------------------------------------------------------------------
# Test 2: specs/smoke-manual-checklist.md contains required UI & API sections
# ------------------------------------------------------------------------------
def test_smoke_manual_checklist_markdown_content():
    """specs/smoke-manual-checklist.md phải tài liệu hóa đầy đủ các hạng mục UI và link tới script."""
    checklist_path = SPECS_DIR / "smoke-manual-checklist.md"
    assert checklist_path.exists(), "specs/smoke-manual-checklist.md phải tồn tại"

    content = checklist_path.read_text(encoding="utf-8")

    # Link tới script smoke API
    assert "scripts/smoke-production.sh" in content

    # Sidebar & session management
    assert "Sidebar" in content
    assert "phiên mới" in content.lower() or "session" in content.lower()
    assert "preview" in content.lower() or "lịch sử" in content.lower()

    # Short-term memory
    assert "Tên tôi là An." in content
    assert "Tên tôi là gì?" in content

    # TTL Cache
    assert "TTL" in content or "cache" in content.lower()

    # Charts (Chart.js canvas)
    assert "Chart.js" in content
    assert "cột" in content.lower() or "bar" in content.lower()
    assert "tròn" in content.lower() or "pie" in content.lower()

    # Domain specific queries
    assert "cháy" in content.lower() or "khói" in content.lower()
    assert "aioc" in content.lower()
    assert "camera" in content.lower()

    # Live Graph hover JSON
    assert "Live Graph" in content or "live graph" in content.lower()
    assert "hover" in content.lower() or "json" in content.lower()


# ------------------------------------------------------------------------------
# Test 3: Mock TestClient — Session API lifecycle (Create -> List -> Messages)
# ------------------------------------------------------------------------------
def test_mock_testclient_session_api_lifecycle():
    """Kiểm tra luồng API /api/sessions: Tạo session, list ≥1, messages API 200."""
    user_id = "smoke_user_mock_phase7"
    title = "Phiên Smoke Test Phase 7"

    # 1. POST /api/sessions
    create_res = client.post("/api/sessions", json={"user_id": user_id, "title": title})
    assert create_res.status_code == 200, f"Create session failed: {create_res.text}"
    session_data = create_res.json()
    assert "id" in session_data or "session_id" in session_data
    session_id = session_data.get("id") or session_data.get("session_id")
    assert session_data["user_id"] == user_id
    assert session_data["title"] == title

    # 2. GET /api/sessions
    list_res = client.get(f"/api/sessions?user_id={user_id}")
    assert list_res.status_code == 200, f"List sessions failed: {list_res.text}"
    list_data = list_res.json()
    assert "sessions" in list_data
    assert len(list_data["sessions"]) >= 1
    found_session = any(
        (s.get("id") == session_id or s.get("session_id") == session_id)
        for s in list_data["sessions"]
    )
    assert found_session, f"Session {session_id} không tìm thấy trong danh sách sessions"

    # 3. GET /api/sessions/{session_id}/messages
    msg_res = client.get(f"/api/sessions/{session_id}/messages?user_id={user_id}")
    assert msg_res.status_code == 200, f"Get session messages failed: {msg_res.text}"
    msg_data = msg_res.json()
    assert "messages" in msg_data
    assert isinstance(msg_data["messages"], list)


# ------------------------------------------------------------------------------
# Test 4: Mock TestClient — TTL Cache 2nd request hits cache node in SSE stream
# ------------------------------------------------------------------------------
def test_mock_testclient_ttl_cache_stream_hit(monkeypatch):
    """Lần 2 cùng câu hỏi stat trong TTL window -> SSE stream kích hoạt node 'cache' và cache_hit=true."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    question = "Hôm nay có bao nhiêu lượt xe vào?"
    session_id = "smoke_ttl_session"
    user_id = "smoke_ttl_user"

    # Giả lập dữ liệu đã được cache từ lần query 1
    store_key = make_cache_key(question, route="query_data")
    cached_payload = {
        "question": question,
        "answer": "Tổng số lượt xe vào hôm nay là 250 lượt.",
        "tool": "query_traffic",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    }
    set_ttl_cached(store_key, cached_payload)

    # Đảm bảo run_agent_stream không cần gọi khi đã trúng TTL cache
    mock_stream = MagicMock()
    monkeypatch.setattr("src.agent.graph.run_agent_stream", mock_stream)

    # Gửi request lần 2 tới /api/agent/stream
    res = client.post(
        "/api/agent/stream",
        json={"question": question, "session_id": session_id, "user_id": user_id},
    )
    assert res.status_code == 200
    mock_stream.assert_not_called()

    body = res.text
    assert '"node_id": "cache"' in body, "SSE stream phải chứa node_id='cache'"
    assert '"cache_hit": true' in body, "SSE detail phải có cache_hit=true"
    assert "Tổng số lượt xe vào hôm nay là 250 lượt." in body


# ------------------------------------------------------------------------------
# Test 5: Stream API yêu cầu session_id và user_id hợp lệ
# ------------------------------------------------------------------------------
def test_mock_testclient_stream_validation():
    """Endpoint /api/agent/stream từ chối request thiếu session_id hoặc user_id với HTTP 400."""
    res1 = client.post("/api/agent/stream", json={"question": "Test", "session_id": "", "user_id": "u1"})
    assert res1.status_code == 400
    assert "session_id" in res1.json()["detail"]

    res2 = client.post("/api/agent/stream", json={"question": "Test", "session_id": "s1", "user_id": "  "})
    assert res2.status_code == 400
    assert "user_id" in res2.json()["detail"]


# ------------------------------------------------------------------------------
# Test 6: Offline verification of the inline Python SSE parser logic
# ------------------------------------------------------------------------------
def test_smoke_sse_parser_offline_logic():
    """Kiểm tra logic phân tích SSE parser inline với các mẫu event thực tế."""
    sample_sse = (
        'data: {"node_id": "recall_memory", "status": "done", "output": []}\n\n'
        'data: {"node_id": "__chart__", "status": "done", "chart_type": "bar", "chart_spec": {"chart_type": "bar"}}\n\n'
        'data: {"node_id": "__answer__", "status": "done", "output": "Biểu đồ cột xe vào hôm nay.", "detail": {"chart_type": "bar"}}\n\n'
    )

    events = []
    for line in sample_sse.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                events.append(json.loads(payload))

    answer = ""
    has_chart = False
    chart_type = ""

    for ev in events:
        if ev.get("node_id") == "__chart__":
            has_chart = True
            chart_type = ev.get("chart_type") or ""
        elif ev.get("node_id") == "__answer__":
            answer = ev.get("output", "")

    assert has_chart is True
    assert chart_type == "bar"
    assert answer == "Biểu đồ cột xe vào hôm nay."
