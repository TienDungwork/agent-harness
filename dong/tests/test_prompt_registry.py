"""Tests for Prompt Registry (Phase 9 - Item 9.3 & full suite).

Kiểm tra:
1. get(), render(), validation biến.
2. Đổi production.txt trỏ version 2 không sửa code -> agent load ngay v2.
3. Revert production.txt về 1 (rollback) -> agent load lại v1.
4. Pytest offline chạy sạch không phụ thuộc API key/DB.
"""

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
