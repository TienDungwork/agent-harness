# Task: Phase 4 — SSE: token/answer + event chart (chart_type + spec hoặc image)

Implement ONLY this unchecked line in `specs/implementation-plan.md`:
`- [ ] SSE: token/answer + event chart (chart_type + spec hoặc image).`

Workdir: `agent-harness/dong`

## Context

Partial wiring exists:
- `render_chart_node` in `src/agent/graph.py` emits graph events with `chart_png_base64`, `chart_meta`, `chart_spec` on `node_id=render_chart`.
- `frontend/app.js` sets `state.lastChart` when any SSE event has `chart_png_base64`, then attaches PNG to `__answer__` message.
- `__answer__` SSE event in `src/main.py` only has `output` (text) + `detail` (tool/row_count) — **no chart_type/spec/image in answer event**.
- No dedicated `__chart__` SSE event contract.
- Token streaming: answer arrives as one block in `__answer__` — add lightweight `__token__` chunks only if easy (optional); primary deliverable is **structured chart SSE event**.

## Goal

Standardize SSE payload so UI receives:
1. **Answer event** — `node_id: "__answer__"`, `output` text, `detail` may include chart summary
2. **Chart event** — dedicated event with `chart_type`, `chart_spec` (JSON), and `chart_png_base64` (image fallback)

## Requirements

### 1. Backend SSE contract — `src/main.py`

Add helper e.g. `_build_chart_sse_event(chart_spec, chart_png_base64) -> dict`:

```python
{
  "node_id": "__chart__",
  "status": "done",
  "chart_type": "bar" | "pie" | "line",
  "chart_spec": { "chart_type", "x_column", "y_column", "title_vi" },
  "chart_png_base64": "..."  # optional empty string if no image
}
```

In `stream_agent` event loop:
- When forwarding graph events, if event has `chart_spec` or `chart_png_base64` from `render_chart` node, also emit `__chart__` event (once per chart, after sanitize).
- On `__final_result__` / building `__answer__`: if chart was seen in stream (track last chart spec/png in generator local vars), attach to `ans_event["detail"]`:
  ```python
  detail_payload["chart_type"] = ...
  detail_payload["chart_spec"] = ...
  detail_payload["chart_png_base64"] = ...  # only if non-empty; or omit if huge — prefer reference via __chart__
  ```

For **cache hit** path: if cached answer had chart metadata (optional — skip if cache doesn't store chart yet).

Optional minimal **token** streaming: if respond produces full text at once, emit single `{"node_id":"__token__","status":"running","token":"..."}` before `__answer__` OR document that token=full answer chunk is acceptable for MVP. Do NOT refactor LLM to true streaming unless trivial.

### 2. Graph stream — ensure chart fields propagate

Verify `run_agent_stream` / `_wrap_node` already puts `chart_spec`, `chart_png_base64` on render_chart events (already in graph.py ~135-138). Fix gaps only if chart fields dropped before reaching main.py.

### 3. Frontend — `frontend/app.js` (minimal, no Chart.js)

Handle new SSE event types without breaking existing flow:

```javascript
if (event.node_id === '__chart__') {
  state.lastChart = event.chart_png_base64 || state.lastChart;
  state.lastChartSpec = event.chart_spec || null;
  state.lastChartType = event.chart_type || (event.chart_spec && event.chart_spec.chart_type);
  continue;
}
if (event.node_id === '__token__' && event.token) {
  // optional: accumulate token text for progressive display — skip if not implemented
}
```

Keep existing PNG display in `appendMessage` via `chart` param (base64 image). Do NOT add Chart.js (next task line 86).

Update placeholder text in chart-slot if chart spec received but no PNG.

### 4. Tests — `tests/test_sse_chart.py` (new)

1. `test_stream_emits_chart_event_on_render_chart` — mock `run_agent_stream` yielding render_chart done event with chart_spec + png, assert SSE contains `__chart__` with `chart_type`, `chart_spec`, `chart_png_base64`.
2. `test_stream_answer_detail_includes_chart_when_present` — mock stream with chart then final result, parse SSE, assert `__answer__` detail has `chart_type` or `chart_spec`.
3. `test_chart_sse_event_schema_fields` — chart_type in bar|pie|line, chart_spec has x_column/y_column/title_vi.
4. `test_stream_no_chart_event_when_no_chart` — plain docs question mock, no `__chart__` in SSE.

Use TestClient + mock `run_agent_stream` pattern from `tests/test_api.py`.

### 5. Docs

- Mark `[x] SSE: token/answer + event chart...` in `specs/implementation-plan.md`
- Append `specs/change-log.md` (2026-09-22)
- Run pytest, report count

### 6. Verify

```bash
cd agent-harness/dong
python -m pytest tests/test_sse_chart.py tests/test_chart_planner.py tests/test_api.py -q
python -m pytest -q
```

## Do NOT

- Chart.js FE rendering (line 86)
- Live graph hover JSON fix (line 87)
- Session history load (line 88)
- Refactor entire streaming architecture

## Acceptance

- SSE emits `__chart__` with chart_type + chart_spec + optional chart_png_base64
- `__answer__` includes chart info in detail when chart rendered
- FE handles `__chart__` without breaking existing PNG flow
- New tests green; full pytest green
