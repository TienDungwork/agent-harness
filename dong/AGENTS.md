# AGENTS.md

Quy tắc cho coding agent trên `agent-harness/dong` (v4).

**Phase 1–4 xong.** Phase tiếp theo: **5 — Trace, tối ưu, stream sự kiện node**.

## Rules

1. **Always read the specs before coding** — `specs/product-spec.md`, `implementation-plan.md`, `test-plan.md`.
2. **Implement only one phase or task at a time** — theo checklist Phase 1→10 trong `implementation-plan.md`. Không nhảy phase.
3. **Keep the app simple** — code ngắn kiểu `llm-engineer-demo`. Một việc một chỗ.
4. **Do not add unnecessary libraries** — chỉ thêm package khi spec yêu cầu rõ.
5. **Do not change architecture unless the spec is updated** — sau Phase 3: chỉ `src/` (+ `frontend/`). Không tạo lại `backend/`. Không web search / text-to-SQL / ghi DB trừ khi đổi product-spec.
6. **After each implementation, update `specs/change-log.md`** — Added/Changed/Verified; đánh `[x]` checklist phase.
7. **After each implementation, explain how to test** — lệnh cụ thể cho người dùng chạy (agent không tự chạy app theo project policy).

## Project notes (ngắn)

- LLM: `LLM_*` → Ollama `192.168.1.196:11434` / `qwen3-16k-nothink:latest` (đã ghi `.env.example`).
- Dữ liệu chỉ đọc. How-to từ tài liệu local. Live graph: stream node, UI ~50%, hover → input/output.
- `tests/` dưới 10 file. Phase 8: `eval/results/golden-30.md` đủ 30 câu.
- Không commit `.env`.
