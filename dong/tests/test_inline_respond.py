"""Unit tests for inline_respond module and graph respond_inline flow (chat & out_of_scope)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.guardrail_nodes import _build_output_evidence
from src.agent.inline_respond import generate_inline_response, get_system_time_vietnam
from src.agent.graph import Agent_Output, respond_inline_node, respond_node
from src.guardrails import check_output


def test_get_system_time_vietnam():
    """get_system_time_vietnam trả về chuỗi có ngày tháng năm và múi giờ Việt Nam."""
    t_str = get_system_time_vietnam()
    assert "ngày" in t_str
    assert "Giờ Việt Nam" in t_str
    assert any(day in t_str for day in ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"])


def test_generate_inline_response_offline_chat():
    """Offline chat trả về lời chào lịch sự và gợi ý chủ đề VMS."""
    with patch("src.agent.inline_respond.use_offline_tools", return_value=True):
        ans = generate_inline_response("chào bạn", intent="chat")
        assert "Chào bạn" in ans
        assert "VMS KCN Hưng Phú" in ans
        assert any(kw in ans.lower() for kw in ("xe", "an ninh", "aioc"))


def test_generate_inline_response_offline_out_of_scope_date():
    """Offline out_of_scope câu hỏi ngày giờ trả về ngày hiện tại và định hướng VMS."""
    with patch("src.agent.inline_respond.use_offline_tools", return_value=True):
        ans = generate_inline_response("hôm nay là ngày bao nhiêu", intent="out_of_scope")
        assert "Hôm nay là" in ans
        assert "VMS KCN Hưng Phú" in ans
        assert any(kw in ans.lower() for kw in ("xe", "an ninh"))


def test_generate_inline_response_offline_out_of_scope_general():
    """Offline out_of_scope câu hỏi chung chung trả về định hướng VMS."""
    with patch("src.agent.inline_respond.use_offline_tools", return_value=True):
        ans = generate_inline_response("thời tiết hôm nay thế nào", intent="out_of_scope")
        assert "VMS" in ans
        assert any(kw in ans.lower() for kw in ("xe", "vùng cấm", "khuôn mặt", "aioc"))


def test_generate_inline_response_online():
    """Online invoke_text gọi LLM sinh câu trả lời có định hướng dẫn dắt."""
    mock_llm_reply = (
        "Hôm nay là ngày 25/09/2026. Chuyên môn chính của tôi là hỗ trợ giám sát camera VMS KCN Hưng Phú. "
        "Bạn có muốn kiểm tra lượng xe vào hôm nay không?"
    )
    with patch("src.agent.inline_respond.use_offline_tools", return_value=False), \
         patch("src.agent.inline_respond.invoke_text", return_value=mock_llm_reply):
        ans = generate_inline_response("hôm nay là ngày bao nhiêu", intent="out_of_scope")
        assert ans == mock_llm_reply


def test_generate_inline_response_fallback_on_error():
    """Khi LLM gặp ngoại lệ, generate_inline_response tự động fallback sang phản hồi an toàn."""
    with patch("src.agent.inline_respond.use_offline_tools", return_value=False), \
         patch("src.agent.inline_respond.invoke_text", side_effect=RuntimeError("LLM connection timeout")):
        ans = generate_inline_response("thời tiết hôm nay thế nào", intent="out_of_scope")
        assert "VMS KCN Hưng Phú" in ans
        assert "Hôm nay là" in ans


def test_respond_inline_node_chat_and_out_of_scope():
    """respond_inline_node gán câu trả lời động và respond_mode tương ứng."""
    with patch("src.agent.inline_respond.generate_inline_response", return_value="Phản hồi thử nghiệm"):
        res_chat = respond_inline_node({"question": "chào bạn", "intent": "chat"})
        assert res_chat["answer"] == "Phản hồi thử nghiệm"
        assert res_chat["respond_mode"] == "inline"

        res_oos = respond_inline_node({"question": "hôm nay là ngày mấy", "intent": "out_of_scope"})
        assert res_oos["answer"] == "Phản hồi thử nghiệm"
        assert res_oos["respond_mode"] == "out_of_scope"


def test_evidence_includes_answer_for_inline_preventing_disclaimer():
    """_build_output_evidence thêm answer vào evidence khi không có query, tránh disclaimer sai số liệu."""
    state = {"respond_mode": "out_of_scope", "question": "hôm nay là ngày bao nhiêu"}
    result = Agent_Output(
        question="hôm nay là ngày bao nhiêu",
        answer="Hôm nay là ngày 25/09/2026. Tôi hỗ trợ VMS KCN Hưng Phú.",
        detail="out_of_scope",
    )
    ev = _build_output_evidence(state, result)
    assert any("25/09/2026" in item for item in ev)

    # Chạy qua check_output bảo đảm không bị gắn disclaimer
    checked = check_output(result.answer, ev, tool_empty=False)
    assert "chưa xác minh" not in checked.answer
