"""Unit tests cho Node validate_sql & repair_sql (Phase 3c)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.validate_sql import repair_sql_node, validate_sql_node
from src.config import Settings, settings


# ── TestValidateSqlNode ───────────────────────────────────────────────────────


class TestValidateSqlNode:
    def test_valid_select_query(self):
        state = {"sql": "SELECT count(*) FROM plate_event", "user_id": "u1", "session_id": "s1"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is True
        assert out["sql_validation"]["reason"] == ""
        assert "error" not in out or out.get("error") == ""
        assert len(out["events"]) == 1
        assert out["events"][0]["node_id"] == "validate_sql"
        assert out["events"][0]["meta"]["ok"] is True

    def test_valid_cte_query(self):
        sql = "WITH t AS (SELECT count(*) AS cnt FROM plate_event) SELECT cnt FROM t"
        state = {"sql": sql}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is True

    def test_rejects_ddl_drop(self):
        state = {"sql": "DROP TABLE plate_event"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False
        assert "Chỉ cho phép câu lệnh bắt đầu bằng SELECT hoặc WITH" in out["sql_validation"]["reason"] or "DDL" in out["sql_validation"]["reason"]
        assert out.get("error") != ""
        assert out["events"][0]["meta"]["ok"] is False

    def test_rejects_dml_delete_in_body(self):
        state = {"sql": "SELECT * FROM plate_event; DELETE FROM plate_event"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False
        assert "multi-statement" in out["sql_validation"]["reason"].lower()

    def test_rejects_insert(self):
        state = {"sql": "INSERT INTO plate_event (id) VALUES (1)"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False

    def test_rejects_unknown_table(self):
        state = {"sql": "SELECT * FROM secret_user_passwords"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False
        assert "không nằm trong danh mục cho phép" in out["sql_validation"]["reason"]

    def test_rejects_empty_sql(self):
        state = {"sql": ""}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False
        assert "rỗng" in out["sql_validation"]["reason"]

    def test_rejects_column_mixing(self):
        # alert_level is from firesmoke_event, not plate_event
        state = {"sql": "SELECT alert_level FROM plate_event"}
        out = validate_sql_node(state)
        assert out["sql_validation"]["ok"] is False
        assert "không thuộc bảng" in out["sql_validation"]["reason"]


# ── TestRepairSqlNode ─────────────────────────────────────────────────────────


class TestRepairSqlNode:
    def test_offline_repair_basic(self):
        with patch("src.agent.validate_sql.use_offline_tools", return_value=True):
            state = {
                "sql": "SELECT bad_col FROM unknown_tbl",
                "question": "Có bao nhiêu xe vào cổng?",
                "repair_count": 0,
                "sql_validation": {"ok": False, "reason": "Bảng không tồn tại"},
            }
            out = repair_sql_node(state)
            assert out["sql"] == "SELECT count(*) FROM plate_event"
            assert out["repair_count"] == 1
            assert out["error"] == ""
            assert len(out["events"]) == 1
            assert out["events"][0]["node_id"] == "repair_sql"

    def test_offline_repair_today_keyword(self):
        with patch("src.agent.validate_sql.use_offline_tools", return_value=True):
            state = {
                "sql": "SELECT * FROM plate_event",
                "question": "Hôm nay có bao nhiêu lượt xe qua cổng?",
                "repair_count": 1,
            }
            out = repair_sql_node(state)
            assert "CURRENT_DATE" in out["sql"]
            assert out["repair_count"] == 2

    def test_online_repair_success(self):
        mock_llm_response = "```sql\nSELECT count(*) FROM plate_event\n```"
        captured_prompts: list[tuple[str, str, int | None]] = []

        def mock_invoke(sys, usr, max_tokens=None):
            captured_prompts.append((sys, usr, max_tokens))
            return mock_llm_response

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", side_effect=mock_invoke):
            state = {
                "sql": "SELECT bad FROM plate_event",
                "question": "Đếm số xe",
                "schema_excerpt": "CREATE TABLE plate_event (id int, event_time timestamp);",
                "repair_count": 0,
                "sql_validation": {"ok": False, "reason": "Cột bad không thuộc bảng"},
            }
            out = repair_sql_node(state)
            assert out["sql"] == "SELECT count(*) FROM plate_event"
            assert out["repair_count"] == 1
            assert out["error"] == ""

            # Check prompt contents
            assert len(captured_prompts) == 1
            sys, usr, max_tokens = captured_prompts[0]
            assert "Cột bad không thuộc bảng" in usr
            assert "SELECT bad FROM plate_event" in usr
            assert "Đếm số xe" in usr
            assert "plate_event" in usr
            assert max_tokens == settings.sql_generate_max_tokens

    def test_online_repair_empty_extract_fallback(self):
        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value="Xin lỗi tôi không thể sửa câu này."):
            state = {
                "sql": "SELECT bad FROM plate_event",
                "question": "Đếm số xe",
                "repair_count": 0,
            }
            out = repair_sql_node(state)
            assert out["sql"] == "SELECT bad FROM plate_event"
            assert out["repair_count"] == 1
            assert out["error"] != ""
            assert out["events"][0]["output"]["error"] == "empty_extract"

    def test_repair_max_limit_exceeded(self):
        state = {
            "sql": "SELECT bad FROM plate_event",
            "question": "Đếm số xe",
            "repair_count": 2,
            "error": "Cột bad không tồn tại.",
        }
        # With default SQL_REPAIR_MAX = 2, repair_count=2 should immediately reject
        out = repair_sql_node(state)
        assert out["repair_count"] == 2
        assert "tối đa" in out["error"]
        assert out["events"][0]["output"]["limit_exceeded"] is True


# ── TestSettings ──────────────────────────────────────────────────────────────


def test_sql_repair_max_default_is_two():
    s = Settings()
    assert s.sql_repair_max == 2
