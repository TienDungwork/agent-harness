"""Tests for generate_sql node — Phase 3c.

Coverage:
- extract_sql: fenced ```sql, bare SQL, trailing semicolon, empty
- Offline: SELECT count(*) FROM plate_event; today → CURRENT_DATE
- Online mock: invoke_text called with max_tokens; extract from response
- Empty extract → error VI ngắn, sql=""
- Hints optional (time_range / chart hint injected when present)
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from src.agent.generate_sql import extract_sql, generate_sql_node


# ---------------------------------------------------------------------------
# extract_sql unit tests
# ---------------------------------------------------------------------------


class TestExtractSql:
    """Test SQL extraction from LLM output."""

    def test_fenced_sql_block(self):
        text = "Đây là SQL:\n```sql\nSELECT * FROM plate_event\n```\nDone."
        assert extract_sql(text) == "SELECT * FROM plate_event"

    def test_fenced_without_sql_lang(self):
        text = "```\nSELECT count(*) FROM plate_event\n```"
        assert extract_sql(text) == "SELECT count(*) FROM plate_event"

    def test_bare_sql_no_fence(self):
        text = "SELECT count(*) FROM plate_event"
        assert extract_sql(text) == "SELECT count(*) FROM plate_event"

    def test_trailing_semicolon_stripped(self):
        text = "```sql\nSELECT 1;\n```"
        assert extract_sql(text) == "SELECT 1"

    def test_bare_trailing_semicolon(self):
        text = "SELECT count(*) FROM plate_event;"
        assert extract_sql(text) == "SELECT count(*) FROM plate_event"

    def test_empty_string(self):
        assert extract_sql("") == ""

    def test_none_input(self):
        assert extract_sql(None) == ""

    def test_whitespace_only(self):
        assert extract_sql("   \n  ") == ""

    def test_thinking_block_stripped(self):
        text = "<think>reasoning here</think>\n```sql\nSELECT 1\n```"
        assert extract_sql(text) == "SELECT 1"

    def test_unclosed_thinking_returns_empty(self):
        text = "<think>reasoning without closing"
        assert extract_sql(text) == ""

    def test_multiline_sql(self):
        text = "```sql\nSELECT vehicle_type, count(*) AS n\nFROM plate_event\nGROUP BY vehicle_type\nORDER BY n DESC\nLIMIT 30\n```"
        sql = extract_sql(text)
        assert "SELECT" in sql
        assert "GROUP BY" in sql
        assert not sql.endswith(";")

    def test_with_cte(self):
        text = "```sql\nWITH cte AS (SELECT 1) SELECT * FROM cte;\n```"
        result = extract_sql(text)
        assert result.startswith("WITH")
        assert not result.endswith(";")


# ---------------------------------------------------------------------------
# Offline generate_sql tests
# ---------------------------------------------------------------------------


class TestOfflineGenerateSql:
    """Offline mode: no LLM call, returns fixed SELECT."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_basic_select(self, _mock_offline):
        state = {"question": "Có bao nhiêu lượt xe?"}
        result = generate_sql_node(state)
        assert result["sql"] == "SELECT count(*) FROM plate_event"
        assert result["error"] == ""
        assert result["events"]
        assert result["events"][0]["meta"]["offline"] is True

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_today_adds_current_date(self, _mock_offline):
        state = {"question": "Hôm nay có bao nhiêu xe vào?"}
        result = generate_sql_node(state)
        assert "CURRENT_DATE" in result["sql"]
        assert "plate_event" in result["sql"]
        assert result["error"] == ""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_english_today(self, _mock_offline):
        state = {"question": "How many vehicles today?"}
        result = generate_sql_node(state)
        assert "CURRENT_DATE" in result["sql"]

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_no_today_no_date_filter(self, _mock_offline):
        state = {"question": "Tổng số lượt xe?"}
        result = generate_sql_node(state)
        assert "CURRENT_DATE" not in result["sql"]
        assert result["sql"] == "SELECT count(*) FROM plate_event"

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_prefers_rewritten_text(self, _mock_offline):
        rewritten = MagicMock()
        rewritten.text = "hôm nay có bao nhiêu lượt xe"
        state = {"question": "original question", "rewritten": rewritten}
        result = generate_sql_node(state)
        assert "CURRENT_DATE" in result["sql"]

    @patch("src.agent.generate_sql.use_offline_tools", return_value=True)
    def test_offline_returns_events(self, _mock_offline):
        state = {"question": "test", "user_id": "u1", "session_id": "s1"}
        result = generate_sql_node(state)
        ev = result["events"][0]
        assert ev["node_id"] == "generate_sql"
        assert ev["meta"]["user_id"] == "u1"
        assert ev["meta"]["session_id"] == "s1"


# ---------------------------------------------------------------------------
# Online generate_sql tests (mocked LLM)
# ---------------------------------------------------------------------------


