"""Acceptance unit & integration tests cho Phase 3d — Post-SQL & chart.

Bao gồm:
1. `try_format_simple_answer`: COUNT 1 dòng → template VI tự nhiên; skip respond LLM hoàn toàn.
2. Chart detect: bar / pie / line chuẩn xác theo từ khóa và cấu trúc dữ liệu.
3. Chart fallback SQL (học duy): tự động truy vấn mở rộng khi SQL gốc < 2 dòng hoặc thiếu nhóm.
4. Render chart đẹp: nhãn tiếng Việt, title, màu/grid, tạo PNG base64 hợp lệ không rỗng.
5. `respond`: chỉ gọi LLM khi dữ liệu phức tạp; giới hạn `max_tokens` cap.
"""

from __future__ import annotations

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
