"""Acceptance unit & integration tests cho Phase 3c: Text-to-SQL Core.

Mục tiêu kiểm thử:
1. Chặn toàn bộ các biến thể DDL / DML / multi-statement / table lạ.
2. Kiểm thử cơ chế repair mock (lặp tối đa SQL_REPAIR_MAX = 2 lần).
3. Kiểm thử execute mock (Postgres read-only, xử lý ngoại lệ DB an toàn).
4. Kiểm thử toàn vẹn chuỗi pipeline text-to-SQL trên đồ thị Graph.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.agent.execute_sql import execute_sql_node
from src.agent.generate_sql import extract_sql, generate_sql_node
from src.agent.graph import Agent_Input, _get_graph, reset_graph, run_agent, run_agent_stream
from src.agent.validate_sql import repair_sql_node, validate_and_repair_sql, validate_sql_node
from src.config import settings
from src.db.validator import validate_sql
from src.llm.schemas import IntentResult, RewrittenQuestion


@pytest.fixture(autouse=True)
def reset_graph_state():
    reset_graph()
    yield
    reset_graph()


# ==============================================================================
# 1. Chặn DDL / DML / An toàn SQL
# ==============================================================================


class TestBlockDdlDmlSecurity:
    @pytest.mark.parametrize("bad_sql, expected_reason_keyword", [
        ("DROP TABLE plate_event", "DDL"),
        ("DROP DATABASE its", "DDL"),
        ("TRUNCATE TABLE plate_event", "DDL"),
        ("ALTER TABLE plate_event ADD COLUMN x int", "DDL"),
        ("CREATE TABLE evil (id int)", "DDL"),
        ("DELETE FROM plate_event WHERE 1=1", "DDL"),
        ("INSERT INTO plate_event (camera_name) VALUES ('cam1')", "DDL"),
        ("UPDATE plate_event SET vehicle_type = 'CAR'", "DDL"),
        ("GRANT ALL ON plate_event TO public", "DDL"),
        ("COPY plate_event TO '/tmp/dump'", "DDL"),
        ("DO $$ BEGIN RAISE NOTICE 'hack'; END $$", "SELECT hoặc WITH"),
        ("SELECT 1; DROP TABLE plate_event", "multi-statement"),
        ("SELECT 1; DELETE FROM plate_event", "multi-statement"),
        ("SELECT * FROM plate_event FOR UPDATE", "DDL"),
        ("SELECT pg_sleep(10) FROM plate_event", "DDL"),
        ("SELECT * FROM non_existent_database_table", "không nằm trong danh mục"),
        ("SELECT alert_level FROM plate_event", "không thuộc bảng"),
    ])
    def test_validator_blocks_all_ddl_and_dml(self, bad_sql: str, expected_reason_keyword: str):
        val = validate_sql(bad_sql)
        assert val.ok is False
        reason_lower = val.reason.lower()
        assert (
            expected_reason_keyword.lower() in reason_lower
            or "chỉ cho phép câu lệnh bắt đầu bằng select hoặc with" in reason_lower
            or "cấm từ khóa ghi/ddl" in reason_lower
        )

    @pytest.mark.parametrize("bad_sql", [
        "DROP TABLE plate_event",
        "DELETE FROM plate_event",
        "INSERT INTO plate_event (id) VALUES (1)",
        "TRUNCATE TABLE plate_event",
        "SELECT 1; DROP TABLE plate_event",
    ])
    def test_execute_node_refuses_to_call_db_for_ddl(self, bad_sql: str):
        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db:
            state = {"sql": bad_sql}
            out = execute_sql_node(state)

            mock_db.assert_not_called()
            assert out["rows"] == []
            assert out["columns"] == []
            assert "SQL không hợp lệ" in out["error"]

    def test_end_to_end_graph_halts_on_unrepairable_ddl(self):
        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"), \
             patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql") as mock_db, \
             patch("src.llm.client.use_offline_tools", return_value=True):

            res = run_agent(Agent_Input(question="Xóa toàn bộ bảng plate_event"))

            mock_db.assert_not_called()
            assert res.detail == "query_data"
            assert "Lỗi khi truy vấn" in res.answer or "không hợp lệ" in res.answer or "tối đa" in res.answer


# ==============================================================================
# 2. Repair Mock (≤ SQL_REPAIR_MAX = 2)
# ==============================================================================


class TestSqlRepairMock:
    def test_repair_attempt_1_success(self):
        initial_bad_sql = "SELECT alert_level FROM plate_event"
        fixed_sql = "SELECT count(*) AS so_luot FROM plate_event"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value=f"```sql\n{fixed_sql}\n```"):

            final_sql, val, count, events = validate_and_repair_sql(
                sql=initial_bad_sql,
                question="Đếm số lượng xe",
                schema_excerpt="CREATE TABLE plate_event (...)",
            )

            assert final_sql == fixed_sql
            assert val.ok is True
            assert count == 1

    def test_repair_attempt_2_success(self):
        initial_bad = "SELECT alert_level FROM plate_event"
        attempt_1_bad = "SELECT zone_name_cached FROM plate_event"
        attempt_2_fixed = "SELECT count(*) AS so_luot FROM plate_event"

        responses = [
            f"```sql\n{attempt_1_bad}\n```",
            f"```sql\n{attempt_2_fixed}\n```",
        ]

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", side_effect=responses):

            final_sql, val, count, events = validate_and_repair_sql(
                sql=initial_bad,
                question="Đếm xe",
                max_repairs=2,
            )

            assert final_sql == attempt_2_fixed
            assert val.ok is True
            assert count == 2

    def test_repair_fails_after_max_repairs_exceeded(self):
        initial_bad = "DROP TABLE plate_event"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"):

            final_sql, val, count, events = validate_and_repair_sql(
                sql=initial_bad,
                question="Xóa bảng",
                max_repairs=settings.sql_repair_max,
            )

            assert val.ok is False
            assert count == settings.sql_repair_max
            assert "DDL" in val.reason or "SELECT" in val.reason

    def test_repair_prompt_contains_necessary_error_and_schema_context(self):
        captured: list[tuple[str, str, int | None]] = []

        def mock_invoke(sys, usr, max_tokens=None):
            captured.append((sys, usr, max_tokens))
            return "```sql\nSELECT count(*) FROM plate_event\n```"

        with patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", side_effect=mock_invoke):

            state = {
                "sql": "SELECT alert_level FROM plate_event",
                "question": "Thống kê lượt xe",
                "schema_excerpt": "TABLE plate_event (event_time, vehicle_type)",
                "repair_count": 0,
                "sql_validation": {"ok": False, "reason": "Cột 'alert_level' không thuộc bảng plate_event."},
            }
            out = repair_sql_node(state)

            assert len(captured) == 1
            sys, usr, max_tokens = captured[0]
            assert "Cột 'alert_level' không thuộc bảng plate_event." in usr
            assert "SELECT alert_level FROM plate_event" in usr
            assert "Thống kê lượt xe" in usr
            assert "TABLE plate_event" in usr
            assert max_tokens == settings.sql_generate_max_tokens


# ==============================================================================
# 3. Execute Mock (Postgres Read-Only & Robust Error Handling)
# ==============================================================================


class TestExecuteMock:
    def test_execute_node_returns_columns_and_rows_with_event(self):
        mock_data = [
            {"vehicle_type": "BUS", "so_luot": 10},
            {"vehicle_type": "CAR", "so_luot": 45},
        ]
        sql = "SELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_data) as mock_exec:

            state = {"sql": sql, "params": []}
            out = execute_sql_node(state)

            mock_exec.assert_called_once_with(sql, [])
            assert out["rows"] == mock_data
            assert out["columns"] == ["vehicle_type", "so_luot"]
            assert out["error"] == ""
            assert len(out["events"]) == 1
            assert out["events"][0]["node_id"] == "execute_sql"
            assert out["events"][0]["output"]["row_count"] == 2

    def test_execute_node_catches_db_exception_without_crashing(self):
        sql = "SELECT count(*) FROM plate_event"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", side_effect=RuntimeError("psycopg2.OperationalError: connection refused")):

            state = {"sql": sql}
            out = execute_sql_node(state)

            assert out["rows"] == []
            assert out["columns"] == []
            assert "connection refused" in out["error"]
            assert out["events"][0]["meta"]["ok"] is False

    def test_execute_node_handles_empty_db_result(self):
        sql = "SELECT * FROM plate_event WHERE event_time > '2099-01-01'"

        with patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=[]):

            state = {"sql": sql}
            out = execute_sql_node(state)

            assert out["rows"] == []
            assert out["columns"] == []
            assert out["error"] == ""
            assert out["events"][0]["output"]["row_count"] == 0


# ==============================================================================
# 4. Pipeline Integration & Stream Event Integrity
# ==============================================================================


class TestPipelineStreamIntegration:
    def test_stream_emits_text_to_sql_nodes_in_exact_order(self):
        mock_rows = [{"so_luot": 100}]

        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nSELECT count(*) AS so_luot FROM plate_event\n```"), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_rows), \
             patch("src.llm.client.use_offline_tools", return_value=True):

            inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe?")
            events = list(run_agent_stream(inp, session_id=f"test_{uuid.uuid4().hex}"))

            node_names = [ev.get("node_id") for ev in events if ev.get("status") == "running"]

            # Verify sequence
            assert "classify" in node_names
            assert "retrieve_schema" in node_names
            assert "generate_sql" in node_names
            assert "validate_sql" in node_names
            assert "execute_sql" in node_names
            assert "respond" in node_names

            # Verify plan_query is NOT in stream
            assert "plan_query" not in node_names