class TestOnlineGenerateSql:
    """Online mode: LLM call with max_tokens, extract SQL from response."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_extracts_sql(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT count(*) FROM plate_event\n```"
        state = {
            "question": "Có bao nhiêu xe?",
            "schema_excerpt": "plate_event: ...",
        }
        result = generate_sql_node(state)
        assert result["sql"] == "SELECT count(*) FROM plate_event"
        assert result["error"] == ""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_passes_max_tokens(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        state = {"question": "test", "schema_excerpt": "..."}
        generate_sql_node(state)

        # invoke_text must have been called with max_tokens kwarg
        call_kwargs = mock_invoke.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 2048 or \
               (len(call_kwargs.args) >= 3 and False) or \
               call_kwargs[1].get("max_tokens") == 2048

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_custom_max_tokens(self, mock_invoke, _mock_offline, monkeypatch):
        """Custom SQL_GENERATE_MAX_TOKENS is forwarded."""
        from src.config import settings
        monkeypatch.setattr(settings, "sql_generate_max_tokens", 500)
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        state = {"question": "test", "schema_excerpt": "..."}
        generate_sql_node(state)
        assert mock_invoke.call_args.kwargs.get("max_tokens") == 500

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_empty_extract_returns_error(self, mock_invoke, _mock_offline):
        """Empty SQL extraction → error in Vietnamese, sql=''."""
        mock_invoke.return_value = "Tôi không hiểu câu hỏi."
        state = {"question": "???", "schema_excerpt": "..."}
        result = generate_sql_node(state)
        assert result["sql"] == ""
        assert result["error"] != ""
        # Error in Vietnamese
        assert any(c in result["error"] for c in ("Không", "không", "lỗi", "Lỗi"))

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_empty_response_returns_error(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = ""
        state = {"question": "test", "schema_excerpt": "..."}
        result = generate_sql_node(state)
        assert result["sql"] == ""
        assert result["error"] != ""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_online_uses_registry_sql_agent(self, mock_invoke, _mock_offline):
        """System prompt comes from registry('sql_agent')."""
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        state = {"question": "test", "schema_excerpt": "s"}
        generate_sql_node(state)
        system_arg = mock_invoke.call_args.args[0]
        # Must contain key rules from sql_agent prompt
        assert "SELECT" in system_arg
        assert "plate_event" in system_arg


# ---------------------------------------------------------------------------
# Hint injection tests
# ---------------------------------------------------------------------------


class TestHintInjection:
    """Time range and chart hints are injected into user prompt when available."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_time_range_hint_injected(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        rewritten = MagicMock()
        rewritten.text = "Hôm nay có bao nhiêu xe?"
        rewritten.time_range = "today"
        state = {
            "question": "Hôm nay có bao nhiêu xe?",
            "rewritten": rewritten,
            "schema_excerpt": "plate_event: ...",
        }
        generate_sql_node(state)
        user_prompt = mock_invoke.call_args.args[1]
        assert "time_range" in user_prompt.lower() or "CURRENT_DATE" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_chart_hint_injected_for_chart_question(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type\n```"
        state = {
            "question": "Vẽ biểu đồ lượt xe theo loại",
            "schema_excerpt": "plate_event: ...",
        }
        generate_sql_node(state)
        user_prompt = mock_invoke.call_args.args[1]
        # Chart hint should mention GROUP BY or biểu đồ
        assert "GROUP BY" in user_prompt or "biểu đồ" in user_prompt.lower()

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_no_hint_for_plain_question(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT count(*) FROM plate_event\n```"
        state = {
            "question": "Tổng số lượt xe",
            "schema_excerpt": "plate_event: ...",
        }
        generate_sql_node(state)
        user_prompt = mock_invoke.call_args.args[1]
        assert "Yêu cầu biểu đồ" not in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_schema_excerpt_in_user_prompt(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        state = {
            "question": "test",
            "schema_excerpt": "SPECIAL_SCHEMA_CONTENT",
        }
        generate_sql_node(state)
        user_prompt = mock_invoke.call_args.args[1]
        assert "SPECIAL_SCHEMA_CONTENT" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text")
    def test_question_in_user_prompt(self, mock_invoke, _mock_offline):
        mock_invoke.return_value = "```sql\nSELECT 1\n```"
        state = {
            "question": "MY_UNIQUE_QUESTION",
            "schema_excerpt": "...",
        }
        generate_sql_node(state)
        user_prompt = mock_invoke.call_args.args[1]
        assert "MY_UNIQUE_QUESTION" in user_prompt


# ---------------------------------------------------------------------------
# Config setting test
# ---------------------------------------------------------------------------


def test_config_sql_generate_max_tokens_default():
    """Settings has sql_generate_max_tokens = 2048 by default (updated in Phase 7)."""
    from src.config import Settings
    s = Settings(OPENAI_API_KEYS="test-key")
    assert s.sql_generate_max_tokens == 2048


# ---------------------------------------------------------------------------
# base_llm max_tokens_override test
# ---------------------------------------------------------------------------


def test_base_llm_max_tokens_override(monkeypatch):
    """base_llm(max_tokens_override=280) passes max_tokens to ChatOpenAI."""
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_keys", "sk-test")
    from src.llm.client import _pool
    _pool.cache_clear()

    from src.llm.client import base_llm
    llm = base_llm(backend_override="openai", max_tokens_override=280)
    assert llm.max_tokens == 280


def test_base_llm_no_max_tokens_by_default(monkeypatch):
    """base_llm() without max_tokens_override does not set max_tokens."""
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_keys", "sk-test")
    from src.llm.client import _pool
    _pool.cache_clear()

    from src.llm.client import base_llm
    llm = base_llm(backend_override="openai")
    assert llm.max_tokens is None
