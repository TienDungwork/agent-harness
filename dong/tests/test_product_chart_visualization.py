"""Product test suite for Chart Visualization: Planner, Pre-SQL hints, Post-SQL Chart.js generation, Empty stats, SSE chart events, Frontend chartjs audit."""
from __future__ import annotations

# ==============================================================================
# --- Sourced from test_chart_planner.py ---
# ==============================================================================

"""Unit tests for Phase 3c: Chart planner & ChartSpec (dong v5).

Tests:
1. plan_chart offline: bar, pie, line detection from Vietnamese questions.
2. render_chart bar + pie produce non-empty PNG base64.
3. graph stream with chart question hits render_chart node and emits chart_meta.
4. invalid chart_type normalizes to bar.
"""


import base64

import pytest

from src.agent.graph import Agent_Input, run_agent_stream
from src.chart import normalize_chart_type, plan_chart, render_chart, should_render_chart
from src.llm.schemas import ChartSpec


SAMPLE_ROWS = [
    {"vehicle_type": "CAR", "so_luot": 45},
    {"vehicle_type": "MOTORCYCLE", "so_luot": 120},
    {"vehicle_type": "TRUCK", "so_luot": 15},
    {"vehicle_type": "BUS", "so_luot": 8},
]


def test_plan_chart_offline_vietnamese_heuristics():
    """plan_chart offline: nhận diện bar, pie, line từ câu hỏi tiếng Việt."""
    # 1. Bar detection
    bar_questions = [
        "Vẽ biểu đồ cột số lượng xe theo loại",
        "Vẽ biểu đồ lượt xe theo loại phương tiện",
        "Thống kê số lượng xe vào cổng",
    ]
    for q in bar_questions:
        spec = plan_chart(SAMPLE_ROWS, q)
        assert isinstance(spec, ChartSpec)
        assert spec.chart_type == "bar", f"Câu hỏi '{q}' phải nhận diện là 'bar', nhận được '{spec.chart_type}'"
        assert spec.x_column == "vehicle_type"
        assert spec.y_column == "so_luot"
        assert spec.title_vi

    # 2. Pie detection
    pie_questions = [
        "Vẽ biểu đồ tròn cơ cấu phương tiện",
        "Tỷ lệ các loại xe ra vào",
        "Cơ cấu xe theo từng loại",
        "Phần trăm lưu lượng xe theo loại",
        "Vẽ biểu đồ pie tỷ lệ phương tiện",
    ]
    for q in pie_questions:
        spec = plan_chart(SAMPLE_ROWS, q)
        assert isinstance(spec, ChartSpec)
        assert spec.chart_type == "pie", f"Câu hỏi '{q}' phải nhận diện là 'pie', nhận được '{spec.chart_type}'"
        assert spec.x_column == "vehicle_type"
        assert spec.y_column == "so_luot"
        assert spec.title_vi

    # 3. Line detection
    line_questions = [
        "Vẽ biểu đồ đường xu hướng xe theo ngày",
        "Lưu lượng xe theo thời gian",
        "Biến động số lượt xe theo tháng",
        "Diễn biến lưu lượng xe qua các ngày",
        "Lượt xe theo giờ trong ngày",
    ]
    for q in line_questions:
        spec = plan_chart(SAMPLE_ROWS, q)
        assert isinstance(spec, ChartSpec)
        assert spec.chart_type == "line", f"Câu hỏi '{q}' phải nhận diện là 'line', nhận được '{spec.chart_type}'"
        assert spec.x_column == "vehicle_type"
        assert spec.y_column == "so_luot"
        assert spec.title_vi


def test_render_chart_bar_and_pie_produce_non_empty_base64_png():
    """render_chart bar + pie tạo chuỗi PNG base64 hợp lệ không rỗng."""
    # Bar chart
    spec_bar = ChartSpec(
        chart_type="bar",
        x_column="vehicle_type",
        y_column="so_luot",
        title_vi="Số lượng xe theo loại",
    )
    b64_bar = render_chart(SAMPLE_ROWS, spec_bar)
    assert b64_bar, "Base64 cho biểu đồ bar không được rỗng"
    assert isinstance(b64_bar, str)
    assert b64_bar.startswith("iVBOR")
    raw_bar = base64.b64decode(b64_bar)
    assert raw_bar.startswith(b"\x89PNG")

    # Pie chart
    spec_pie = ChartSpec(
        chart_type="pie",
        x_column="vehicle_type",
        y_column="so_luot",
        title_vi="Tỷ lệ cơ cấu phương tiện",
    )
    b64_pie = render_chart(SAMPLE_ROWS, spec_pie)
    assert b64_pie, "Base64 cho biểu đồ pie không được rỗng"
    assert isinstance(b64_pie, str)
    assert b64_pie.startswith("iVBOR")
    raw_pie = base64.b64decode(b64_pie)
    assert raw_pie.startswith(b"\x89PNG")

    # Line chart (phụ trợ xác minh tính hoàn thiện)
    spec_line = ChartSpec(
        chart_type="line",
        x_column="vehicle_type",
        y_column="so_luot",
        title_vi="Xu hướng lưu lượng",
    )
    b64_line = render_chart(SAMPLE_ROWS, spec_line)
    assert b64_line, "Base64 cho biểu đồ line không được rỗng"
    assert b64_line.startswith("iVBOR")
    assert base64.b64decode(b64_line).startswith(b"\x89PNG")


def test_graph_stream_with_chart_question_hits_render_chart_and_emits_chart_meta():
    """Graph stream với câu hỏi biểu đồ kích hoạt node render_chart và phát sinh chart_meta."""
    inp = Agent_Input(question="Vẽ biểu đồ lượt xe theo loại phương tiện", user_id="u_chart_test")
    events = list(run_agent_stream(inp, session_id="sess_chart_test", user_id="u_chart_test"))

    node_ids = [ev.get("node_id") for ev in events if ev.get("node_id")]
    assert "render_chart" in node_ids, f"Graph stream phải kích hoạt node 'render_chart', thực tế nhận: {node_ids}"

    # Tìm sự kiện done của render_chart
    chart_done = next(
        (ev for ev in events if ev.get("node_id") == "render_chart" and ev.get("status") == "done"),
        None,
    )
    assert chart_done is not None, "Phải có sự kiện done từ node 'render_chart'"

    # Kiểm tra chart_meta chứa đủ cấu hình JSON
    chart_meta = chart_done.get("chart_meta")
    assert chart_meta is not None, "Sự kiện render_chart phải có 'chart_meta'"
    assert chart_meta.get("chart_type") in ("bar", "pie", "line")
    assert "x_column" in chart_meta
    assert "y_column" in chart_meta
    assert "title_vi" in chart_meta

    # Kiểm tra chart_png_base64
    b64 = chart_done.get("chart_png_base64")
    assert b64 is not None and len(b64) > 0, "render_chart phải trả về PNG base64 không rỗng"
    assert b64.startswith("iVBOR")

    # Kiểm tra meta chứa đầy đủ thông tin spec
    meta = chart_done.get("meta") or {}
    assert meta.get("chart_type") in ("bar", "pie", "line")
    assert meta.get("chart_spec") == chart_meta


