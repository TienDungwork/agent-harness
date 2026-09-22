# Task: Phase 5 line 97 ONLY — Empty số liệu: trả đúng (có "0" khi rule yêu cầu)

Workdir: agent-harness/dong

Implement ONLY:
`- [ ] Empty số liệu: trả đúng (ví dụ phải có "0" khi rule yêu cầu).`

## Context

- Golden-30 case 008 (`eval/datasets/agent_stat/v2.yaml`): `must_include: ["0"]` khi đếm đám đông không có sự kiện.
- `respond_node` đã có message có "0 lượt / 0 kết quả" khi `not rows`.
- `EMPTY_TOOL_REPLY` trong guardrails **thiếu** số "0" — khi LLM bịa số trên tool rỗng, output guardrail mất "0".
- `check_output(..., tool_empty=True)` giữ câu trả lời "trung thực" không có "0" — eval fail.

## Implementation

1. **`src/guardrails.py`**
   - Thêm `empty_stat_reply() -> str` — message chuẩn có "0 lượt / 0 kết quả".
   - `EMPTY_TOOL_REPLY = empty_stat_reply()` (hoặc alias).
   - `check_output`: khi `tool_empty=True` và answer không chứa `"0"` → chuẩn hoá về `empty_stat_reply()`.

2. **`src/agent/graph.py`**
   - `respond_node`: dùng `empty_stat_reply()` thay chuỗi hardcode.
   - `orchestrator_respond_node`: empty query path dùng `empty_stat_reply()`.

3. **Tests** — `tests/test_phase5_empty_stat.py`:
   - `empty_stat_reply()` chứa "0".
   - `respond_node` với rows=[] → answer có "0".
   - `check_output` tool_empty + fabricated → có "0".
   - `check_output` tool_empty + honest không có "0" → chuẩn hoá có "0".
   - API mock empty query → answer có "0".

Run `pytest tests/test_phase5_empty_stat.py tests/test_guardrails.py tests/test_orchestrator.py -q` then `pytest -q`.

## Docs
- Mark `[x]` line 97 in specs/implementation-plan.md
- Entry specs/change-log.md

Do not modify unrelated files.
