"""Offline tests — invoke_structured + Pydantic schemas (không gọi LAN)."""

from __future__ import annotations

import base64
import pytest
from pydantic import ValidationError

from src.chart import plan_chart, render_chart, should_render_chart
from src.llm.schemas import (
    ChartSpec,
    DocsAnswer,
    IntentResult,
    QueryPlan,
    RewrittenQuestion,
    StatAnswer,
)
from src.llm.structured import invoke_structured


def test_rewritten_question_schema_defaults():
    q = RewrittenQuestion(text="đếm xe hôm nay")
    assert q.text == "đếm xe hôm nay"
    assert q.filters == []
    assert q.time_range is None


def test_intent_result_rejects_invalid_intent():
    with pytest.raises(ValidationError):
        IntentResult(intent="weather", reason="x")


def test_query_plan_and_stat_chart_schemas():
    plan = QueryPlan(tables=["vehicle_events"], selects=["count(*)"], filters=["vehicle_type=car"], limit=10)
    assert plan.group_by == []
    assert plan.limit == 10

    docs = DocsAnswer(answer_vi="Mở menu Camera", card_ids=["how_to_add_cam"], steps=["B1", "B2"])
    assert docs.steps == ["B1", "B2"]

    stat = StatAnswer(answer_vi="Có 12 xe", highlights=["12"], chart_requested=True)
    assert stat.chart_requested is True

    chart = ChartSpec(chart_type="bar", x_column="loai", y_column="so_luong", title_vi="Lượt xe")
    assert chart.chart_type == "bar"


def test_invoke_structured_mock_returns_schema(monkeypatch):
    expected = IntentResult(intent="how_to", reason="hỏi cách dùng")

    class _FakeStructured:
        def invoke(self, messages):
            assert messages
            return expected

    class _FakeLLM:
        def with_structured_output(self, schema):
            assert schema is IntentResult
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    result = invoke_structured(
        [{"role": "user", "content": "làm sao thêm camera?"}],
        IntentResult,
    )
    assert result == expected
    assert result.intent == "how_to"


def test_invoke_structured_coerces_dict_to_schema(monkeypatch):
    class _FakeStructured:
        def invoke(self, messages):
            return {
                "text": "đếm xe IN hôm nay",
                "filters": ["direction=IN"],
                "time_range": "today",
                "intent_hint": "query_data",
            }

    class _FakeLLM:
        def with_structured_output(self, schema):
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    result = invoke_structured([{"role": "user", "content": "xe vào hôm nay"}], RewrittenQuestion)
    assert isinstance(result, RewrittenQuestion)
    assert result.filters == ["direction=IN"]
    assert result.intent_hint == "query_data"


def test_invoke_structured_validation_error_is_clear(monkeypatch):
    class _FakeStructured:
        def invoke(self, messages):
            return {"intent": "weather", "reason": "x"}

    class _FakeLLM:
        def with_structured_output(self, schema):
            return _FakeStructured()

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    with pytest.raises(RuntimeError, match="không khớp schema IntentResult"):
        invoke_structured([{"role": "user", "content": "trời mưa?"}], IntentResult)


def test_invoke_structured_llm_failure_is_clear(monkeypatch):
    class _FakeLLM:
        def with_structured_output(self, schema):
            raise ConnectionError("refused")

    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    with pytest.raises(RuntimeError, match="Lỗi LLM structured"):
        invoke_structured([{"role": "user", "content": "hi"}], RewrittenQuestion)


# --- Phase 2.5: Chart tests (render_chart, should_render_chart, plan_chart) ---


def test_render_chart_bar_success():
    """render_chart trả về chuỗi PNG base64 hợp lệ, bắt đầu bằng iVBOR và magic \x89PNG."""
    rows = [
        {"vehicle_type": "CAR", "n": 10},
        {"vehicle_type": "MOTORCYCLE", "n": 20},
        {"vehicle_type": "TRUCK", "n": 3},
    ]
    spec = ChartSpec(chart_type="bar", x_column="vehicle_type", y_column="n", title_vi="Lượt xe theo loại")
    b64 = render_chart(rows, spec)

    assert b64
    assert isinstance(b64, str)
    assert b64.startswith("iVBOR")
    raw_bytes = base64.b64decode(b64)
    assert raw_bytes.startswith(b"\x89PNG")


def test_render_chart_line_and_pie():
    """render_chart hỗ trợ chart_type line và pie."""
    rows = [
        {"vehicle_type": "CAR", "n": 10},
        {"vehicle_type": "MOTORCYCLE", "n": 20},
        {"vehicle_type": "TRUCK", "n": 5},
    ]

    # Line chart
    spec_line = ChartSpec(chart_type="line", x_column="vehicle_type", y_column="n", title_vi="Lượt xe theo thời gian")
    b64_line = render_chart(rows, spec_line)
    assert b64_line.startswith("iVBOR")
    assert base64.b64decode(b64_line).startswith(b"\x89PNG")

    # Pie chart
    spec_pie = ChartSpec(chart_type="pie", x_column="vehicle_type", y_column="n", title_vi="Tỷ lệ cơ cấu phương tiện")
    b64_pie = render_chart(rows, spec_pie)
    assert b64_pie.startswith("iVBOR")
    assert base64.b64decode(b64_pie).startswith(b"\x89PNG")