def test_invalid_chart_type_normalizes_to_bar():
    """Kiểu biểu đồ không hợp lệ được tự động chuẩn hóa về 'bar'."""
    # 1. normalize_chart_type function
    assert normalize_chart_type("unknown") == "bar"
    assert normalize_chart_type("invalid_type") == "bar"
    assert normalize_chart_type("") == "bar"
    assert normalize_chart_type(None) == "bar"
    assert normalize_chart_type(12345) == "bar"
    assert normalize_chart_type("scatter") == "bar"
    assert normalize_chart_type("donut") == "pie" or normalize_chart_type("donut") == "bar"
    assert normalize_chart_type("  BAR  ") == "bar"
    assert normalize_chart_type("PIE") == "pie"
    assert normalize_chart_type("LINE") == "line"

    # 2. ChartSpec validator
    spec_invalid = ChartSpec(chart_type="unsupported_chart", x_column="cat", y_column="val", title_vi="Tiêu đề")
    assert spec_invalid.chart_type == "bar"

    spec_none = ChartSpec(chart_type=None, x_column="cat", y_column="val", title_vi="Tiêu đề")
    assert spec_none.chart_type == "bar"

    spec_upper = ChartSpec(chart_type="PIE", x_column="cat", y_column="val", title_vi="Tiêu đề")
    assert spec_upper.chart_type == "pie"

    spec_line = ChartSpec(chart_type="LINE", x_column="cat", y_column="val", title_vi="Tiêu đề")
    assert spec_line.chart_type == "line"

    # 3. render_chart with invalid chart_type runs without exception and renders as bar
    rendered = render_chart(SAMPLE_ROWS, spec_invalid)
    assert rendered.startswith("iVBOR")
    assert base64.b64decode(rendered).startswith(b"\x89PNG")

# ==============================================================================
# --- Sourced from test_pre_sql_chart_hint.py ---
# ==============================================================================

"""Tests for Phase 3b: Chart hint pre-SQL (build_chart_sql_hint + injection into text-to-SQL).

All tests run offline (mock LLM/DB) — no network required.
"""


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

# ==============================================================================
# --- Sourced from test_phase3d_post_sql_chart.py ---
# ==============================================================================

"""Acceptance unit & integration tests cho Phase 3d — Post-SQL & chart.

Bao gồm:
1. `try_format_simple_answer`: COUNT 1 dòng → template VI tự nhiên; skip respond LLM hoàn toàn.
2. Chart detect: bar / pie / line chuẩn xác theo từ khóa và cấu trúc dữ liệu.
3. Chart fallback SQL (học duy): tự động truy vấn mở rộng khi SQL gốc < 2 dòng hoặc thiếu nhóm.
4. Render chart đẹp: nhãn tiếng Việt, title, màu/grid, tạo PNG base64 hợp lệ không rỗng.
5. `respond`: chỉ gọi LLM khi dữ liệu phức tạp; giới hạn `max_tokens` cap.
"""


import base64
from unittest.mock import MagicMock, patch

import pytest

from src.agent.chart_fallback import (
    fallback_chart_query,
    should_retry_chart_query,
)
from src.agent.graph import Agent_Input, AgentState, render_chart_node, reset_graph, respond_node, run_agent
from src.agent.simple_answer import _fmt_num, try_format_simple_answer
from src.chart.render import (
    _detect_chart_type,
    _format_label,
    plan_chart,
    render_chart,
    should_render_chart,
)
from src.config import settings
from src.llm.schemas import ChartSpec, IntentResult


@pytest.fixture(autouse=True)
def clean_graph_fixture():
    reset_graph()
    yield
    reset_graph()


# ==============================================================================
# 1. Test try_format_simple_answer (Single Row Aggregate Fast Path)
# ==============================================================================


class TestSimpleAnswerFormatting:
    def test_single_count_vehicles_today(self):
        rows = [{"so_luot": 1250}]
        ans = try_format_simple_answer("Hôm nay có bao nhiêu lượt xe vào cổng?", rows)
        assert ans == "Có 1.250 lượt xe vào hôm nay."

    def test_single_count_cars_yesterday(self):
        rows = [{"count": 42}]
        ans = try_format_simple_answer("Hôm qua có bao nhiêu ô tô vào khu công nghiệp?", rows)
        assert ans == "Có 42 lượt ô tô hôm qua."

    def test_single_count_motorcycles(self):
        rows = [{"n": 300}]
        ans = try_format_simple_answer("Đếm số lượng xe máy", rows)
        assert ans == "Có 300 lượt xe máy."

    def test_single_count_trucks(self):
        rows = [{"so_luot": 88}]
        ans = try_format_simple_answer("Có bao nhiêu xe tải hôm nay?", rows)
        assert ans == "Có 88 lượt xe tải hôm nay."

    def test_single_count_active_cameras(self):
        rows = [{"total": 35}]
        ans = try_format_simple_answer("Hệ thống có bao nhiêu camera đang hoạt động trực tuyến?", rows)
        assert ans == "Có 35 camera đang hoạt động."

    def test_vehicle_events_not_labeled_anomaly(self):
        rows = [{"count": 526}]
        ans = try_format_simple_answer("Nay có bao nhiêu sự kiện phương tiện", rows)
        assert ans == "Có 526 sự kiện phương tiện."
        assert "bất thường" not in ans

    def test_single_count_crowd_anomalies(self):
        rows = [{"count": 0}]
        ans = try_format_simple_answer("Hôm nay có phát hiện đám đông nào không?", rows)
        assert ans == "Có 0 lượt phát hiện đám đông hôm nay."

    def test_single_count_intrusions(self):
        rows = [{"so_su_kien": 3}]
        ans = try_format_simple_answer("Hôm nay có sự kiện leo trèo hoặc xâm nhập hàng rào không?", rows)
        assert ans == "Có 3 phát hiện xâm nhập/leo trèo hôm nay."

    def test_single_count_fire_smoke(self):
        rows = [{"count": 0}]
        ans = try_format_simple_answer("Hôm nay có cảnh báo cháy hoặc khói không?", rows)
        assert ans == "Có 0 cảnh báo cháy hoặc khói hôm nay."

    def test_single_count_fights(self):
        rows = [{"so_vu": 1}]
        ans = try_format_simple_answer("Có vụ ẩu đả nào xảy ra hôm nay không?", rows)
        assert ans == "Có 1 vụ ẩu đả hôm nay."

    def test_single_count_water_level(self):
        rows = [{"count": 2}]
        ans = try_format_simple_answer("Hôm nay có cảnh báo ngập hoặc mực nước vượt ngưỡng không?", rows)
        assert ans == "Có 2 cảnh báo mực nước hôm nay."

    def test_multiple_numeric_columns_single_row(self):
        rows = [{"car": 15, "motorcycle": 45}]
        ans = try_format_simple_answer("Thống kê số lượng ô tô và xe máy hôm nay", rows)
        assert "15 ô tô" in ans
        assert "45 xe máy" in ans
        assert "hôm nay" in ans

    def test_returns_none_for_multi_row_table(self):
        rows = [
            {"vehicle_type": "CAR", "so_luot": 15},
            {"vehicle_type": "MOTORCYCLE", "so_luot": 45},
        ]
        ans = try_format_simple_answer("Thống kê xe theo loại", rows)
        assert ans is None

    def test_returns_none_for_single_row_with_text_columns(self):
        rows = [{"camera_name": "Cổng chính", "so_luot": 15}]
        ans = try_format_simple_answer("Camera cổng chính có bao nhiêu lượt xe?", rows)
        assert ans is None

    def test_respond_node_skips_llm_for_simple_count(self):
        """Khi có simple answer, respond_node không gọi invoke_text và đánh dấu llm_used=False."""
        mock_invoke = MagicMock()
        with patch("src.llm.client.invoke_text", mock_invoke), \
             patch("src.llm.client.use_offline_tools", return_value=False):

            state: AgentState = {
                "question": "Hôm nay có bao nhiêu lượt xe máy?",
                "rows": [{"count": 120}],
                "columns": ["count"],
                "error": "",
            }
            res = respond_node(state)

            assert mock_invoke.call_count == 0
            assert res["result"].answer == "Có 120 lượt xe máy hôm nay."
            assert res["events"][0]["output"]["answer_source"] == "template_simple"
            assert res["events"][0]["meta"]["llm_used"] is False


