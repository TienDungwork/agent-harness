# Task — Phase 5 line 100: Thiếu biến prompt — lỗi rõ (không template trống)

Workdir: agent-harness/dong (repo root for this subproject).

Implement ONLY this unchecked item from specs/implementation-plan.md:
`- [ ] Thiếu biến prompt: lỗi rõ (không template trống).`

Do NOT implement line 101 (TTL/memory) or unrelated tasks.

## Context

- `src/prompts/registry.py` — `PromptRegistry.render()` already raises `ValueError("Thiếu biến khi render prompt: {missing}")` when kwargs missing.
- `tests/test_llm.py` — existing tests for missing var on `agent_system`.
- `src/main.py` — `_format_error_message()` maps DB/LLM errors to short Vietnamese UI messages.
- test-plan.md: "Prompt registry | render production; thiếu biến → ValueError"

## Requirements

1. **Registry hardening** (`src/prompts/registry.py`):
   - Reject empty/whitespace-only template before render → raise `ValueError` with clear message including prompt `name` (e.g. `"Prompt 'X' có template rỗng"`).
   - Improve missing-variable error: include prompt `name` + list of missing vars in Vietnamese (e.g. `"Prompt 'agent_system' thiếu biến: ['now']"`).
   - After `.format()`, validate rendered string is non-empty; if empty → raise `ValueError`.
   - Optional: detect unreplaced `{placeholders}` left in rendered output → raise `ValueError` (prevent sending broken template to LLM).

2. **User-facing errors** (`src/main.py`):
   - Extend `_format_error_message()` to recognize prompt render errors (missing var, empty template, unreplaced placeholders) → short Vietnamese message like: `"Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."`
   - Do NOT leak internal stack or full template content.

3. **Tests** — create `tests/test_phase5_prompt_vars.py`:
   - Empty template → ValueError with prompt name.
   - Missing required var → ValueError mentions prompt name + var name.
   - Successful render still works for `agent_system` with `now=...`.
   - `_format_error_message` maps prompt ValueError to friendly Vietnamese (no "Thiếu biến khi render prompt" raw text to user).
   - Optional integration: patch `registry().render` to raise prompt error during `/api/chat` or stream → 503 or stream `__answer__` error with friendly message (follow pattern from test_phase5_llm_db_errors.py).

4. **Update docs after implement**:
   - Mark `[x]` line 100 in `specs/implementation-plan.md`.
   - Add entry to `specs/change-log.md`.

5. **Run tests**:
   ```bash
   cd agent-harness/dong
   pytest tests/test_phase5_prompt_vars.py tests/test_llm.py -q
   pytest -q
   ```
   Fix any broken assertions in existing tests if error message format changed intentionally.

## Constraints

- Minimal diff — only files needed for this task.
- PEP 8, plain Python style per project rules.
- Do NOT add new features beyond prompt error clarity.
- Do NOT run live eval.

## Deliverables

- Code + tests passing
- implementation-plan line 100 checked
- change-log updated
