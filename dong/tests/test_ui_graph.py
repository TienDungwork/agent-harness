"""Integration tests verifying frontend UI assets and Backend API connection."""

from __future__ import annotations

from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_frontend_assets_served_and_valid():
    """Kiểm tra Frontend HTML được phục vụ đúng và chứa các thành phần cốt lõi."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    # Kiểm tra liên kết script và stylesheet
    assert 'href="style.css"' in html
    assert 'src="app.js"' in html
    # Kiểm tra 8 domain tags
    assert "Phương tiện (ITS)" in html
    assert "Vùng cấm (Fence)" in html
    assert "Khuôn mặt (Face)" in html
    assert "Ẩu đả (Fight)" in html
    assert "Đám đông (Crowd)" in html
    assert "Leo trèo (Intrusion)" in html
    assert "Cháy khói (Fire)" in html
    assert "Mực nước (Water)" in html


def test_api_chat_contract_for_frontend():
    """Kiểm tra hợp đồng dữ liệu /api/chat khớp chính xác cấu trúc mà app.js yêu cầu."""
    payload = {
        "question": "Hôm nay có bao nhiêu lượt xe vào?",
        "model_provider": "openai",
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "question" in data
    assert "answer" in data
    assert "tool" in data
    assert "detail" in data
    assert isinstance(data["detail"], dict)

def test_frontend_app_js_stream():
    """Kiểm tra app.js đã chuyển sang dùng stream thực, thay vì mock graph."""
    res = client.get("/app.js")
    if res.status_code == 404:
        # Fallback to reading file directly if StaticFiles is not set up correctly in test
        with open("frontend/app.js", "r", encoding="utf-8") as f:
            js = f.read()
    else:
        js = res.text
    
    assert "/api/agent/stream" in js
    assert "getReader" in js or "ReadableStream" in js
    # check mock graph is disabled on send
    assert "runMockGraph(question);" not in js
    # check upsertGraphNode is called in the SSE parsing block
    assert "upsertGraphNode(event.node_id" in js

    # check node IO hover/click behavior
    assert "function showNodeIo" in js
    assert "addEventListener('click', () => showNodeIo" in js
    assert "addEventListener('mouseenter', () => showNodeIo" in js
    assert "IO_MAX_CHARS" in js or "2000" in js
    assert "status !== 'done'" in js

    # check reset graph is called on new message
    handle_send = js.split("function handleSendMessage")[1]
    assert "resetGraph()" in handle_send

    # Phase 7 checks: Real API endpoint is used and Phase 2 mock is gone
    assert "Backend chưa bắt buộc" not in js
    assert "Graph bên phải đang chạy mock" not in js
    
    # Verify single stream logic
    assert "getApiEndpoint('/api/chat')" not in handle_send, "handleSendMessage should not call /api/chat"
    assert "event.node_id === '__answer__'" in handle_send, "Must handle __answer__ event"
    assert "removeThinkingIndicator()" in handle_send, "Must clear thinking indicator"
    
    # Phase 7 UI display checks: assert appendMessage assistant path and row_count handling
    assert "appendMessage('assistant'" in handle_send
    assert "detail.row_count > 0" in js

def test_frontend_settings_api_url_wiring():
    """Kiểm tra input-api-url / getApiEndpoint / agent_api_base_url wiring."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert 'id="input-api-url"' in html
    assert 'FastAPI (src.main:app)' in html

    res = client.get("/app.js")
    if res.status_code == 404:
        with open("frontend/app.js", "r", encoding="utf-8") as f:
            js = f.read()
    else:
        js = res.text
        
    assert "agent_api_base_url" in js
    assert "getApiEndpoint(" in js
    assert "state.apiBaseUrl.replace(/\\/+$/, '')" in js
