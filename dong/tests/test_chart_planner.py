"""Unit tests for Phase 3c: Chart planner & ChartSpec (dong v5).

Tests:
1. plan_chart offline: bar, pie, line detection from Vietnamese questions.
2. render_chart bar + pie produce non-empty PNG base64.
3. graph stream with chart question hits render_chart node and emits chart_meta.
4. invalid chart_type normalizes to bar.
"""

from __future__ import annotations

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
