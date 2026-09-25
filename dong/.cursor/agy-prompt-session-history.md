# Task: Phase 4 line 88 ONLY — Đổi session → load lịch sử short-term đúng phiên

Workdir: agent-harness/dong

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] Đổi session → load lịch sử short-term đúng phiên.`

Do NOT implement Phase 5+ or other unchecked lines.

## Problem

- Sessions API (`GET/POST/DELETE /api/sessions`) chỉ lưu metadata (title, preview) — **không** lưu messages.
- FE (`frontend/app.js`) giữ messages trong `state.sessions[].messages` in-memory; reload hoặc đổi phiên có thể mất/lẫn lịch sử.
- Backend short-term checkpointer (LangGraph MemorySaver, `thread_id=session_id`) chỉ lưu HumanMessage cho graph context — **không** đủ để render UI chat (thiếu assistant answer, chart, detail).

## Goal (product-spec AC #6, test-plan Memory short-term)

Khi user đổi session trên sidebar → chat panel hiển thị **đúng** lịch sử Q&A của phiên đó, không lẫn phiên khác. Sau reload trang vẫn load được lịch sử đã chat.

## Implementation (minimal, production-only)

### Backend

1. **`src/sessions/store.py`**
   - Thêm `"messages": []` khi `create_session`.
   - `get_session_messages(session_id, user_id) -> list[dict]`
   - `append_session_messages(session_id, user_id, messages: list[dict]) -> dict | None` — append, cập nhật `updated_at`, optional auto title/preview từ user message đầu / answer gần nhất.

2. **`src/sessions/schemas.py`**
   - `SessionMessage`: role, content, timestamp, detail (optional dict), chart (optional dict)
   - `SessionMessagesResponse`: messages: list[SessionMessage]

3. **`src/main.py`**
   - `GET /api/sessions/{session_id}/messages?user_id=` → 404 nếu session không thuộc user; trả messages list.
   - Trong `stream_agent` event_generator: sau mỗi `__answer__` done (cache hit, out_of_scope, normal stream) → gọi `append_session_messages` lưu cặp `{role:user, content:question}` + `{role:assistant, content:answer, detail, chart?}`.
   - Cập nhật `update_session_meta` preview/title khi append (nếu chưa có logic).

4. Export new functions from `src/sessions/__init__.py` if needed.

### Frontend

5. **`frontend/app.js`**
   - `loadCurrentSessionMessages()` → **async**: fetch `GET /api/sessions/{id}/messages?user_id=`; render messages; reset graph; show welcome nếu rỗng.
   - `switchSession`, `init()` (sau initUserAndSessions), `deleteSession` fallback: await loadCurrentSessionMessages.
   - Giữ optimistic local push khi gửi tin (UX); sau stream __answer__ có thể rely on server persistence khi switch back.
   - Đảm bảo `appendMessage` nhận chart object từ stored messages.

### Tests

6. **`tests/test_session_messages.py`** (new) hoặc extend `tests/test_sessions_api.py`:
   - append/get messages isolation giữa 2 session_id cùng user
   - GET messages 404 wrong user
   - Stream (mock) append messages và GET trả đúng
   - FE static: `loadCurrentSessionMessages` fetch `/api/sessions/` + `/messages`

Run: `python -m pytest tests/test_session_messages.py tests/test_sessions_api.py tests/test_memory_shortterm.py -q` then `python -m pytest -q`.

## Docs

- Mark `[x]` line 88 in specs/implementation-plan.md
- Add entry specs/change-log.md (2026-09-22, Phase 4 session history)

Do not modify unrelated files.