# ==============================================================================
# 2. Test Chart Detection & Chart Type Classification
# ==============================================================================


class TestChartDetectionAndKind:
    @pytest.mark.parametrize(
        "q,expected",
        [
            ("Vẽ biểu đồ số lượt xe theo loại hôm nay", True),
            ("Hãy cho tôi xem chart thống kê camera", True),
            ("Thống kê theo từng cổng kiểm soát", True),
            ("Cơ cấu tỷ lệ các loại phương tiện", True),
            ("Hôm nay có bao nhiêu xe máy vào?", False),
            ("Hướng dẫn cách mở cấu hình AIOC", False),
        ],
    )
    def test_should_render_chart_detection(self, q, expected):
        assert should_render_chart(q) == expected

    @pytest.mark.parametrize(
        "q,expected_kind",
        [
            ("Vẽ biểu đồ tròn tỷ lệ các loại xe", "pie"),
            ("Cơ cấu phần trăm phương tiện ra vào", "pie"),
            ("Biểu đồ tỉ lệ xe tải so với xe máy", "pie"),
            ("Vẽ biểu đồ đường lượt xe theo ngày trong tháng 9", "line"),
            ("Xu hướng lưu lượng xe theo giờ hôm nay", "line"),
            ("Diễn biến số vụ cảnh báo theo thời gian", "line"),
            ("Vẽ biểu đồ cột thống kê xe theo camera", "bar"),
            ("Biểu đồ số lượng phương tiện theo loại xe", "bar"),
        ],
    )
    def test_detect_chart_type_from_question(self, q, expected_kind):
        assert _detect_chart_type(q) == expected_kind

    def test_detect_line_chart_from_date_labels(self):
        labels = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
        assert _detect_chart_type("Biểu đồ lượt xe", labels=labels) == "line"


# ==============================================================================
# 3. Test Chart Fallback SQL Recovery
# ==============================================================================


class TestChartFallbackSql:
    def test_should_retry_chart_query_when_under_2_rows(self):
        rows = [{"count": 42}]
        sql = "SELECT count(*) FROM plate_event"
        q = "Vẽ biểu đồ thống kê số lượng phương tiện theo loại xe hôm nay"
        assert should_retry_chart_query(question=q, sql=sql, rows=rows) is True

    def test_should_not_retry_when_already_has_multiple_rows(self):
        rows = [
            {"vehicle_type": "CAR", "so_luot": 10},
            {"vehicle_type": "MOTORCYCLE", "so_luot": 30},
        ]
        sql = "SELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type"
        q = "Vẽ biểu đồ các loại xe"
        assert should_retry_chart_query(question=q, sql=sql, rows=rows) is False

    def test_fallback_chart_query_offline_mock(self):
        rows = [{"count": 100}]
        sql = "SELECT count(*) FROM plate_event"
        q = "Vẽ biểu đồ các loại xe hôm nay"

        with patch("src.agent.chart_fallback.use_offline_tools", return_value=True):
            res = fallback_chart_query(question=q, sql=sql, rows=rows)
            assert res is not None
            assert len(res["rows"]) >= 2
            assert res["fallback"] is True
            assert "vehicle_type" in res["columns"]

    def test_render_chart_node_applies_fallback_and_renders(self):
        """Khi ban đầu chỉ có 1 dòng, render_chart_node tự động gọi fallback và vẽ chart thành công."""
        initial_rows = [{"count": 50}]
        sql = "SELECT count(*) FROM plate_event"
        q = "Vẽ biểu đồ phương tiện theo loại hôm nay"

        with patch("src.agent.chart_fallback.use_offline_tools", return_value=True):
            state: AgentState = {
                "question": q,
                "rows": initial_rows,
                "columns": ["count"],
                "sql": sql,
            }
            out = render_chart_node(state)

            assert bool(out["chart_png_base64"]) is True
            assert out["events"][0]["output"]["fallback_applied"] is True
            assert len(out["rows"]) >= 2


# ==============================================================================
# 4. Test Chart Rendering Quality (Matplotlib Base64 PNG)
# ==============================================================================


class TestChartRenderingQuality:
    def test_render_bar_chart_png_valid_base64(self):
        rows = [
            {"vehicle_type": "CAR", "so_luot": 25},
            {"vehicle_type": "MOTORCYCLE", "so_luot": 80},
            {"vehicle_type": "TRUCK", "so_luot": 15},
        ]
        spec = ChartSpec(
            chart_type="bar",
            x_column="vehicle_type",
            y_column="so_luot",
            title_vi="Biểu đồ phân loại phương tiện",
        )
        png_b64 = render_chart(rows, spec)
        assert bool(png_b64) is True
        raw_bytes = base64.b64decode(png_b64)
        assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic header

    def test_render_pie_chart_png_valid_base64(self):
        rows = [
            {"vehicle_type": "CAR", "so_luot": 50},
            {"vehicle_type": "MOTORCYCLE", "so_luot": 50},
        ]
        spec = ChartSpec(
            chart_type="pie",
            x_column="vehicle_type",
            y_column="so_luot",
            title_vi="Cơ cấu phần trăm phương tiện",
        )
        png_b64 = render_chart(rows, spec)
        assert bool(png_b64) is True
        raw_bytes = base64.b64decode(png_b64)
        assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_line_chart_png_valid_base64(self):
        rows = [
            {"ngay": "2026-09-01", "so_luot": 100},
            {"ngay": "2026-09-02", "so_luot": 150},
            {"ngay": "2026-09-03", "so_luot": 120},
        ]
        spec = ChartSpec(
            chart_type="line",
            x_column="ngay",
            y_column="so_luot",
            title_vi="Diễn biến lượt xe theo ngày",
        )
        png_b64 = render_chart(rows, spec)
        assert bool(png_b64) is True
        raw_bytes = base64.b64decode(png_b64)
        assert raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_vietnamese_label_mapping(self):
        assert _format_label("CAR") == "Ô tô"
        assert _format_label("MOTORCYCLE") == "Xe máy"
        assert _format_label("TRUCK") == "Xe tải"
        assert _format_label("BUS") == "Xe buýt"
        assert _format_label("IN") == "Vào"
        assert _format_label("OUT") == "Ra"
        assert _format_label("CROWD_DETECTION") == "Đám đông"
        assert _format_label("INTRUSION_DETECTION") == "Xâm nhập/Leo trèo"
        assert _format_label("WATER_LEVEL_DETECTION") == "Mực nước"


