"""Unit tests cho hàm validate_and_repair_sql dùng chung (Phase 3c)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.validate_sql import validate_and_repair_sql
from src.db.validator import ValidationResult


class TestSharedValidateAndRepair:
    def test_valid_sql_returns_immediately_zero_repairs(self):
        sql = "SELECT count(*) AS so_luot FROM plate_event"
        res_sql, val, count, events = validate_and_repair_sql(
            sql=sql,
            question="Đếm tổng số xe",
        )
        assert res_sql == sql
        assert val.ok is True
        assert count == 0
        assert len(events) == 1
        assert events[0]["node_id"] == "validate_sql"
        assert events[0]["meta"]["ok"] is True

    def test_invalid_sql_repaired_successfully_on_first_attempt(self):
        # Column mixing: alert_level is from firesmoke_event, not plate_event
        initial_sql = "SELECT alert_level FROM plate_event"
        valid_repaired_sql = "SELECT count(*) FROM plate_event"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value=f"```sql\n{valid_repaired_sql}\n```"):

            res_sql, val, count, events = validate_and_repair_sql(
                sql=initial_sql,
                question="Đếm xe",
                schema_excerpt="CREATE TABLE plate_event (id int, event_time timestamp);",
            )

            assert res_sql == valid_repaired_sql
            assert val.ok is True
            assert count == 1
            # Events: validate (failed) -> repair -> validate (passed)
            node_ids = [ev["node_id"] for ev in events]
            assert node_ids == ["validate_sql", "repair_sql", "validate_sql"]
            assert events[0]["output"]["ok"] is False
            assert events[2]["output"]["ok"] is True

    def test_invalid_sql_repaired_on_second_attempt(self):
        initial_sql = "SELECT alert_level FROM plate_event"
        still_bad_sql = "SELECT zone_name_cached FROM plate_event"  # zone_name_cached is from zone_event
        final_valid_sql = "SELECT count(*) FROM plate_event"

        llm_responses = [
            f"```sql\n{still_bad_sql}\n```",
            f"```sql\n{final_valid_sql}\n```",
        ]

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", side_effect=llm_responses):

            res_sql, val, count, events = validate_and_repair_sql(
                sql=initial_sql,
                question="Đếm xe",
                max_repairs=2,
            )

            assert res_sql == final_valid_sql
            assert val.ok is True
            assert count == 2
            node_ids = [ev["node_id"] for ev in events]
            assert node_ids == ["validate_sql", "repair_sql", "validate_sql", "repair_sql", "validate_sql"]

    def test_stops_when_max_repairs_exceeded(self):
        initial_sql = "DROP TABLE plate_event"
        always_bad_sql = "DROP TABLE plate_event"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value=f"```sql\n{always_bad_sql}\n```"):

            res_sql, val, count, events = validate_and_repair_sql(
                sql=initial_sql,
                question="Xóa bảng",
                max_repairs=2,
            )

            assert val.ok is False
            assert count == 2
            assert "Cấm từ khóa ghi/DDL" in val.reason or "Chỉ cho phép" in val.reason

    def test_custom_max_repairs_override(self):
        initial_sql = "DROP TABLE plate_event"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"):

            res_sql, val, count, events = validate_and_repair_sql(
                sql=initial_sql,
                question="Xóa",
                max_repairs=1,
            )

            assert val.ok is False
            assert count == 1
