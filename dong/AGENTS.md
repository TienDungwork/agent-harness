# AGENTS.md — agent dong (v6)

Hướng dẫn cho agent khi làm việc trong `agent-harness/dong`.

## Specs (đọc trước khi code)

1. `specs/product-spec.md` — mục tiêu & acceptance criteria
2. `specs/implementation-plan.md` — checklist từng phase & task
3. `specs/test-plan.md` — quy trình test offline (pytest) và live (Docker + 196)
4. `specs/change-log.md` — lịch sử thay đổi qua từng task

## Rules

- Always read the specs before coding.
- Implement only **one unchecked item** (`[ ]`) mỗi lần — đánh `[x]` khi xong.
- Keep the app simple; code ngắn, production-only, không thêm thư viện không cần thiết.
- Do not change architecture unless the spec is updated first.
- Đảm bảo Docker compose là đường chạy chính duy nhất (`docker compose up --build -d`).
- After each task:
  - Mark task completed (`[x]`) in `specs/implementation-plan.md`.
  - Update `specs/change-log.md` (1 entry ngắn).
  - Provide manual test steps & review against acceptance criteria.

## Quick Run & Test Commands

```bash
# Đường chạy chính (Docker):
cd agent-harness/dong
docker compose up --build -d
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/llm/ping

# Kiểm tra test offline nhanh:
pytest -q

# Chạy eval golden-30 (Phase 7):
python eval/run.py --judge
```

## Cursor + Antigravity Delegation

| Cursor | Antigravity |
|--------|-------------|
| Spec, plan, review | Implement **đúng 1 task** |

```bash
# Delegate 1 task cụ thể:
./scripts/antigravity-delegate.sh --workdir agent-harness/dong --timeout 600 "Continue with the next unchecked item in specs/implementation-plan.md..."
```