# ==============================================================================
# 5. Test Respond Node Max Tokens & Error Degradation
# ==============================================================================


class TestRespondNodeMaxTokensAndDegradation:
    def test_complex_multi_row_calls_llm_with_max_tokens(self):
        mock_invoke = MagicMock(return_value="Theo dữ liệu, xe máy chiếm đa số với 150 lượt.")

        with patch("src.llm.client.invoke_text", mock_invoke), \
             patch("src.llm.client.use_offline_tools", return_value=False):

            state: AgentState = {
                "question": "Phân tích chi tiết lưu lượng xe theo từng camera",
                "rows": [
                    {"camera_name": "Cổng 1", "so_luot": 150},
                    {"camera_name": "Cổng 2", "so_luot": 80},
                ],
                "columns": ["camera_name", "so_luot"],
                "error": "",
            }
            res = respond_node(state)

            assert mock_invoke.call_count == 1
            _, kwargs = mock_invoke.call_args
            assert kwargs.get("max_tokens") == settings.sql_respond_max_tokens
            assert "xe máy" in res["result"].answer
            assert res["events"][0]["output"]["answer_source"] == "llm_text"

    def test_empty_rows_returns_empty_stat_reply_without_llm(self):
        mock_invoke = MagicMock()
        with patch("src.llm.client.invoke_text", mock_invoke), \
             patch("src.llm.client.use_offline_tools", return_value=False):

            state: AgentState = {
                "question": "Có bao nhiêu xe biển số 99A-99999 hôm nay?",
                "rows": [],
                "columns": [],
                "error": "",
            }
            res = respond_node(state)

            assert mock_invoke.call_count == 0
            assert "không tìm thấy" in res["result"].answer.lower() or "không có" in res["result"].answer.lower()
            assert res["events"][0]["output"]["answer_source"] == "empty"

    def test_error_state_returns_friendly_error_without_llm(self):
        mock_invoke = MagicMock()
        with patch("src.llm.client.invoke_text", mock_invoke), \
             patch("src.llm.client.use_offline_tools", return_value=False):

            state: AgentState = {
                "question": "Đếm xe",
                "rows": [],
                "columns": [],
                "error": "Timeout kết nối cơ sở dữ liệu",
            }
            res = respond_node(state)

            assert mock_invoke.call_count == 0
            assert "Lỗi khi truy vấn" in res["result"].answer
            assert "Timeout" in res["result"].answer
            assert res["events"][0]["output"]["answer_source"] == "error"

# ==============================================================================
# --- Sourced from test_sse_chart.py ---
# ==============================================================================

"""Phase 4 SSE chart event tests.

Tests for:
- __chart__ SSE event emitted when render_chart graph node fires (chart_png_base64 present).
- __answer__ detail includes chart_type / chart_spec when chart was rendered.
- __chart__ event schema has required fields: node_id, status, chart_type, chart_spec, chart_png_base64.
- No __chart__ event when graph yields no chart data.
- chart_rows included in __chart__ event when render_chart input has rows.
- chart_rows included in __answer__ detail when chart present.

Mock pattern follows test_api.py: patch src.agent.graph.run_agent_stream.
"""


import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Output
from src.main import _build_chart_sse_event, app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHART_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
_CHART_SPEC = {"chart_type": "bar", "x_column": "vehicle_type", "y_column": "count", "title_vi": "Xe theo loại"}
_CHART_ROWS = [
    {"vehicle_type": "Xe máy", "count": 120},
    {"vehicle_type": "Ô tô", "count": 45},
]


def _parse_sse_events(text: str) -> list[dict]:
    """Parse raw SSE text into a list of event dicts."""
    events = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.splitlines():
            if line.startswith("data: "):
                data = line[6:].strip()
                if data and data != "[DONE]":
                    try:
                        events.append(json.loads(data))
                    except json.JSONDecodeError:
                        pass
    return events


def _mock_stream_with_chart(*args, **kwargs):
    """Generator that simulates run_agent_stream yielding a render_chart node event + final result."""
    yield {
        "node_id": "render_chart",
        "status": "done",
        "input": {"question": "Vẽ biểu đồ xe hôm nay", "rows": _CHART_ROWS},
        "output": {"rendered": True, "chart_spec": _CHART_SPEC},
        "chart_png_base64": _CHART_PNG_B64,
        "chart_spec": _CHART_SPEC,
        "chart_meta": _CHART_SPEC,
        "meta": {},
    }
    yield {
        "__final_result__": Agent_Output(
            question="Vẽ biểu đồ xe hôm nay",
            answer="Đây là biểu đồ xe hôm nay.",
            detail="query_data",
        )
    }


def _mock_stream_no_chart(*args, **kwargs):
    """Generator that simulates run_agent_stream with no chart data."""
    yield {
        "node_id": "classify",
        "status": "done",
        "input": "test",
        "output": "query_data",
    }
    yield {
        "__final_result__": Agent_Output(
            question="Hôm nay có bao nhiêu xe?",
            answer="Hôm nay có 100 xe.",
            detail="query_data",
        )
    }


# ---------------------------------------------------------------------------
# Test 1: __chart__ event is emitted when render_chart node has chart_png_base64
# ---------------------------------------------------------------------------

def test_stream_emits_chart_event_on_render_chart(monkeypatch):
    """POST /api/agent/stream phải emit __chart__ event khi render_chart node có chart_png_base64."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream", side_effect=_mock_stream_with_chart):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Vẽ biểu đồ xe hôm nay", "session_id": "test-chart", "user_id": "tester"},
        )

    assert res.status_code == 200
    events = _parse_sse_events(res.text)
    chart_events = [ev for ev in events if ev.get("node_id") == "__chart__"]
    assert len(chart_events) == 1, f"Expected 1 __chart__ event, got {len(chart_events)}. Events: {events}"
    chart_ev = chart_events[0]
    assert chart_ev["status"] == "done"
    assert chart_ev["chart_png_base64"] == _CHART_PNG_B64
    assert chart_ev["chart_type"] == "bar"


# ---------------------------------------------------------------------------
# Test 2: __answer__ detail includes chart_type / chart_spec when chart present
# ---------------------------------------------------------------------------

def test_stream_answer_detail_includes_chart_when_present(monkeypatch):
    """__answer__ SSE event detail phải có chart_type và chart_spec khi chart được render."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream", side_effect=_mock_stream_with_chart):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Vẽ biểu đồ xe hôm nay", "session_id": "test-chart2", "user_id": "tester"},
        )

    assert res.status_code == 200
    events = _parse_sse_events(res.text)
    answer_events = [ev for ev in events if ev.get("node_id") == "__answer__"]
    assert len(answer_events) == 1, f"Expected 1 __answer__ event, got {len(answer_events)}"
    detail = answer_events[0].get("detail", {})
    assert "chart_type" in detail, f"detail missing chart_type: {detail}"
    assert "chart_spec" in detail, f"detail missing chart_spec: {detail}"
    assert detail["chart_type"] == "bar"
    assert isinstance(detail["chart_spec"], dict)


