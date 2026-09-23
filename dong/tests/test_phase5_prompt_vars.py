"""Phase 5 — Thiếu biến prompt: lỗi rõ (không template trống).

Kiểm tra:
1. Template rỗng hoặc whitespace-only trước render -> ValueError có tên prompt.
2. Thiếu biến bắt buộc -> ValueError có tên prompt + danh sách biến thiếu tiếng Việt.
3. Render ra chuỗi rỗng -> ValueError có tên prompt.
4. Render còn placeholder chưa thay thế -> ValueError có tên prompt + placeholder.
5. Render thành công agent_system với now=...
6. _format_error_message maps prompt ValueError sang câu tiếng Việt thân thiện cho người dùng.
7. Integration: lỗi prompt trong /api/chat -> 503 friendly message.
8. Integration: lỗi prompt trong /api/agent/stream -> __answer__ error SSE friendly message.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import USER_ERROR_MAX_LEN, _format_error_message, app
from src.prompts.registry import Prompt, PromptRegistry, registry

client = TestClient(app)


def test_empty_template_raises_value_error_with_prompt_name():
    """Template rỗng trước render phải raise ValueError kèm tên prompt."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_empty", version=1, template="")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_empty")
        err = str(exc_info.value)
        assert "test_empty" in err
        assert "template rỗng" in err.lower()


def test_whitespace_template_raises_value_error_with_prompt_name():
    """Template chỉ chứa khoảng trắng/xuống dòng phải raise ValueError kèm tên prompt."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_ws", version=1, template="  \n\t  ")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_ws")
        err = str(exc_info.value)
        assert "test_ws" in err
        assert "template rỗng" in err.lower()


def test_missing_required_var_raises_value_error_with_name_and_var():
    """Thiếu biến bắt buộc phải raise ValueError kèm tên prompt và tên biến thiếu."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_prompt_vars", version=1, template="Xin chào {now}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_prompt_vars")
        err = str(exc_info.value)
        assert "test_prompt_vars" in err
        assert "now" in err
        assert "thiếu biến" in err.lower()


def test_render_resulting_in_empty_string_raises_value_error():
    """Template sau khi render ra chuỗi rỗng phải raise ValueError."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_blank_output", version=1, template="{content}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_blank_output", content="   ")
        err = str(exc_info.value)
        assert "test_blank_output" in err
        assert "rỗng" in err.lower()


def test_unreplaced_placeholder_raises_value_error():
    """Placeholder chưa được thay thế còn sót lại trong kết quả render phải raise ValueError."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_placeholder", version=1, template="Xin chào {user}")
    with patch.object(reg, "get", return_value=fake_prompt):
        with pytest.raises(ValueError) as exc_info:
            reg.render("test_placeholder", user="{unreplaced_var}")
        err = str(exc_info.value)
        assert "test_placeholder" in err
        assert "placeholder" in err.lower()
        assert "unreplaced_var" in err


def test_successful_render_prompt_with_vars():
    """Render thành công prompt với tham số."""
    reg = PromptRegistry()
    fake_prompt = Prompt(name="test_prompt_vars", version=1, template="Thời gian là {now}")
    with patch.object(reg, "get", return_value=fake_prompt):
        rendered = reg.render("test_prompt_vars", "production", now="2026-09-22 15:30:00")
        assert "2026-09-22 15:30:00" in rendered
        assert len(rendered.strip()) > 0


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
        ValueError("Prompt 'test_empty' có template rỗng"),
        ValueError("Prompt 'test_render' sau khi render có nội dung rỗng"),
        ValueError("Prompt 'test_ph' còn chứa placeholder chưa thay thế: ['{var}']"),
        ValueError("Thiếu biến khi render prompt: ['now']"),
    ],
)
def test_format_error_message_maps_prompt_errors_to_user_friendly(exc: Exception):
    """_format_error_message phải map các lỗi cấu hình prompt sang thông báo ngắn gọn tiếng Việt."""
    msg = _format_error_message(exc)
    assert msg == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "thiếu biến khi render prompt" not in msg.lower()
    assert "now" not in msg
    assert "test_empty" not in msg
    assert len(msg) <= USER_ERROR_MAX_LEN


def test_format_error_message_no_stack_or_template_leak():
    """Thông báo lỗi prompt không được leak traceback hoặc nội dung template."""
    exc = ValueError("Prompt 'agent_system' thiếu biến: ['now']\nTraceback: file.py line 123 SELECT * FROM vehicles")
    msg = _format_error_message(exc)
    assert "traceback" not in msg.lower()
    assert "select" not in msg.lower()
    assert "file.py" not in msg
    assert msg == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."


def test_api_chat_prompt_error_returns_503_friendly_message():
    """Lỗi prompt trong /api/chat trả về HTTP 503 với thông báo tiếng Việt thân thiện."""
    with patch(
        "src.main.run_agent",
        side_effect=ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
    ):
        res = client.post(
            "/api/chat",
            json={
                "question": "Hôm nay có bao nhiêu lượt xe vào?",
                "session_id": "session-test-prompt",
                "user_id": "user-test",
            },
        )
    assert res.status_code == 503
    detail = res.json().get("detail", "")
    assert detail == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "now" not in detail


def test_api_stream_prompt_error_yields_friendly_answer_sse(monkeypatch):
    """Lỗi prompt trong /api/agent/stream không làm crash generator, trả về __answer__ error."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache

    _cache.clear()

    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=ValueError("Prompt 'agent_system' thiếu biến: ['now']"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={
                "question": "Hôm nay có bao nhiêu lượt xe vào?",
                "session_id": "session-test-stream",
                "user_id": "user-test",
            },
        )
    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))
    answer = next(ev for ev in events if ev.get("node_id") == "__answer__")
    assert answer.get("status") == "error"
    assert answer.get("output") == "Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."
    assert "traceback" not in str(answer.get("output", "")).lower()
