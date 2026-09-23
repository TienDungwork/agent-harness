"""Unit tests for Dual LLM backend integration (OpenAI & Self-hosted Qwen3-4B)."""

from __future__ import annotations

import pytest
from langchain_openai import ChatOpenAI

from src.llm import (
    _BACKENDS,
    _RotatingKeyPool,
    base_llm,
    use_offline_tools,
)
from src.config import settings


def test_backends_registry_contains_required_providers():
    """Kiểm tra registry chứa đầy đủ 'openai' và 'self_hosted'."""
    assert "openai" in _BACKENDS
    assert "self_hosted" in _BACKENDS
    assert _BACKENDS["self_hosted"].default_base_url == "http://192.168.1.196:18083/v1"
    assert _BACKENDS["self_hosted"].requires_real_key is False


def test_base_llm_self_hosted_configuration(monkeypatch):
    """Kiểm tra khởi tạo ChatOpenAI cho model tự host qwen3-4b."""
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_base_url", "http://192.168.1.196:18083/v1")
    monkeypatch.setattr(settings, "model_name", "qwen3-4b")
    monkeypatch.setattr(settings, "model_api_key", "test-qwen-key")

    llm = base_llm(backend_override="self_hosted")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "qwen3-4b"
    assert str(llm.openai_api_base).rstrip("/") == "http://192.168.1.196:18083/v1"
    assert llm.openai_api_key.get_secret_value() == "test-qwen-key"


def test_base_llm_openai_cloud_configuration(monkeypatch):
    """Kiểm tra khởi tạo ChatOpenAI cho OpenAI Cloud gpt-4o-mini."""
    monkeypatch.setattr(settings, "openai_api_keys", "sk-proj-test1,sk-proj-test2")
    from src.llm import _pool
    _pool.cache_clear()

    llm = base_llm(backend_override="openai")
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "gpt-4o-mini"
    assert llm.openai_api_key.get_secret_value() in ["sk-proj-test1", "sk-proj-test2"]


def test_base_llm_invalid_backend_raises_value_error():
    """Backend không hợp lệ raise ValueError."""
    with pytest.raises(ValueError, match="không hợp lệ"):
        base_llm(backend_override="unsupported_provider")


def test_rotating_key_pool_round_robin_and_cooldown():
    """Kiểm tra key pool xoay vòng và cooldown khi gặp rate limit."""
    keys = ["key-1", "key-2", "key-3"]
    pool = _RotatingKeyPool(keys)

    # Round-robin
    first = pool.get_key()
    second = pool.get_key()
    third = pool.get_key()
    assert {first, second, third} == {"key-1", "key-2", "key-3"}

    # Đưa key-1 vào cooldown 60s
    pool.mark_limited("key-1", cooldown_seconds=60.0)

    # Lượt lấy tiếp theo không được trả về key-1 nếu còn key khác khả dụng
    retrieved = [pool.get_key() for _ in range(4)]
    assert "key-1" not in retrieved

from pathlib import Path

import pytest

from src.prompts import PromptRegistry, registry


def test_prompt_registry_default_dir_is_resource():
    reg = PromptRegistry()
    assert "resource" in reg.prompts_dir.parts
    assert reg.prompts_dir.as_posix().endswith("resource/prompts")
    assert reg.prompts_dir.is_dir()


def test_prompt_registry_get_by_version():
    reg = registry()
    prompt = reg.get("sql_agent", 1)
    assert prompt.name == "sql_agent"
    assert prompt.version == 1
    assert "PostgreSQL" in prompt.template


def test_prompt_registry_get_classify_production():
    reg = registry()
    prompt = reg.get("classify", "production")
    assert prompt.name == "classify"
    assert "Phân loại ý định câu người dùng" in prompt.template


def test_prompt_registry_render_success():
    reg = registry()
    rendered = reg.render("sql_agent", "production")
    assert "PostgreSQL" in rendered
    assert "SELECT" in rendered


def test_prompt_registry_non_existent_prompt_raises_file_not_found():
    reg = registry()
    with pytest.raises(FileNotFoundError):
        reg.get("non_existent_prompt", 1)


ALL_PROMPT_NAMES = [
    "answer_docs",
    "classify",
    "judge_eval",
    "memory_extract",
    "orchestrator",
    "plan_chart",
    "respond_stat",
    "rewrite",
    "sql_agent",
]


@pytest.mark.parametrize("prompt_name", ALL_PROMPT_NAMES)
def test_each_prompt_name_loads(prompt_name: str):
    """Kiểm tra từng prompt name trong resource/prompts/ load thành công qua registry."""
    reg = registry()
    prompt = reg.get(prompt_name, "production")
    assert prompt.name == prompt_name
    assert prompt.version >= 1
    assert len(prompt.template.strip()) > 0


def test_render_missing_var_raises_value_error_for_prompt_with_vars(monkeypatch):
    """Kiểm tra render prompt có chứa biến khi thiếu biến sẽ raise ValueError."""
    from unittest.mock import patch
    from src.prompts.registry import Prompt

    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_vars", version=1, template="Xin chào {now}, user là {user}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_vars")
        assert "test_vars" in str(exc_info.value)
        assert "thiếu biến" in str(exc_info.value).lower()
        assert "now" in str(exc_info.value)


def test_api_llm_ping_returns_metadata():
    """Kiểm tra GET /api/llm/ping trả về {status, backend, model, base_url}."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from src.main import app

    tc = TestClient(app)
    with patch("src.main.llm_ping", return_value="OK"):
        res = tc.get("/api/llm/ping")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "OK"
        assert data["backend"] == settings.llm_backend
        assert data["model"] == settings.effective_model
        assert "base_url" in data


