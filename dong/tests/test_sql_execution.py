"""Unit tests cho Node execute_sql (Phase 3c)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.execute_sql import execute_sql_node


class TestExecuteSqlNode:
    def test_revalidates_and_executes_valid_sql_mock_pg(self):
        mock_rows = [{"vehicle_type": "car", "so_luot": 12}]
        sql = "SELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_rows) as mock_db:
            state = {
                "sql": sql,
                "params": [],
                "user_id": "u1",
                "session_id": "s1",
            }
            out = execute_sql_node(state)

            mock_db.assert_called_once_with(sql, [])
            assert out["rows"] == mock_rows
            assert out["columns"] == ["vehicle_type", "so_luot"]
            assert out["error"] == ""
            assert len(out["events"]) == 1
            assert out["events"][0]["node_id"] == "execute_sql"
            assert out["events"][0]["output"]["row_count"] == 1
            assert out["events"][0]["meta"]["ok"] is True

    def test_revalidate_rejects_ddl_drop(self):
        sql = "DROP TABLE plate_event"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": sql}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert out["rows"] == []
            assert out["columns"] == []
            assert "SQL không hợp lệ" in out["error"]
            assert out["events"][0]["output"]["revalidate_failed"] is True
            assert out["events"][0]["meta"]["ok"] is False

    def test_revalidate_rejects_dml_delete(self):
        sql = "DELETE FROM plate_event WHERE 1=1"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": sql}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert out["rows"] == []
            assert "SQL không hợp lệ" in out["error"]

    def test_revalidate_rejects_unknown_table(self):
        sql = "SELECT * FROM passwords_table"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": sql}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert out["rows"] == []
            assert "không nằm trong danh mục cho phép" in out["error"]

    def test_revalidate_rejects_empty_sql(self):
        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": "   "}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert out["rows"] == []
            assert "SQL không hợp lệ" in out["error"]

    def test_db_exception_caught_and_reported(self):
        sql = "SELECT count(*) FROM plate_event"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", side_effect=RuntimeError("Database connection timed out")):
            state = {"sql": sql}
            out = execute_sql_node(state)

            assert out["rows"] == []
            assert out["columns"] == []
            assert "Database connection timed out" in out["error"]
            assert out["events"][0]["output"]["error"] == "Database connection timed out"
            assert out["events"][0]["meta"]["ok"] is False

    def test_offline_mode_returns_fallback_rows(self):
        sql = "SELECT count(*) FROM plate_event"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=True), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": sql}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert len(out["rows"]) == 1
            assert out["columns"] == ["count"]
            assert out["error"] == ""
            assert out["events"][0]["output"]["row_count"] == 1
