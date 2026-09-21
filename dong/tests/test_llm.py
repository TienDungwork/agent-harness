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

from src.agent.answer import _get_system_prompt
from src.agent.graph import _system_prompt
from src.prompts import PromptRegistry, registry


def test_prompt_registry_get_by_version():
    reg = registry()
    prompt = reg.get("agent_system", 1)
    assert prompt.name == "agent_system"
    assert prompt.version == 1
    assert "{now}" in prompt.template


def test_prompt_registry_get_answer_v1():
    reg = registry()
    prompt = reg.get("answer", version=1)
    assert prompt.name == "answer"
    assert prompt.version == 1

    prompt_v_str = reg.get("answer", version="v1")
    assert prompt_v_str.version == 1


def test_prompt_registry_get_production():
    reg = registry()
    prompt = reg.get("agent_system", "production")
    assert prompt.name == "agent_system"
    assert prompt.version == 1


def test_prompt_registry_render_success():
    reg = registry()
    rendered = reg.render("agent_system", "production", now="2026-09-18 12:00:00")
    assert "2026-09-18 12:00:00" in rendered
    assert "Bạn là trợ lý thống kê xe ra/vào" in rendered


def test_prompt_registry_render_missing_variable_raises_value_error():
    reg = registry()
    with pytest.raises(ValueError) as exc_info:
        reg.render("agent_system", "production")
    assert "Thiếu biến khi render prompt" in str(exc_info.value)
    assert "now" in str(exc_info.value)


def test_prompt_registry_non_existent_prompt_raises_file_not_found():
    reg = registry()
    with pytest.raises(FileNotFoundError):
        reg.get("non_existent_prompt", 1)


def test_agent_graph_system_prompt_integration():
    sys_prompt = _system_prompt()
    assert "Bạn là trợ lý thống kê xe ra/vào" in sys_prompt
    assert "Thời điểm hiện tại" in sys_prompt


def test_agent_answer_system_prompt_integration():
    ans_prompt = _get_system_prompt()
    assert "Bạn viết câu trả lời tiếng Việt ngắn gọn cho câu hỏi thống kê" in ans_prompt


def test_prompt_registry_switch_production_alias_and_rollback():
    """Test 3 & 4 trong test-plan.md:
    Đổi production.txt từ '1' sang '2' (không sửa code) -> agent dùng v2.
    Revert production.txt về '1' (rollback) -> agent quay lại v1.
    """
    prod_file = Path(__file__).resolve().parent.parent / "prompts" / "agent_system" / "production.txt"
    original_version = prod_file.read_text("utf-8").strip()

    try:
        # Step 1: Đổi production.txt sang version 2 (KHÔNG sửa code Python)
        prod_file.write_text("2\n", encoding="utf-8")

        # Verify: _system_prompt() load ngay prompt v2
        sys_prompt_v2 = _system_prompt()
        assert "[v2]" in sys_prompt_v2
        assert "xâm nhập khu vực v2" in sys_prompt_v2

        # Step 2: Rollback = trỏ production.txt về version 1
        prod_file.write_text("1\n", encoding="utf-8")

        # Verify: _system_prompt() quay lại prompt v1
        sys_prompt_v1 = _system_prompt()
        assert "[v2]" not in sys_prompt_v1
        assert "Bạn là trợ lý thống kê xe ra/vào" in sys_prompt_v1

    finally:
        # Đảm bảo file production.txt luôn được khôi phục về trạng thái ban đầu
        prod_file.write_text(f"{original_version}\n", encoding="utf-8")
