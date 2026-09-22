"""Frontend live graph hover — structured JSON I/O khớp backend SSE."""

from __future__ import annotations

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
