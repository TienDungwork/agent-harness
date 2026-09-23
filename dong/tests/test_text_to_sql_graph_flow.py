"""Unit & integration tests cho Graph text-to-SQL flow (Phase 3c).

Flow: query_db -> pre (retrieve_schema) -> generate_sql -> validate_sql <-> repair_sql -> execute_sql -> render_chart / respond.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.graph import Agent_Input, _build_graph, reset_graph, run_agent
from src.llm.schemas import IntentResult, RewrittenQuestion


@pytest.fixture(autouse=True)
def clean_graph():
    reset_graph()
    yield
    reset_graph()


class TestTextToSqlGraphFlow:
    def test_end_to_end_valid_query_flow(self):
        """Happy path: retrieve_schema -> generate_sql -> validate_sql -> execute_sql -> respond."""
        mock_rows = [{"vehicle_type": "truck", "so_luot": 15}]

        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nSELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type\n```"), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_rows), \
             patch("src.llm.client.use_offline_tools", return_value=True):  # respond node in offline template mode
            
            inp = Agent_Input(question="Thống kê lượt xe theo loại xe")
            res = run_agent(inp)

            assert res.detail == "query_data"
            assert "truck" in res.answer or "15" in res.answer
            assert res.query is not None
            assert res.query.row_count == 1

    def test_validation_failure_triggers_repair_loop_and_succeeds(self):
        """Generate creates invalid SQL -> validate_sql fails -> repair_sql repairs -> validate_sql passes -> execute_sql."""
        mock_rows = [{"so_luot": 42}]
        call_count = {"repair": 0}

        def mock_repair(sys, usr, max_tokens=None):
            call_count["repair"] += 1
            return "```sql\nSELECT count(*) AS so_luot FROM plate_event\n```"

        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nSELECT alert_level FROM plate_event\n```"), \
             patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", side_effect=mock_repair), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_rows), \
             patch("src.llm.client.use_offline_tools", return_value=False), \
             patch("src.llm.client.invoke_text", return_value="Có 42 lượt xe."):

            inp = Agent_Input(question="Đếm tổng số xe")
            res = run_agent(inp)

            assert call_count["repair"] == 1
            assert res.detail == "query_data"
            assert "42" in res.answer
            assert res.query.row_count == 1

    def test_repair_max_limit_routes_to_respond_with_error(self):
        """Repair loop stops after SQL_REPAIR_MAX and routes to respond without crashing."""
        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"), \
             patch("src.agent.validate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.validate_sql.invoke_text", return_value="```sql\nDROP TABLE plate_event\n```"), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.llm.client.use_offline_tools", return_value=True):

            inp = Agent_Input(question="Xóa dữ liệu")
            res = run_agent(inp)

            assert res.detail == "query_data"
            assert "Lỗi khi truy vấn" in res.answer or "không hợp lệ" in res.answer or "tối đa" in res.answer

    def test_chart_requested_routes_through_render_chart(self):
        """When chart is requested, execute_sql routes to render_chart before respond."""
        mock_rows = [{"vehicle_type": "car", "so_luot": 20}, {"vehicle_type": "truck", "so_luot": 10}]

        with patch("src.agent.graph.classify_intent_safe", return_value=IntentResult(intent="query_data", reason="mock")), \
             patch("src.agent.generate_sql.use_offline_tools", return_value=False), \
             patch("src.agent.generate_sql.invoke_text", return_value="```sql\nSELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type\n```"), \
             patch("src.agent.execute_sql.use_offline_tools", return_value=False), \
             patch("src.agent.execute_sql.execute_sql", return_value=mock_rows), \
             patch("src.agent.graph.render_chart", return_value="mock_png_base64_data"), \
             patch("src.llm.client.use_offline_tools", return_value=True):

            inp = Agent_Input(question="Vẽ biểu đồ số lượng xe theo loại")
            res = run_agent(inp)

            assert res.detail == "query_data"
            assert res.query.row_count == 2
