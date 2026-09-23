"""Phase 2 task 1 — Chart UI audit: wiring slot / canvas / img PNG tồn tại."""

from __future__ import annotations

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


