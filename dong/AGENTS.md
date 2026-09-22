# AGENTS.md

Quy tắc cho coding agent trên `agent-harness/dong`.

**Trạng thái:** v4 legacy ReAct đã thay trên đường chính; Phase 1–**7** xong; Dự án đã sẵn sàng để demo.

## Rules

1. **Đọc spec trước khi code** — `specs/product-spec.md`, `specs/implementation-plan.md`, `specs/test-plan.md`.
2. **Một phase hoặc một task** — checklist Phase 1→7; đánh `[x]` khi xong.
3. **Giữ app đơn giản** — module mỏng, ít layer; config một chỗ (`src/config.py`).
4. **Không thêm thư viện không cần thiết** — dùng stack hiện có trừ khi spec yêu cầu.
5. **Không đổi kiến trúc** nếu chưa cập nhật `specs/product-spec.md`.
6. **Sau mỗi lần implement:** cập nhật `specs/change-log.md`.
7. **Sau mỗi lần implement:** ghi rõ lệnh test cho user (theo `specs/test-plan.md`).

## Dong v5 (tóm tắt)

- Mọi LLM call → Pydantic structured (`invoke_structured`).
- DB read-only: `QueryPlan` → SQL parameterized → validator.
- Graph: `rewrite → classify → query|docs|out` (thay ReAct tool cố định).
- Deploy đường chính: Docker Compose only; không `.venv` trong quick start.

## Tests

- `tests/` < 10 file. `pytest -q` offline trước khi đánh phase xong.

## Antigravity (tuỳ chọn)

Cursor review; agy implement — `./scripts/antigravity-delegate.sh` (xem repo root `AGENTS.md`).