# ---------------------------------------------------------------------------
# Test 3: __chart__ event schema has all required fields
# ---------------------------------------------------------------------------

def test_chart_sse_event_schema_fields():
    """_build_chart_sse_event phải trả về dict đủ các field bắt buộc."""
    spec = {"chart_type": "pie", "x_column": "label", "y_column": "value", "title_vi": "Test"}
    png = _CHART_PNG_B64
    event = _build_chart_sse_event(spec, png)

    assert event["node_id"] == "__chart__"
    assert event["status"] == "done"
    assert event["chart_type"] == "pie"
    assert event["chart_spec"] == spec
    assert event["chart_png_base64"] == png

    # Fallback: None spec → empty dict, default chart_type = bar
    ev2 = _build_chart_sse_event(None, "")
    assert ev2["node_id"] == "__chart__"
    assert ev2["status"] == "done"
    assert ev2["chart_type"] == "bar"
    assert ev2["chart_spec"] == {}
    assert ev2["chart_png_base64"] == ""


# ---------------------------------------------------------------------------
# Test 4: No __chart__ event when stream has no chart data
# ---------------------------------------------------------------------------

def test_stream_no_chart_event_when_no_chart(monkeypatch):
    """Không có __chart__ event khi stream không có render_chart node với chart_png_base64."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream", side_effect=_mock_stream_no_chart):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu xe?", "session_id": "test-no-chart", "user_id": "tester"},
        )

    assert res.status_code == 200
    events = _parse_sse_events(res.text)
    chart_events = [ev for ev in events if ev.get("node_id") == "__chart__"]
    assert len(chart_events) == 0, f"Expected no __chart__ events, got {chart_events}"

    # __answer__ detail should NOT have chart_type or chart_spec
    answer_events = [ev for ev in events if ev.get("node_id") == "__answer__"]
    assert len(answer_events) == 1
    detail = answer_events[0].get("detail", {})
    assert "chart_type" not in detail
    assert "chart_spec" not in detail


# ---------------------------------------------------------------------------
# Test 5: __chart__ event contains chart_rows when render_chart input has rows
# ---------------------------------------------------------------------------

def test_stream_chart_event_includes_chart_rows(monkeypatch):
    """__chart__ SSE event phải có chart_rows khi render_chart event input có rows."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream", side_effect=_mock_stream_with_chart):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Vẽ biểu đồ xe hôm nay", "session_id": "test-chart-rows", "user_id": "tester"},
        )

    assert res.status_code == 200
    events = _parse_sse_events(res.text)
    chart_events = [ev for ev in events if ev.get("node_id") == "__chart__"]
    assert len(chart_events) == 1, f"Expected 1 __chart__ event, got {len(chart_events)}"
    chart_ev = chart_events[0]
    assert "chart_rows" in chart_ev, f"__chart__ event missing chart_rows: {chart_ev}"
    assert isinstance(chart_ev["chart_rows"], list)
    assert len(chart_ev["chart_rows"]) == 2
    assert chart_ev["chart_rows"][0]["vehicle_type"] == "Xe máy"


# ---------------------------------------------------------------------------
# Test 6: __answer__ detail contains chart_rows when chart present
# ---------------------------------------------------------------------------

def test_stream_answer_detail_includes_chart_rows(monkeypatch):
    """__answer__ SSE event detail phải có chart_rows khi chart được render với rows."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)
    from src.main import _cache
    _cache.clear()

    with patch("src.agent.graph.run_agent_stream", side_effect=_mock_stream_with_chart):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Vẽ biểu đồ xe hôm nay", "session_id": "test-answer-rows", "user_id": "tester"},
        )

    assert res.status_code == 200
    events = _parse_sse_events(res.text)
    answer_events = [ev for ev in events if ev.get("node_id") == "__answer__"]
    assert len(answer_events) == 1, f"Expected 1 __answer__ event, got {len(answer_events)}"
    detail = answer_events[0].get("detail", {})
    assert "chart_rows" in detail, f"__answer__ detail missing chart_rows: {detail}"
    assert isinstance(detail["chart_rows"], list)
    assert len(detail["chart_rows"]) == 2


# ---------------------------------------------------------------------------
# Test 7: _build_chart_sse_event includes chart_rows when provided
# ---------------------------------------------------------------------------

def test_build_chart_sse_event_with_rows():
    """_build_chart_sse_event phải bao gồm chart_rows khi được cung cấp."""
    spec = {"chart_type": "bar", "x_column": "label", "y_column": "val", "title_vi": "Test"}
    rows = [{"label": "A", "val": 10}, {"label": "B", "val": 20}]

    event = _build_chart_sse_event(spec, _CHART_PNG_B64, chart_rows=rows)
    assert "chart_rows" in event
    assert event["chart_rows"] == rows

    # Without rows — field should be absent
    event_no_rows = _build_chart_sse_event(spec, _CHART_PNG_B64)
    assert "chart_rows" not in event_no_rows

    # With empty list — field should be present (empty list is a valid rows value)
    event_empty_rows = _build_chart_sse_event(spec, _CHART_PNG_B64, chart_rows=[])
    assert "chart_rows" in event_empty_rows
    assert event_empty_rows["chart_rows"] == []

# ==============================================================================
# --- Sourced from test_frontend_chartjs.py ---
# ==============================================================================

"""Frontend Chart.js integration tests.

Tests verify static file contents:
- index.html includes Chart.js v4 CDN script tag before app.js.
- app.js defines renderChartJs function.
- app.js handles chart_rows from SSE events.
- app.js saves chart as object {png, spec, type, rows}.
"""


from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
APP_JS = FRONTEND_DIR / "app.js"
STYLE_CSS = FRONTEND_DIR / "style.css"

CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"


# ---------------------------------------------------------------------------
# Test 1: index.html includes Chart.js CDN before app.js
# ---------------------------------------------------------------------------

def test_index_html_includes_chartjs_cdn():
    """index.html phải có thẻ <script> Chart.js CDN trước app.js."""
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    content = INDEX_HTML.read_text(encoding="utf-8")

    assert CHARTJS_CDN in content, (
        f"index.html thiếu Chart.js CDN script: {CHARTJS_CDN}"
    )

    # CDN must appear BEFORE app.js
    cdn_pos = content.index(CHARTJS_CDN)
    appjs_pos = content.index("app.js")
    assert cdn_pos < appjs_pos, (
        f"Chart.js CDN (pos {cdn_pos}) phải đứng trước app.js (pos {appjs_pos}) trong index.html"
    )


# ---------------------------------------------------------------------------
# Test 2: app.js defines renderChartJs function
# ---------------------------------------------------------------------------

def test_app_js_has_renderChartJs():
    """app.js phải định nghĩa hàm renderChartJs."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    assert "function renderChartJs" in content, (
        "app.js thiếu định nghĩa hàm renderChartJs"
    )