def test_render_chart_empty_rows_and_invalid_spec():
    """render_chart trả về chuỗi rỗng khi rows rỗng hoặc spec là None."""
    spec = ChartSpec(chart_type="bar", x_column="col_x", y_column="col_y", title_vi="Test")
    assert render_chart([], spec) == ""
    assert render_chart(None, spec) == ""
    assert render_chart([{"col_x": "A", "col_y": 1}], None) == ""


def test_render_chart_fallback_column_selection():
    """render_chart tự động chọn cột nếu spec thiếu cột hoặc cột không khớp."""
    rows = [
        {"loai_xe": "CAR", "so_luong": 15},
        {"loai_xe": "BUS", "so_luong": 2},
    ]
    spec_missing_cols = ChartSpec(chart_type="bar", x_column="", y_column="", title_vi="Biểu đồ")
    b64 = render_chart(rows, spec_missing_cols)
    assert b64.startswith("iVBOR")


def test_should_render_chart_keywords_true_and_false():
    """should_render_chart phát hiện đúng từ khóa vẽ biểu đồ tiếng Việt và tiếng Anh."""
    # True cases
    assert should_render_chart("Vẽ biểu đồ số lượng xe") is True
    assert should_render_chart("vẽ biểu đồ lượt xe hôm nay") is True
    assert should_render_chart("chart lượt xe theo ngày") is True
    assert should_render_chart("plot dữ liệu camera cổng 1") is True
    assert should_render_chart("Vẽ đồ thị số xe") is True
    assert should_render_chart("thống kê theo loại xe") is True
    assert should_render_chart("tỷ lệ xe máy so với ô tô") is True
    assert should_render_chart("cơ cấu phương tiện") is True
    assert should_render_chart("phân bố lưu lượng xe") is True
    assert should_render_chart("vẽ lượng xe ra vào") is True

    # False cases
    assert should_render_chart("Có bao nhiêu camera đang hoạt động?") is False
    assert should_render_chart("Làm sao thêm camera mới vào hệ thống?") is False
    assert should_render_chart("Thời tiết hôm nay thế nào?") is False
    assert should_render_chart("") is False
    assert should_render_chart(None) is False


def test_should_render_chart_with_stat_answer():
    """should_render_chart tôn trọng cờ chart_requested trong StatAnswer."""
    stat_requested = StatAnswer(answer_vi="Có 15 xe ô tô.", chart_requested=True)
    assert should_render_chart("Bao nhiêu xe?", stat_requested) is True

    stat_not_requested = StatAnswer(answer_vi="Có 15 xe ô tô.", chart_requested=False)
    assert should_render_chart("Bao nhiêu xe?", stat_not_requested) is False


def test_plan_chart_offline_heuristics():
    """plan_chart offline trích xuất đúng cột category + numeric và chart_type."""
    rows = [
        {"vehicle_type": "CAR", "so_luong": 12},
        {"vehicle_type": "TRUCK", "so_luong": 4},
    ]

    # Bar chart heuristic
    spec_bar = plan_chart(rows, "Vẽ biểu đồ lượt xe theo loại")
    assert isinstance(spec_bar, ChartSpec)
    assert spec_bar.chart_type == "bar"
    assert spec_bar.x_column == "vehicle_type"
    assert spec_bar.y_column == "so_luong"
    assert spec_bar.title_vi

    # Line chart heuristic
    spec_line = plan_chart(rows, "Lượt xe theo ngày")
    assert spec_line.chart_type == "line"

    # Pie chart heuristic
    spec_pie = plan_chart(rows, "Tỷ lệ cơ cấu phương tiện")
    assert spec_pie.chart_type == "pie"

    # Empty rows
    spec_empty = plan_chart([], "Biểu đồ")
    assert isinstance(spec_empty, ChartSpec)
    assert spec_empty.x_column == ""
    assert spec_empty.y_column == ""


def test_plan_chart_mock_structured_online(monkeypatch):
    """plan_chart gọi invoke_structured khi online và trả về ChartSpec từ LLM."""
    expected = ChartSpec(chart_type="line", x_column="ngay", y_column="luot", title_vi="Xu hướng xe")

    class _FakeStructured:
        def invoke(self, messages):
            assert messages
            return expected

    class _FakeLLM:
        def with_structured_output(self, schema):
            assert schema is ChartSpec
            return _FakeStructured()

    monkeypatch.setattr("src.chart.render.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    rows = [{"ngay": "2026-09-21", "luot": 100}]
    result = plan_chart(rows, "Vẽ xu hướng lưu lượng")
    assert result == expected
    assert result.chart_type == "line"
    assert result.x_column == "ngay"
    assert result.y_column == "luot"


def test_plan_chart_llm_failure_falls_back_to_offline(monkeypatch):
    """plan_chart tự động fallback sang offline heuristic nếu LLM structured gặp lỗi."""
    class _FakeLLM:
        def with_structured_output(self, schema):
            raise RuntimeError("LLM connection timeout")

    monkeypatch.setattr("src.chart.render.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.llm.structured.base_llm", lambda **kwargs: _FakeLLM())

    rows = [{"vehicle_type": "BUS", "n": 8}]
    result = plan_chart(rows, "Vẽ biểu đồ xe buýt")
    assert isinstance(result, ChartSpec)
    assert result.x_column == "vehicle_type"
    assert result.y_column == "n"

