"""Tests for Phase 3b: Chart hint pre-SQL (build_chart_sql_hint + injection into text-to-SQL).

All tests run offline (mock LLM/DB) — no network required.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.generate_sql import generate_sql_node
from src.agent.pre_sql import build_chart_sql_hint
from src.llm.schemas import RewrittenQuestion


# ── 1. build_chart_sql_hint unit tests ────────────────────────────────────────

def test_chart_hint_no_chart_keyword_returns_empty():
    """Câu hỏi không có từ khóa biểu đồ → trả về \"\"."""
    assert build_chart_sql_hint("xin chào") == ""
    assert build_chart_sql_hint("Có bao nhiêu xe vào hôm nay?") == ""
    assert build_chart_sql_hint("") == ""
    assert build_chart_sql_hint("Thống kê lượt xe") == ""


def test_chart_hint_vehicle_chart_returns_vehicle_type_group_by():
    """Câu hỏi biểu đồ + từ khóa xe/phương tiện (không hướng) → hint GROUP BY vehicle_type."""
    hint = build_chart_sql_hint("Vẽ biểu đồ cột lượt xe theo loại hôm nay")
    assert hint != ""
    assert "vehicle_type" in hint
    assert "GROUP BY" in hint.upper() or "group by" in hint.lower()


def test_chart_hint_vehicle_chart_mentions_no_direction_group():
    """Hint xe không chứa GROUP BY direction khi không hỏi hướng."""
    hint = build_chart_sql_hint("Vẽ biểu đồ số lượng phương tiện theo loại")
    assert hint != ""
    assert "vehicle_type" in hint
    assert "direction" in hint.lower()


def test_chart_hint_direction_focused_returns_generic():
    """Câu hỏi biểu đồ + hướng rõ ràng → generic hint."""
    hint = build_chart_sql_hint("Vẽ biểu đồ lượt xe vào ra theo hướng")
    assert hint != ""
    assert "GROUP BY" in hint.upper() or "group by" in hint.lower()


def test_chart_hint_non_vehicle_chart_returns_generic():
    """Câu hỏi biểu đồ không liên quan xe → generic hint."""
    hint = build_chart_sql_hint("Vẽ biểu đồ thống kê sự kiện cháy khói")
    assert hint != ""
    assert "GROUP BY" in hint.upper() or "group by" in hint.lower()
    assert "vehicle_type" not in hint


def test_chart_hint_generic_contains_expected_structure():
    """Generic hint phải đề cập GROUP BY nhãn + 2 cột + ORDER BY + LIMIT."""
    hint = build_chart_sql_hint("Vẽ biểu đồ sự kiện hàng ngày")
    assert hint != ""
    assert "GROUP BY" in hint.upper() or "group by" in hint.lower()
    assert "count" in hint.lower() or "COUNT" in hint
    assert "ORDER BY" in hint.upper() or "order by" in hint.lower()
    assert "LIMIT" in hint.upper() or "limit" in hint.lower()


# ── 2. Online generate_sql_node: chart hint in user prompt ─────────────────────

@patch("src.agent.generate_sql.use_offline_tools", return_value=False)
@patch("src.agent.generate_sql.invoke_text", return_value="SELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type")
def test_generate_sql_online_injects_chart_hint_for_bieu_do(mock_invoke, _mock_offline):
    """Câu hỏi có 'biểu đồ' → user prompt của generate_sql_node chứa chart hint."""
    rewritten = RewrittenQuestion(
        text="Vẽ biểu đồ cột lượt xe theo loại hôm nay",
        time_range="today",
    )
    state = {
        "question": "Vẽ biểu đồ cột lượt xe theo loại hôm nay",
        "rewritten": rewritten,
        "schema_excerpt": "Table: plate_event",
    }
    res = generate_sql_node(state)
    assert res["sql"] != ""
    assert mock_invoke.called
    _sys_prompt, user_prompt = mock_invoke.call_args[0][:2]

    # Chart hint must be present in user prompt
    assert "vehicle_type" in user_prompt
    assert "GROUP BY" in user_prompt.upper()
    # Time hint also present
    assert "Khoảng thời gian" in user_prompt
    # Schema + question also present
    assert "Table: plate_event" in user_prompt
    assert "Vẽ biểu đồ cột lượt xe theo loại hôm nay" in user_prompt


@patch("src.agent.generate_sql.use_offline_tools", return_value=False)
@patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
def test_generate_sql_online_no_chart_hint_for_plain_count(mock_invoke, _mock_offline):
    """Câu hỏi thống kê thông thường (không có từ khóa biểu đồ) → KHÔNG có chart hint."""
    rewritten = RewrittenQuestion(
        text="Hôm nay có bao nhiêu xe vào?",
        time_range="today",
    )
    state = {
        "question": "Hôm nay có bao nhiêu xe vào?",
        "rewritten": rewritten,
        "schema_excerpt": "Table: plate_event",
    }
    res = generate_sql_node(state)
    assert res["sql"] != ""
    assert mock_invoke.called
    _sys_prompt, user_prompt = mock_invoke.call_args[0][:2]

    # No chart hint
    assert "Yêu cầu biểu đồ" not in user_prompt
    # Time hint still present
    assert "Khoảng thời gian" in user_prompt
