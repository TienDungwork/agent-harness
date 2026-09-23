"""Frontend Chart.js integration tests.

Tests verify static file contents:
- index.html includes Chart.js v4 CDN script tag before app.js.
- app.js defines renderChartJs function.
- app.js handles chart_rows from SSE events.
- app.js saves chart as object {png, spec, type, rows}.
"""

from __future__ import annotations

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



