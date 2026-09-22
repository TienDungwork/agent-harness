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

from __future__ import annotations

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
