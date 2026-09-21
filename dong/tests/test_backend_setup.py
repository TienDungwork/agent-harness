"""Test Backend Setup & Frontend UI serving."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.main import app

client = TestClient(app)


def test_backend_health_endpoint():
    """Kiểm tra endpoint /api/health trả về trạng thái hợp lệ."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "active_model" in data
    assert "llm_backend" in data


def test_backend_models_endpoint():
    """Kiểm tra endpoint /api/models trả về danh sách model hỗ trợ (OpenAI + Qwen3-4B)."""
    res = client.get("/api/models")
    assert res.status_code == 200
    data = res.json()
    assert "supported_models" in data
    model_ids = [m["id"] for m in data["supported_models"]]
    assert "gpt-4o-mini" in model_ids
    assert "qwen3-4b" in model_ids


def test_dual_model_settings():
    """Kiểm tra Settings giải quyết đúng base_url và model cho self_hosted."""
    s = Settings(
        LLM_BACKEND="self_hosted",
        MODEL_BASE_URL="http://192.168.1.196:18083/v1",
        MODEL_NAME="qwen3-4b",
    )
    assert s.effective_base_url == "http://192.168.1.196:18083/v1"
    assert s.effective_model == "qwen3-4b"


def test_frontend_index_served():
    """Kiểm tra endpoint GET / phục vụ giao diện Claude UI frontend."""
    res = client.get("/")
    assert res.status_code == 200
    assert "agent_ATIN" in res.text
    assert "chat-viewport" in res.text
    assert "settings-modal" in res.text
