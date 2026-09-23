"""Phase 3b acceptance tests — Pre-SQL context assertions.

Covers ALL four checklist items from Phase 3b final pytest task:

  a) Excerpt smaller than full catalog:
       retrieve_schema_node / select_relevant_tables + build_schema_excerpt for a
       single-domain vehicle question yields an excerpt smaller than the full
       catalog; related table present; unrelated tables absent.

  b) time_range in context:
       Online-mocked generate_sql_node (use_offline_tools=False + mock invoke_text)
       with RewrittenQuestion(time_range="today") → user prompt contains
       time_range hint ("Khoảng thời gian" / "time_range": today).

  c) chart hint in context:
       Same style mock with chart question ("Vẽ biểu đồ…") → user prompt
       contains chart hint (GROUP BY / vehicle_type or generic GROUP BY).
       One combined test has BOTH time_range + chart hint in the same user
       prompt (order: time → chart → schema → question).

  d) Graph-level offline stream/node smoke:
       retrieve_schema event has selected_tables ≤ 4 and schema_excerpt scoped.

All tests run offline / mocked — no live LLM or DB required.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from src.agent.generate_sql import generate_sql_node
from src.agent.graph import retrieve_schema_node
from src.db.catalog import build_schema_excerpt, select_relevant_tables
from src.llm.schemas import RewrittenQuestion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_CATALOG_TABLES = [
    "plate_event",
    "zone_event",
    "smf_face_events",
    "fire_smoke_event",
    "anomaly_event",
]


def _full_catalog_excerpt() -> str:
    return build_schema_excerpt()


# ---------------------------------------------------------------------------
# a) Excerpt smaller than full catalog
# ---------------------------------------------------------------------------


class TestExcerptSmallerThanFullCatalog:
    """Assert scoped excerpt is strictly smaller than full catalog."""

    def test_single_domain_vehicle_excerpt_smaller_than_full(self):
        """select_relevant_tables + build_schema_excerpt for vehicle question
        yields excerpt smaller than full catalog; plate_event present;
        unrelated tables absent."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Hôm nay có bao nhiêu lượt xe vào cổng?", limit=4)

        assert len(tables) <= 4
        assert "plate_event" in tables

        scoped = build_schema_excerpt(tables)
        assert len(scoped) < len(full), (
            f"Scoped excerpt length {len(scoped)} must be < full catalog {len(full)}"
        )
        assert "Table: plate_event" in scoped
        # Unrelated tables must be absent
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in scoped, f"Unrelated table {tbl!r} found in scoped excerpt"

    def test_retrieve_schema_node_vehicle_scoped_smaller_than_full(self):
        """retrieve_schema_node for a vehicle question yields scoped excerpt
        (uses plate_event only) that is strictly smaller than full catalog."""
        full = _full_catalog_excerpt()
        state = {
            "question": "Có bao nhiêu xe tải qua cổng hôm nay?",
            "rewritten": RewrittenQuestion(text="Có bao nhiêu xe tải qua cổng hôm nay?"),
            "intent": "query_data",
            "user_id": "u-test",
            "session_id": "s-test",
        }
        result = retrieve_schema_node(state)

        assert "schema_excerpt" in result
        excerpt = result["schema_excerpt"]
        selected = result.get("selected_tables", [])

        # Must select ≤ 4 tables
        assert len(selected) <= 4
        # plate_event must be included for a vehicle question
        assert "plate_event" in selected
        # Excerpt strictly smaller than full catalog
        assert len(excerpt) < len(full), (
            f"Scoped excerpt ({len(excerpt)} chars) must be < full catalog ({len(full)} chars)"
        )
        assert "Table: plate_event" in excerpt
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in excerpt

    def test_fire_domain_excerpt_smaller_than_full(self):
        """Fire-domain question yields excerpt smaller than full, fire_smoke_event present."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Phát hiện khói ở khu vực nào hôm nay?", limit=4)
        scoped = build_schema_excerpt(tables)

        assert len(scoped) < len(full)
        assert "Table: fire_smoke_event" in scoped
        assert "Table: plate_event" not in scoped

    def test_face_domain_excerpt_smaller_than_full(self):
        """Face-domain question yields excerpt smaller than full, smf_face_events present."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Hôm nay có bao nhiêu người chấm công khuôn mặt?", limit=4)
        scoped = build_schema_excerpt(tables)

        assert len(scoped) < len(full)
        assert "Table: smf_face_events" in scoped
        assert "Table: plate_event" not in scoped

    def test_full_catalog_excerpt_contains_all_tables(self):
        """Sanity: full catalog excerpt contains all 5 tables."""
        full = _full_catalog_excerpt()
        for tbl in _FULL_CATALOG_TABLES:
            assert f"Table: {tbl}" in full, f"Full catalog must include Table: {tbl}"


# ---------------------------------------------------------------------------
# b) time_range in context
# ---------------------------------------------------------------------------


