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
