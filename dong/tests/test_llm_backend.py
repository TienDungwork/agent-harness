"""Unit tests for Dual LLM backend integration (OpenAI & Self-hosted Qwen3-4B)."""

from __future__ import annotations

import pytest
from langchain_openai import ChatOpenAI

from backend.llm import (
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
