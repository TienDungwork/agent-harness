# Task: Phase 4 — API sessions: list / create / delete; UI gọi thật

Implement ONLY this unchecked line in `specs/implementation-plan.md`:
`- [ ] API sessions: list / create / delete; UI gọi thật.`

Workdir: `agent-harness/dong`

## Context

- Phase 2 UI sidebar sessions uses **localStorage mock** (`agent_sessions` with sample data).
- Backend accepts `session_id`/`user_id` at `/api/chat` and `/api/agent/stream` but **no Sessions API**.
- Short-term memory: LangGraph `MemorySaver`, `thread_id = session_id`.
- Frontend: `agent_user_id`, `agent_session_id` in `frontend/app.js`.

## Goal

Backend in-memory Sessions API + Frontend calls real API for list/create/delete.

## Requirements

### 1. `src/sessions/store.py`

In-memory dict keyed by `user_id`. Session: `id`, `user_id`, `title`, `preview`, `updated_at`, `created_at` (ISO8601).

- `list_sessions(user_id)` — sorted updated_at desc
- `create_session(user_id, title="Phiên chat mới")`
- `delete_session(user_id, session_id)` → bool
- `get_session(user_id, session_id)`
- `update_session_meta(...)` optional
- `clear_sessions_store()` for tests

### 2. `src/main.py`

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/sessions?user_id=` | `{ "sessions": [...] }` |
| POST | `/api/sessions` `{user_id, title?}` | session object |
| DELETE | `/api/sessions/{session_id}?user_id=` | `{ "deleted": true }` or 404 |

### 3. `frontend/app.js`

- Init: GET sessions; if empty POST create; restore active id
- New chat: POST create
- Delete button per session item → DELETE
- Remove sample1/sample2 mock data
- Keep localStorage: `agent_user_id`, `agent_session_id` only
- **Do not** add session_id to stream body yet (next task line 84)

### 4. `tests/test_sessions_api.py`

TestClient: list empty, create, sort, delete ok, wrong user 404, not found 404, user isolation.

### 5. Mark `[x]`, update `specs/change-log.md`, run pytest.

## Do NOT

Stream session_id (line 84), chart SSE, checkpointer history, external DB.