# ---------------------------------------------------------------------------
# Test 3: app.js handles chart_rows from SSE __chart__ event
# ---------------------------------------------------------------------------

def test_app_js_handles_chart_rows_from_sse():
    """app.js phải đọc chart_rows từ SSE __chart__ event và lưu vào state."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    # State must declare lastChartRows
    assert "lastChartRows" in content, (
        "app.js thiếu lastChartRows trong state"
    )

    # SSE handler must read event.chart_rows
    assert "event.chart_rows" in content, (
        "app.js thiếu xử lý event.chart_rows trong SSE loop"
    )

    # Must pass rows to renderChartJs
    assert "renderChartJs" in content, (
        "app.js không gọi renderChartJs"
    )


# ---------------------------------------------------------------------------
# Test 4: app.js saves chart as object with png/spec/type/rows fields
# ---------------------------------------------------------------------------

def test_app_js_saves_chart_as_object():
    """app.js phải lưu chart trong session message dưới dạng object {png, spec, type, rows}."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    # chartPayload object must be constructed with spec/type/rows/png keys
    assert "chartPayload" in content, (
        "app.js thiếu biến chartPayload khi lưu chart vào message"
    )
    # All required fields of the chart object
    for key in ("png:", "spec:", "type:", "rows:"):
        assert key in content, (
            f"app.js chart object thiếu field '{key}'"
        )


# ---------------------------------------------------------------------------
# Test 5: app.js appendMessage supports object chartPayload (not just string)
# ---------------------------------------------------------------------------

def test_app_js_appendMessage_supports_chart_object():
    """appendMessage trong app.js phải xử lý chartPayload dạng object {png, spec, type, rows}."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    # Must check typeof chartPayload === 'object'
    assert "typeof chartPayload === 'object'" in content, (
        "app.js appendMessage thiếu kiểm tra typeof chartPayload === 'object'"
    )

    # Must handle string fallback (legacy PNG base64)
    assert "typeof chartPayload === 'string'" in content, (
        "app.js appendMessage thiếu xử lý chartPayload dạng string (legacy PNG)"
    )


# ---------------------------------------------------------------------------
# Test 6: app.js defines CHART_VI_LABELS and formatChartLabel
# ---------------------------------------------------------------------------

def test_app_js_has_chart_vi_labels_and_format_label():
    """app.js phải có từ điển dịch nhãn tiếng Việt và hàm formatChartLabel."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    assert "CHART_VI_LABELS" in content, (
        "app.js thiếu khai báo từ điển CHART_VI_LABELS"
    )
    assert "function formatChartLabel" in content, (
        "app.js thiếu định nghĩa hàm formatChartLabel"
    )
    for label_key in ("'CAR'", "'MOTORCYCLE'", "'MOTORBIKE'", "'TRUCK'", "'BUS'", "'IN'", "'OUT'"):
        assert label_key in content, (
            f"CHART_VI_LABELS thiếu nhãn {label_key}"
        )


# ---------------------------------------------------------------------------
# Test 7: app.js renderChartJs supports title_vi and title plugin path
# ---------------------------------------------------------------------------

def test_app_js_renderChartJs_title_vi_and_plugin():
    """renderChartJs phải đọc title_vi, có fallback title, và cấu hình plugin title."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    assert "chartSpec.title_vi" in content, (
        "renderChartJs thiếu đọc chartSpec.title_vi"
    )
    assert "title:" in content or "title :" in content, (
        "renderChartJs thiếu cấu hình plugins.title trong Chart.js options"
    )
    assert "display: Boolean(title)" in content or "display: true" in content, (
        "renderChartJs thiếu bật hiển thị title plugin"
    )


# ---------------------------------------------------------------------------
# Test 8: chart-canvas-wrapper class present in JS and CSS
# ---------------------------------------------------------------------------

def test_chart_canvas_wrapper_in_js_and_css():
    """chart-canvas-wrapper phải có mặt trong cả app.js và style.css để chống méo / blank."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    assert STYLE_CSS.exists(), f"style.css not found at {STYLE_CSS}"

    js_content = APP_JS.read_text(encoding="utf-8")
    css_content = STYLE_CSS.read_text(encoding="utf-8")

    assert "chart-canvas-wrapper" in js_content, (
        "app.js renderChartJs thiếu tạo wrapper class 'chart-canvas-wrapper'"
    )
    assert ".chart-canvas-wrapper" in css_content, (
        "style.css thiếu CSS rule .chart-canvas-wrapper"
    )
    assert "min-height" in css_content, (
        "style.css .chart-canvas-wrapper thiếu min-height"
    )


# ---------------------------------------------------------------------------
# Test 9: renderChartJs configures bar scales with beginAtZero
# ---------------------------------------------------------------------------

def test_app_js_renderChartJs_bar_scales_beginAtZero():
    """renderChartJs phải cấu hình scale trục Y với beginAtZero: true cho bar chart."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    assert "beginAtZero: true" in content, (
        "renderChartJs thiếu cấu hình beginAtZero: true cho trục Y bar chart"
    )
    assert "scales" in content, (
        "renderChartJs thiếu cấu hình options.scales cho bar chart"
    )


# ---------------------------------------------------------------------------
# Test 10: renderChartJs configures pie legend with VI labels and percentage
# ---------------------------------------------------------------------------

def test_app_js_renderChartJs_pie_legend_and_percentage():
    """renderChartJs phải hiển thị legend cho pie với nhãn VI (formatChartLabel) và tỷ lệ % rõ ràng."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    content = APP_JS.read_text(encoding="utf-8")

    # Legend display condition for pie
    assert "display: type === 'pie'" in content, (
        "renderChartJs thiếu hiển thị legend cho pie chart (display: type === 'pie')"
    )

    # Legend position bottom
    assert "position: 'bottom'" in content, (
        "renderChartJs thiếu vị trí position: 'bottom' cho legend pie"
    )

    # Legend generateLabels callback with percentage
    assert "generateLabels:" in content, (
        "renderChartJs thiếu generateLabels callback trong legend để định dạng nhãn và %"
    )
    assert "${pct}%" in content or "%" in content, (
        "renderChartJs thiếu định dạng tỷ lệ % trong legend generateLabels"
    )

    # Tooltip callback includes percentage for pie
    assert "type === 'pie'" in content, (
        "renderChartJs tooltip thiếu nhánh xử lý riêng cho type === 'pie'"
    )
    assert "(${pct}%)" in content or "%)" in content, (
        "renderChartJs tooltip thiếu hiển thị tỷ lệ % cho pie chart"
    )

    # formatChartLabel is used for chart labels
    assert "formatChartLabel" in content, (
        "renderChartJs thiếu sử dụng hàm formatChartLabel cho nhãn"
    )
    assert "rows.map(r => formatChartLabel(" in content or "formatChartLabel(r[xCol])" in content, (
        "renderChartJs không ánh xạ rows với formatChartLabel"
    )

    # Pie slice border separator
    assert "dataset.borderColor = '#ffffff'" in content, (
        "renderChartJs thiếu viền trắng phân cách lát cắt pie chart"
    )