class TestTimeRangeInContext:
    """Assert time_range hint appears in generate_sql_node user prompt."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_time_range_today_in_user_message(self, mock_invoke, _mock_offline):
        """generate_sql online mock: RewrittenQuestion(time_range='today') →
        user prompt contains 'Khoảng thời gian (time_range): today'."""
        rewritten = RewrittenQuestion(
            text="Hôm nay có bao nhiêu xe vào?",
            filters=["direction=IN"],
            time_range="today",
        )
        state = {
            "question": "Hôm nay có bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event\nColumns: event_time, direction",
        }
        generate_sql_node(state)

        assert mock_invoke.called
        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian (time_range): today" in user_prompt, (
            f"time_range hint missing from user prompt:\n{user_prompt[:500]}"
        )
        assert "today" in user_prompt
        assert "CURRENT_DATE" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_time_range_yesterday_in_user_message(self, mock_invoke, _mock_offline):
        """generate_sql: time_range='yesterday' → user prompt contains yesterday hint."""
        rewritten = RewrittenQuestion(
            text="Hôm qua bao nhiêu xe ra?",
            time_range="yesterday",
        )
        state = {
            "question": "Hôm qua bao nhiêu xe ra?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian (time_range): yesterday" in user_prompt
        assert "CURRENT_DATE - 1" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_no_time_range_when_none(self, mock_invoke, _mock_offline):
        """generate_sql: time_range=None → user prompt does NOT contain time_range hint."""
        rewritten = RewrittenQuestion(text="Bao nhiêu xe vào?", time_range=None)
        state = {
            "question": "Bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian" not in user_prompt
        # Schema and question still present
        assert "Table: plate_event" in user_prompt
        assert "Bao nhiêu xe vào?" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_schema_and_question_always_in_user_message(self, mock_invoke, _mock_offline):
        """Regardless of time_range, schema_excerpt and question text are always present."""
        for tr in ("today", None):
            mock_invoke.reset_mock()
            rewritten = RewrittenQuestion(text="Đếm xe tải vào hôm nay", time_range=tr)
            state = {
                "question": "Đếm xe tải vào hôm nay",
                "rewritten": rewritten,
                "schema_excerpt": "Table: plate_event\nColumns: vehicle_type",
            }
            generate_sql_node(state)

            user_prompt = mock_invoke.call_args[0][1]

            assert "Table: plate_event" in user_prompt, f"Schema missing (time_range={tr})"
            assert "Đếm xe tải vào hôm nay" in user_prompt, f"Question missing (time_range={tr})"


# ---------------------------------------------------------------------------
# c) chart hint in context
# ---------------------------------------------------------------------------


class TestChartHintInContext:
    """Assert chart hint appears in generate_sql_node user prompt for chart questions."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type")
    def test_chart_hint_in_user_message_for_bieu_do(self, mock_invoke, _mock_offline):
        """generate_sql online mock: chart question → user prompt contains GROUP BY hint."""
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ cột lượt xe theo loại hôm nay",
            time_range=None,
        )
        state = {
            "question": "Vẽ biểu đồ cột lượt xe theo loại hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower(), (
            f"GROUP BY hint missing from chart question user prompt:\n{user_prompt[:500]}"
        )
        assert "vehicle_type" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_no_chart_hint_for_plain_count(self, mock_invoke, _mock_offline):
        """generate_sql: plain count question (no 'biểu đồ') → no chart hint in user prompt."""
        rewritten = RewrittenQuestion(text="Hôm nay có bao nhiêu xe vào?", time_range=None)
        state = {
            "question": "Hôm nay có bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        # Chart-specific marker absent
        assert "Yêu cầu biểu đồ" not in user_prompt

    # --- Combined: BOTH time_range + chart hint in the SAME user message ---

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type")
    def test_combined_time_range_and_chart_hint_in_user_message(self, mock_invoke, _mock_offline):
        """COMBINED — Both time_range AND chart hint present in user prompt.
        Order must be: time_range hint → chart hint → schema excerpt → question.
        """
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ số lượng xe theo loại hôm nay",
            filters=["direction=IN"],
            time_range="today",
        )
        state = {
            "question": "Vẽ biểu đồ số lượng xe theo loại hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event\nColumns: vehicle_type, event_time",
        }
        generate_sql_node(state)

        assert mock_invoke.called
        user_prompt = mock_invoke.call_args[0][1]

        # 1. time_range hint present
        assert "Khoảng thời gian (time_range): today" in user_prompt, (
            f"time_range hint missing:\n{user_prompt[:600]}"
        )
        # 2. chart hint present
        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower(), (
            f"chart GROUP BY hint missing:\n{user_prompt[:600]}"
        )
        assert "vehicle_type" in user_prompt
        # 3. schema excerpt present
        assert "Table: plate_event" in user_prompt
        # 4. question present
        assert "Vẽ biểu đồ số lượng xe theo loại hôm nay" in user_prompt

        # Order check: time_range before chart hint before schema before question
        pos_time = user_prompt.index("Khoảng thời gian")
        chart_marker = "Yêu cầu biểu đồ"
        if chart_marker in user_prompt:
            pos_chart = user_prompt.index(chart_marker)
        else:
            pos_chart = user_prompt.upper().index("GROUP BY")
        pos_schema = user_prompt.index("Table: plate_event")
        pos_question = user_prompt.index("Vẽ biểu đồ số lượng xe theo loại hôm nay")

        assert pos_time < pos_chart, "time_range hint must appear before chart hint"
        assert pos_chart < pos_schema, "chart hint must appear before schema excerpt"
        assert pos_schema < pos_question, "schema excerpt must appear before question"

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT entity_type, count(*) FROM fire_smoke_event GROUP BY entity_type")
    def test_generic_chart_hint_non_vehicle_domain(self, mock_invoke, _mock_offline):
        """Non-vehicle chart question → generic GROUP BY hint (no vehicle_type push)."""
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ thống kê sự kiện cháy khói hôm nay",
            time_range="today",
        )
        state = {
            "question": "Vẽ biểu đồ thống kê sự kiện cháy khói hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: fire_smoke_event\nColumns: entity_type, event_time",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        # Generic GROUP BY hint present
        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower()
        # vehicle_type NOT pushed for a fire question
        assert "vehicle_type" not in user_prompt


# ---------------------------------------------------------------------------
# d) Graph-level offline stream/node smoke
# ---------------------------------------------------------------------------


class TestGraphLevelOfflineSmoke:
    """Graph offline stream smoke: retrieve_schema event has ≤4 selected_tables
    and a scoped schema_excerpt."""

    def test_graph_retrieve_schema_event_scoped_vehicle(self):
        """Offline graph stream: retrieve_schema event for vehicle question has
        selected_tables ≤ 4 and scoped schema_excerpt (plate_event present,
        unrelated absent)."""
        from src.agent.graph import Agent_Input, run_agent_stream

        full_len = len(_full_catalog_excerpt())
        inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
        mock_rows = [{"so_luot": 5}]
        with (
            patch("src.llm.client.use_offline_tools", return_value=True),
            patch("src.agent.graph.execute_sql", return_value=mock_rows),
        ):
            events = list(run_agent_stream(inp, session_id=f"smoke-{uuid.uuid4().hex}"))

        schema_events = [
            ev for ev in events
            if ev.get("node_id") == "retrieve_schema" and ev.get("status") == "done"
        ]
        assert len(schema_events) == 1, f"Expected 1 retrieve_schema done event, got {len(schema_events)}"

        ev = schema_events[0]
        output = ev.get("output", {})
        selected = output.get("selected_tables", [])
        excerpt = output.get("schema_excerpt", "")

        # selected_tables ≤ 4
        assert len(selected) <= 4, f"selected_tables exceeds 4: {selected}"
        # plate_event selected for vehicle question
        assert "plate_event" in selected, f"plate_event missing from {selected}"
        # schema_excerpt scoped (shorter than full)
        assert len(excerpt) < full_len, (
            f"Scoped excerpt ({len(excerpt)} chars) must be < full catalog ({full_len} chars)"
        )
        assert "Table: plate_event" in excerpt
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in excerpt, f"Unrelated {tbl} found in scoped excerpt"

    def test_graph_retrieve_schema_event_scoped_fire(self):
        """Offline graph stream: retrieve_schema for fire question → fire_smoke_event selected."""
        from src.agent.graph import Agent_Input, run_agent_stream

        inp = Agent_Input(question="Có cảnh báo cháy nào hôm nay không?")
        mock_rows = [{"so_luot": 0}]
        with (
            patch("src.llm.client.use_offline_tools", return_value=True),
            patch("src.agent.graph.execute_sql", return_value=mock_rows),
        ):
            events = list(run_agent_stream(inp, session_id=f"smoke-{uuid.uuid4().hex}"))

        schema_events = [
            ev for ev in events
            if ev.get("node_id") == "retrieve_schema" and ev.get("status") == "done"
        ]
        assert len(schema_events) == 1

        output = schema_events[0].get("output", {})
        selected = output.get("selected_tables", [])
        excerpt = output.get("schema_excerpt", "")

        assert len(selected) <= 4
        assert "fire_smoke_event" in selected
        assert "Table: fire_smoke_event" in excerpt
        assert "Table: plate_event" not in excerpt

    def test_retrieve_schema_node_selected_tables_max_4_all_domains(self):
        """retrieve_schema_node never returns more than 4 tables for any question."""
        questions = [
            "Hôm nay có bao nhiêu lượt xe vào và cảnh báo cháy?",
            "Thống kê tất cả các sự kiện trong KCN",
            "Xe vào + chấm công + cháy + xâm nhập hôm nay",
            "ALPR và fire smoke và zone và face và anomaly",
        ]
        for q in questions:
            state = {"question": q}
            result = retrieve_schema_node(state)
            selected = result.get("selected_tables", [])
            assert len(selected) <= 4, f"selected_tables > 4 for {q!r}: {selected}"
