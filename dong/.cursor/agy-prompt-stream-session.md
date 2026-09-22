# Task: Phase 4 — POST /api/agent/stream nhận session_id, user_id, câu hỏi

Implement ONLY this unchecked line in `specs/implementation-plan.md`:
`- [ ] POST /api/agent/stream nhận session_id, user_id, câu hỏi.`

Workdir: `agent-harness/dong`

## Context

- Backend `ChatRequest` in `src/main.py` already has optional fields:
  `session_id: str = "default"`, `user_id: str = "default"`.
- `/api/agent/stream` already passes `session_id`/`user_id` to `run_agent_stream` and Langfuse metadata when present in request.
- Frontend `handleSendMessage()` in `frontend/app.js` currently sends ONLY:
  `{ question, model_provider }` — **missing session_id and user_id**.
- `state.userId` and `state.activeSessionId` are available from Phase 4 sessions API.
- Short-term memory uses `thread_id = session_id` in graph checkpointer.

## Goal

Wire end-to-end: UI stream request includes `session_id`, `user_id`, `question`; backend validates and propagates to graph/memory/trace.

## Requirements

### 1. Backend — `src/main.py`

- Ensure `/api/agent/stream` uses `session_id` and `user_id` from request body (already mostly done — verify/fix gaps).
- Add lightweight validation for stream (and optionally `/api/chat` for consistency):
  - Reject empty/whitespace-only `session_id` or `user_id` with HTTP 400 (message tiếng Việt ngắn).
  - Do NOT require UUID format — any non-empty string OK.
- Include `session_id` and `user_id` in SSE trace metadata on graph node events if not already (check `_wrap_node` / stream events — add to event dict meta field if missing and cheap).
- Keep backward compat: if tests send only `{question}`, either still work with defaults OR update tests to pass explicit ids — prefer explicit ids in new tests.

### 2. Frontend — `frontend/app.js`

In `handleSendMessage()` fetch body, change to:

```javascript
body: JSON.stringify({
  question: question,
  model_provider: state.activeModel,
  session_id: state.activeSessionId,
  user_id: state.userId,
})
```

- Guard: if `!state.activeSessionId`, call `createNewSession()` first (already partially handled).
- Do NOT implement chart SSE or Chart.js (next tasks).

### 3. Tests

Add or extend tests (prefer `tests/test_api.py` or new `tests/test_stream_session.py`):

1. `test_api_agent_stream_accepts_session_and_user_id` — POST with explicit ids, mock `run_agent_stream`, assert kwargs `session_id` and `user_id` match.
2. `test_api_agent_stream_rejects_empty_session_id` — 400 when session_id="" or whitespace.
3. `test_api_agent_stream_rejects_empty_user_id` — 400 when user_id="" or whitespace.
4. Optional: assert SSE first graph event meta contains session_id/user_id if implemented.

Use existing TestClient + mock `run_agent_stream` pattern from `test_api_agent_stream_smoke`.

Update `test_api_agent_stream_passes_trace_parent_span` if needed to include session_id/user_id in json body.

### 4. Docs

- Mark `[x] POST /api/agent/stream nhận session_id, user_id, câu hỏi.` in `specs/implementation-plan.md`
- Append entry to `specs/change-log.md` (2026-09-22)
- Run pytest and report count

### 5. Verify

```bash
cd agent-harness/dong
python -m pytest tests/test_api.py tests/test_stream_session.py -q  # if new file
python -m pytest -q
```

## Do NOT

- Chart SSE events (line 85)
- Chart.js frontend (line 86)
- Session history load from checkpointer (line 88)
- PATCH session preview sync
- Unrelated refactors

## Acceptance

- FE stream POST sends session_id + user_id + question
- Backend validates non-empty ids and passes to run_agent_stream
- New tests green; full pytest green