# ---------------------------------------------------------------------------
# Test 11: app.js gates chart-slot on chartPayload and provides empty state
# ---------------------------------------------------------------------------

def test_app_js_conditional_chart_slot_and_empty_state():
    """app.js chỉ gắn .chart-slot khi có chartPayload; câu không chart không có chart-slot; rỗng hiện empty state."""
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    assert STYLE_CSS.exists(), f"style.css not found at {STYLE_CSS}"

    js = APP_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    # Gate: assistant messages do NOT unconditionally create chart-slot
    assert "role === 'assistant' && chartPayload" in js, (
        "app.js appendMessage phải kiểm tra chartPayload trước khi tạo .chart-slot cho assistant"
    )

    # Empty state: when payload exists but no renderable data (empty rows / missing spec)
    assert "chart-empty-state" in js or "chart-slot-empty" in js, (
        "app.js thiếu class cho empty state của chart (chart-slot-empty hoặc chart-empty-state)"
    )
    assert "Chưa có dữ liệu để hiển thị biểu đồ" in js, (
        "app.js thiếu thông báo tiếng Việt ngắn gọn khi payload không có dữ liệu vẽ chart"
    )

    # CSS rules for modest empty state (compact, not blocking text)
    assert ".chart-slot.chart-slot-empty" in css, (
        "style.css thiếu rule định kiểu .chart-slot.chart-slot-empty"
    )
    assert "min-height: auto" in css or "min-height: unset" in css, (
        "style.css .chart-slot.chart-slot-empty cần min-height: auto để không choán không gian"
    )




# ==============================================================================
# --- Sourced from test_frontend_graph_hover.py ---
# ==============================================================================

"""Frontend live graph hover — structured JSON I/O khớp backend SSE."""


from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "frontend" / "app.js"


def _read_app_js() -> str:
    assert APP_JS.exists(), f"app.js not found at {APP_JS}"
    return APP_JS.read_text(encoding="utf-8")


def test_formatIoValue_parses_json_string():
    js = _read_app_js()
    block = js.split("function formatIoValue")[1].split("function truncateIoText")[0]
    assert "JSON.parse(trimmed)" in block
    assert "JSON.stringify(val, null, 2)" in block


def test_upsertGraphNode_merges_io_on_running():
    js = _read_app_js()
    block = js.split("function upsertGraphNode")[1].split("// ==")[0]
    assert "const prev = state.graphNodes[nodeId]" in block
    assert "status === 'done'" in block
    assert "prev.input" in block
    assert "prev.output" in block


def test_showNodeIo_pretty_json_sections():
    js = _read_app_js()
    block = js.split("function showNodeIo")[1].split("function upsertGraphNode")[0]
    assert "'input:\\n'" in block or "'input:\\n' +" in block
    assert "'output:\\n'" in block or "'\\n\\noutput:\\n'" in block
    assert "formatIoValue(n.input)" in block
    assert "formatIoValue(n.output)" in block
    assert "formatIoValue(n.meta)" in block


def test_sse_passes_structured_io_to_upsertGraphNode():
    js = _read_app_js()
    assert "upsertGraphNode(" in js
    assert "event.input" in js
    assert "event.output" in js
    assert "event.meta" in js


def test_graph_hover_tracks_hovered_node_and_refreshes_on_done():
    js = _read_app_js()
    assert "hoveredGraphNodeId" in js
    assert "mouseenter" in js
    assert "hoveredGraphNodeId === nodeId" in js


def test_io_max_chars_limit():
    js = _read_app_js()
    assert "IO_MAX_CHARS = 80000" in js
    assert "truncateIoText" in js

# ==============================================================================
# --- Sourced from test_phase2_chart_ui_audit.py ---
# ==============================================================================

"""Phase 2 task 1 — Chart UI audit: wiring slot / canvas / img PNG tồn tại."""


from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
APP_JS = FRONTEND / "app.js"
STYLE_CSS = FRONTEND / "style.css"
INDEX_HTML = FRONTEND / "index.html"
AUDIT_MD = Path(__file__).resolve().parent.parent / "specs" / "v7-chart-ui-audit.md"
CHECKLIST_MD = Path(__file__).resolve().parent.parent / "specs" / "smoke-manual-checklist.md"


def test_chart_ui_audit_doc_exists():
    assert AUDIT_MD.exists(), "specs/v7-chart-ui-audit.md phải tồn tại sau Phase 2 audit"
    text = AUDIT_MD.read_text(encoding="utf-8")
    assert "chart-slot" in text
    assert "canvas" in text.lower()
    assert "png" in text.lower()
    assert "placeholder" in text.lower()


def test_app_js_chart_slot_canvas_png_placeholder():
    js = APP_JS.read_text(encoding="utf-8")
    assert "chart-slot" in js
    assert "function renderChartJs" in js
    assert "createElement('canvas')" in js or 'createElement("canvas")' in js
    assert "data:image/png;base64" in js
    assert "chart-placeholder" in js
    assert "node_id === '__chart__'" in js or 'node_id === "__chart__"' in js


def test_style_css_chart_slot_rules():
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert ".chart-slot" in css
    assert ".chart-placeholder" in css
    assert "canvas" in css


def test_index_html_chartjs_cdn():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "chart.js" in html.lower()
    assert "app.js" in html


def test_app_js_chart_placeholder_not_always_on():
    """Assistant message không tự động tạo chart-slot/placeholder khi không có chartPayload."""
    js = APP_JS.read_text(encoding="utf-8")
    assert "role === 'assistant' && chartPayload" in js, (
        "app.js phải kiểm tra chartPayload để không tạo chart-slot cho tin nhắn thông thường"
    )
    assert "chart-slot-empty" in js
    assert "Chưa có dữ liệu để hiển thị biểu đồ" in js


def test_smoke_manual_checklist_chart_prompts_and_phase2_criteria():
    """specs/smoke-manual-checklist.md có đúng 1 câu bar, 1 câu pie và pass criteria Phase 2."""
    assert CHECKLIST_MD.exists(), "specs/smoke-manual-checklist.md phải tồn tại"
    text = CHECKLIST_MD.read_text(encoding="utf-8")
    assert "Vẽ biểu đồ cột lượt xe theo loại hôm nay" in text
    assert "Vẽ biểu đồ tròn tỷ lệ loại xe" in text
    assert "chart-canvas-wrapper" in text
    assert "beginAtZero" in text
    assert "borderColor" in text
    assert "placeholder" in text.lower()



# ==============================================================================
# --- Sourced from test_phase4_connect_ui_data.py ---
# ==============================================================================

"""Phase 4 Acceptance Tests — Connect UI to data.

Kiểm tra:
1. SSE event __chart__ mang đủ chart_type, chart_spec, chart_png_base64, chart_rows cho FE.
2. __answer__ detail payload mang đủ chart metadata và rows.
3. app.js: nhận SSE -> vẽ bar / pie trong bubble chat và hỗ trợ cả PNG fallback.
4. Live graph hover: upsertGraphNode và showNodeIo xử lý khớp dữ liệu I/O các node text-to-SQL (generate_sql, validate_sql, execute_sql, render_chart).
5. Session + stream bảo toàn session_id và user_id xuyên suốt pipeline.
6. End-to-end stream: câu hỏi "Vẽ biểu đồ..." sinh đầy đủ chuỗi SSE events hợp lệ.
"""


