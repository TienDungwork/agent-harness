"""Phase 4 Acceptance Tests — Connect UI to data.

Kiểm tra:
1. SSE event __chart__ mang đủ chart_type, chart_spec, chart_png_base64, chart_rows cho FE.
2. __answer__ detail payload mang đủ chart metadata và rows.
3. app.js: nhận SSE -> vẽ bar / pie trong bubble chat và hỗ trợ cả PNG fallback.
4. Live graph hover: upsertGraphNode và showNodeIo xử lý khớp dữ liệu I/O các node text-to-SQL (generate_sql, validate_sql, execute_sql, render_chart).
5. Session + stream bảo toàn session_id và user_id xuyên suốt pipeline.
6. End-to-end stream: câu hỏi "Vẽ biểu đồ..." sinh đầy đủ chuỗi SSE events hợp lệ.
"""

from __future__ import annotations

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
