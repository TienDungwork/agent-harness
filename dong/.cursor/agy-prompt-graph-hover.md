# Task: Phase 4 line 87 ONLY — Live graph hover: JSON input/output khớp backend

Workdir: agent-harness/dong (already there)

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] Live graph hover: JSON input/output khớp backend.`

Do NOT implement line 88 (session short-term history) or any other task.

## Context

- Backend graph nodes emit SSE events with structured dict `input`/`output` (see src/agent/node_io.py, src/agent/graph.py `_wrap_node`, src/main.py `_sanitize_sse_event`).
- Right panel live graph: frontend/app.js — `upsertGraphNode()`, `showNodeIo()`, `formatIoValue()`, hover/click on `.graph-node` cards.
- Panel HTML: `#graph-io-body` (pre) in frontend/index.html.
- test-plan.md: "SSE graph | Hover khớp Langfuse" — hover must show same structured JSON as backend SSE/Langfuse trace.
- product-spec.md: "Trace: mỗi graph node ghi đủ input và output (Langfuse + SSE hover)."

## Likely gaps to fix

1. `upsertGraphNode`: when `status === 'running'`, SSE has no input/output — do NOT overwrite existing I/O with undefined/null on later updates; merge: keep prior input/output until done event provides them.
2. `formatIoValue`: if value is a JSON string, parse and pretty-print; objects → `JSON.stringify(val, null, 2)`; null/undefined → readable label.
3. `showNodeIo`: display pretty JSON for input and output separately; optionally include `meta` if stored on node state.
4. SSE handler (~line 884): pass full structured payload to upsertGraphNode (input, output, meta if present); ensure objects stay objects after JSON.parse (not re-stringified summaries).
5. Keep IO_MAX_CHARS = 80000 truncation with existing message.

## Tests (add/update)

Create `tests/test_frontend_graph_hover.py` (or extend tests/test_api.py) with static file assertions on frontend/app.js:
- `formatIoValue` handles object AND JSON string
- `upsertGraphNode` merges I/O (running does not wipe done data)
- `showNodeIo` uses pretty JSON (JSON.stringify with indent)
- SSE calls upsertGraphNode with event.input / event.output
- IO_MAX_CHARS present

Optional: one integration-style test mocking stream SSE payload with structured execute node `{input: {sql, params}, output: {rows, row_count}}` and assert app.js wiring stores objects.

Run: `python -m pytest tests/test_frontend_graph_hover.py tests/test_api.py -q` then `python -m pytest -q` — all must pass.

## Docs

After implementation:
1. Mark `[x] Live graph hover: JSON input/output khớp backend.` in specs/implementation-plan.md
2. Add entry to specs/change-log.md (date 2026-09-22, Phase 4 graph hover)

Do not modify unrelated files.