import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import _build_chart_sse_event, app

client = TestClient(app)


def test_build_chart_sse_event_structure():
    """SSE event __chart__ mang đủ chart_type, chart_spec, chart_png_base64, chart_rows."""
    spec = {
        "chart_type": "pie",
        "x_column": "vehicle_type",
        "y_column": "count",
        "title_vi": "Cơ cấu loại xe hôm nay",
    }
    rows = [{"vehicle_type": "CAR", "count": 25}, {"vehicle_type": "MOTORCYCLE", "count": 100}]
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    ev = _build_chart_sse_event(chart_spec=spec, chart_png_base64=png_b64, chart_rows=rows)
    assert ev["node_id"] == "__chart__"
    assert ev["status"] == "done"
    assert ev["chart_type"] == "pie"
    assert ev["chart_spec"]["title_vi"] == "Cơ cấu loại xe hôm nay"
    assert ev["chart_png_base64"] == png_b64
    assert len(ev["chart_rows"]) == 2


def test_stream_chart_question_emits_chart_and_answer_events():
    """End-to-end SSE stream cho câu hỏi biểu đồ phát sinh __chart__ và __answer__ mang thông tin chart."""
    req_body = {
        "question": "Vẽ biểu đồ số lượng xe theo loại hôm nay",
        "session_id": "test-sess-phase4",
        "user_id": "test-user-phase4",
    }
    mock_rows = [
        {"vehicle_type": "CAR", "so_luot": 50},
        {"vehicle_type": "TRUCK", "so_luot": 20},
        {"vehicle_type": "BUS", "so_luot": 5},
    ]

    with (
        patch("src.llm.client.use_offline_tools", return_value=True),
        patch("src.agent.graph.execute_sql", return_value=mock_rows),
    ):
        res = client.post("/api/agent/stream", json=req_body)

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    node_ids = [e.get("node_id") for e in events]
    assert "recall" in node_ids
    assert "rewrite" in node_ids
    assert "classify" in node_ids
    assert "retrieve_schema" in node_ids
    assert "generate_sql" in node_ids
    assert "validate_sql" in node_ids
    assert "execute_sql" in node_ids
    assert "render_chart" in node_ids
    assert "__chart__" in node_ids
    assert "respond" in node_ids
    assert "__answer__" in node_ids

    # Check __chart__ event
    chart_ev = next(e for e in events if e.get("node_id") == "__chart__")
    assert chart_ev["chart_type"] in ("bar", "pie", "line")
    assert chart_ev["chart_png_base64"] != ""
    assert isinstance(chart_ev.get("chart_spec"), dict)

    # Check __answer__ event
    answer_ev = next(e for e in events if e.get("node_id") == "__answer__")
    assert answer_ev["status"] == "done"
    detail = answer_ev.get("detail", {})
    assert "chart_type" in detail or "chart_spec" in detail


def test_frontend_files_and_chartjs_wiring():
    """Kiểm tra frontend/app.js và index.html có đầy đủ Chart.js, renderChartJs và live graph hover."""
    root = Path(__file__).resolve().parent.parent
    index_html = (root / "frontend" / "index.html").read_text("utf-8")
    app_js = (root / "frontend" / "app.js").read_text("utf-8")
    style_css = (root / "frontend" / "style.css").read_text("utf-8")

    # Chart.js library
    assert "chart.js" in index_html.lower() or "chart.min.js" in index_html.lower()

    # Chart rendering functions
    assert "renderChartJs" in app_js
    assert "chart-canvas-wrapper" in app_js
    assert "chart-canvas-wrapper" in style_css
    assert "chart-slot" in app_js

    # Live graph hover & I/O panel
    assert "upsertGraphNode" in app_js
    assert "showNodeIo" in app_js
    assert "graph-node" in app_js
    assert "graphIoBody" in app_js or "graph-io-body" in app_js or "graph-io-body" in index_html


def test_stream_preserves_session_and_user_ids():
    """Kiểm tra session_id và user_id được duy trì trong suốt luồng stream."""
    session_id = "sess-preserve-123"
    user_id = "user-preserve-456"

    with patch("src.llm.client.use_offline_tools", return_value=True):
        res = client.post(
            "/api/agent/stream",
            json={
                "question": "Hôm nay có bao nhiêu lượt xe vào?",
                "session_id": session_id,
                "user_id": user_id,
            },
        )

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    # All node events with meta must have session_id & user_id
    for ev in events:
        if ev.get("node_id") not in ("__chart__", "__answer__", "cache", "guardrail", "error"):
            meta = ev.get("meta")
            if isinstance(meta, dict):
                assert meta.get("session_id") == session_id
                assert meta.get("user_id") == user_id

# ==============================================================================
# --- Sourced from test_phase5_empty_stat.py ---
# ==============================================================================

"""Phase 5 — Empty số liệu trả đúng, có '0' khi rule yêu cầu."""


from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import respond_node
from src.llm.schemas import QueryResult
from src.guardrails import EMPTY_TOOL_REPLY, check_output, empty_stat_reply
from src.main import app

client = TestClient(app)


def test_empty_stat_reply_contains_zero():
    msg = empty_stat_reply()
    assert "0" in msg
    assert EMPTY_TOOL_REPLY == msg


def test_respond_node_empty_rows_includes_zero():
    out = respond_node({
        "question": "Có bao nhiêu lượt đám đông?",
        "rows": [],
        "columns": [],
        "user_id": "u1",
        "session_id": "s1",
    })
    assert "0" in out["result"].answer
    assert out["events"][0]["output"]["answer_source"] == "empty"


def test_check_output_tool_empty_fabricated_uses_zero_reply():
    result = check_output(
        "Có 5 lượt xe vào hôm nay.",
        ["Hôm nay có bao nhiêu lượt xe vào?", "total=0"],
        tool_empty=True,
    )
    assert "0" in result.answer
    assert "5" not in result.answer
    assert "fabricated_numbers_on_empty_tool" in result.issues


def test_check_output_tool_empty_honest_normalized_to_zero():
    result = check_output(
        "Không có dữ liệu lượt xe vào hôm nay.",
        ["Hôm nay có bao nhiêu lượt xe vào?"],
        tool_empty=True,
    )
    assert "0" in result.answer
    assert "empty_stat_missing_zero" in result.issues


def test_api_chat_empty_query_answer_has_zero():
    from src.agent.graph import Agent_Output

    empty_out = Agent_Output(
        question="Hôm nay có phát hiện leo trèo không?",
        answer=empty_stat_reply(),
        query=QueryResult(tool="sql_builder", columns=[], rows=[], row_count=0),
        detail="query_data",
    )

    with patch("src.main.run_agent", return_value=empty_out):
        res = client.post(
            "/api/chat",
            json={
                "question": "Hôm nay có phát hiện leo trèo không?",
                "session_id": "sess-empty",
                "user_id": "user-empty",
            },
        )

    assert res.status_code == 200
    assert "0" in res.json()["answer"]

