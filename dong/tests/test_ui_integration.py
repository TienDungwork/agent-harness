"""Integration tests verifying frontend UI assets and Backend API connection."""

from __future__ import annotations

from fastapi.testclient import TestClient
from backend.main import app

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
