"""Unit & integration tests for Phase 7: Docker + LLM_BACKEND=self_hosted (196)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from src.config import Settings, settings
from src.main import app

client = TestClient(app)


def test_docker_compose_ai_backend_self_hosted_environment():
    """docker-compose.yml ai_backend environment phải có đầy đủ passthrough self_hosted @ 196."""
    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml phải tồn tại"

    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = data.get("services", {})
    assert "ai_backend" in services, "ai_backend service phải có trong docker-compose.yml"

    backend = services["ai_backend"]
    env = backend.get("environment", {})

    # Kiểm tra các biến LLM self_hosted với default production
    assert "LLM_BACKEND" in env
    assert env["LLM_BACKEND"] == "${LLM_BACKEND:-self_hosted}"

    assert "MODEL_BASE_URL" in env
    assert env["MODEL_BASE_URL"] == "${MODEL_BASE_URL:-http://192.168.1.196:18083/v1}"

    assert "MODEL_NAME" in env
    assert env["MODEL_NAME"] == "${MODEL_NAME:-qwen3-4b}"

    assert "MODEL_API_KEY" in env
    assert env["MODEL_API_KEY"] == "${MODEL_API_KEY:-}"

    assert "MODEL_ENDPOINT" in env
    assert env["MODEL_ENDPOINT"] == "${MODEL_ENDPOINT:-http://192.168.1.196:18083/v1/chat/completions}"

    # Đảm bảo cấu hình mạng và host không bị ảnh hưởng
    assert "host.docker.internal:host-gateway" in backend.get("extra_hosts", [])
    assert "kcn_network" in backend.get("networks", [])


def test_settings_self_hosted_defaults():
    """Cấu hình Settings khi LLM_BACKEND=self_hosted phải trỏ đúng gateway 196 và qwen3-4b."""
    s = Settings(
        LLM_BACKEND="self_hosted",
        MODEL_BASE_URL="http://192.168.1.196:18083/v1",
        MODEL_NAME="qwen3-4b",
    )
    assert s.llm_backend == "self_hosted"
    assert s.effective_base_url == "http://192.168.1.196:18083/v1"
    assert s.effective_model == "qwen3-4b"
    assert s.model_endpoint == "http://192.168.1.196:18083/v1/chat/completions"


def test_api_health_self_hosted_backend(monkeypatch):
    """GET /api/health trả về llm_backend=self_hosted và active_model=qwen3-4b."""
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_name", "qwen3-4b")

    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["llm_backend"] == "self_hosted"
    assert data["active_model"] == "qwen3-4b"


def test_api_llm_ping_self_hosted_success(monkeypatch):
    """GET /api/llm/ping trả về backend self_hosted + model qwen3-4b khi gateway sẵn sàng."""
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_name", "qwen3-4b")
    monkeypatch.setattr(settings, "model_base_url", "http://192.168.1.196:18083/v1")

    with patch("src.main.llm_ping", return_value="OK"):
        res = client.get("/api/llm/ping")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "OK"
        assert data["backend"] == "self_hosted"
        assert data["model"] == "qwen3-4b"
        assert data["base_url"] == "http://192.168.1.196:18083/v1"


def test_api_llm_ping_self_hosted_failure(monkeypatch):
    """GET /api/llm/ping trả về HTTP 503 khi gateway 196 không phản hồi."""
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_name", "qwen3-4b")
    monkeypatch.setattr(settings, "model_base_url", "http://192.168.1.196:18083/v1")

    err_msg = "Lỗi kết nối tới LLM tại http://192.168.1.196:18083/v1/models: Connection refused"
    with patch("src.main.llm_ping", side_effect=RuntimeError(err_msg)):
        res = client.get("/api/llm/ping")
        assert res.status_code == 503
        data = res.json()
        assert "Connection refused" in data["detail"]


def test_verify_docker_script_exists_and_executable():
    """Script scripts/verify-docker-self-hosted.sh tồn tại, executable và kiểm tra đúng logic."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify-docker-self-hosted.sh"
    assert script_path.exists(), "scripts/verify-docker-self-hosted.sh phải tồn tại"
    assert os.access(script_path, os.X_OK), "scripts/verify-docker-self-hosted.sh phải có quyền thực thi (executable)"

    content = script_path.read_text(encoding="utf-8")
    assert "/api/health" in content
    assert "/api/llm/ping" in content
    assert "self_hosted" in content


def test_env_example_documentation_block():
    """.env.example ghi rõ cấu hình production Docker self_hosted và các biến bắt buộc."""
    env_example_path = Path(__file__).resolve().parent.parent / ".env.example"
    assert env_example_path.exists()
    content = env_example_path.read_text(encoding="utf-8")

    assert "self_hosted" in content
    assert "192.168.1.196:18083" in content
    assert "MODEL_API_KEY" in content
    assert "DB_HOST" in content
    assert "LLM_BACKEND=openai" in content
