# Task: Phase 5 line 96 ONLY — Out-of-scope / injection: từ chối rõ, tiếng Việt

Workdir: agent-harness/dong

Implement ONLY:
`- [ ] Out-of-scope / injection: từ chối rõ, tiếng Việt.`

Do NOT implement lines 97–102 or other phases.

## Problem

- Injection/toxic: API trả `detail: "Câu hỏi bị từ chối: prompt_injection_detected"` — lộ mã máy, không thân thiện tiếng Việt.
- Eval golden-30 (`eval/datasets/agent_stat/v2.yaml` cases 028–030) vẫn cần field `reason: prompt_injection_detected` (giữ mã trong JSON, không nhét vào detail user-facing).
- Out-of-scope: `OUT_OF_SCOPE_REPLY` đã tiếng Việt; cần đảm bảo `/api/chat`, `/api/agent/stream`, FE stream hiển thị rõ.
- `test_api_agent_stream_prompt_injection_blocked` thiếu `session_id`/`user_id` — có thể test sai nguyên nhân 400.

## Implementation

### 1. `src/guardrails.py`
- Thêm `INJECTION_REJECT_MESSAGE`, `TOXIC_REJECT_MESSAGE` (tiếng Việt, rõ ràng).
- Thêm `rejection_detail(reason: str) -> str` map reason code → message tiếng Việt.

### 2. `src/main.py`
- `guardrail_violation_handler`: `detail=rejection_detail(exc.reason)`; giữ `reason=exc.reason` cho eval.
- Stream out_of_scope: đảm bảo `__answer__` output là `OUT_OF_SCOPE_REPLY`; guardrail node có thể thêm `detail.status=out_of_scope` nếu cần (không phá FE).

### 3. Tests — `tests/test_phase5_guardrail_vi.py` (new) hoặc extend `tests/test_guardrails.py` + `tests/test_api.py`:
- Injection `/api/chat` + `/api/agent/stream` (có session_id, user_id): status 400, `detail` tiếng Việt (không chứa raw `prompt_injection_detected`), `reason` vẫn có mã.
- Toxic: tương tự với `unsafe_content`.
- Out-of-scope `/api/chat` + stream: 200/SSE answer chứa "ngoài phạm vi" hoặc nội dung `OUT_OF_SCOPE_REPLY`.
- Sửa test stream injection cũ nếu thiếu session fields.

Run: `pytest tests/test_phase5_guardrail_vi.py tests/test_guardrails.py tests/test_api.py tests/test_readonly.py -q` then `pytest -q`.

## Docs
- Mark `[x]` line 96 in specs/implementation-plan.md
- Entry specs/change-log.md

Do not modify unrelated files.
