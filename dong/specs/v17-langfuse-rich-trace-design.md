# v17 — Langfuse rich traces (parity UI + prompts + slim state)

**Status:** Design approved (chat 2026-11-10) — chờ user review file này rồi mới writing-plans / code.  
**Approach:** Helper chuẩn `trace_payload` (hướng **2**).  
**Không:** Đổi topology graph; không gửi chart PNG / full `rows` / full `events` lên Langfuse.

## Goal

Trace các **bước lớn** trên Langfuse đầy đủ tương đương timeline UI (input/output/metadata), cộng thêm:

- Full **system / user prompt** + output text trên span LLM (sau **redaction nhẹ**).
- **`state_snapshot` rút gọn** trên mỗi node span lớn.

Nguồn sự thật vẫn là kết quả node / LLM call: UI (SSE) và Langfuse được ghi **song song** từ `_wrap_node` / `trace_step` — không copy UI→Langfuse hay ngược lại.

## Non-goals

- Không đổi payload SSE / giao diện chat.
- Không lưu chart ra disk; không đẩy `chart_png_base64` lên Langfuse.
- Không snapshot full `AgentState` (loại `rows`, `events`, `messages`, `schema_excerpt` đầy đủ, chart).
- Không làm lại golden-30 bắt buộc trong phase này (optional smoke tay).

## Quyết định đã chốt

| # | Quyết định |
|---|------------|
| 1 | Prompt: **B** — full text + redaction nhẹ (mask secret; truncate cứng ~20–32 KB/field) |
| 2 | State: **B** — slim fields trên `metadata.state_snapshot` |
| 3 | Kiến trúc: **2** — helper `trace_payload` dùng chung |
| 4 | Node I/O giữ parity SSE (`json_safe`); không thay bằng state |

## Kiến trúc

```text
node / LLM call
    │
    ├─► helper: redact_text / slim_state / llm_io_payload
    │
    ├─► Langfuse: trace_step / _wrap_node  (input, output, metadata)
    └─► SSE queue: q.put(...)               (như hiện tại — không đổi contract)
```

### Module mới

`src/infra/monitoring/trace_payload.py`

| Hàm | Việc |
|-----|------|
| `redact_text(s)` | Mask Bearer / `sk-…` / pattern password-like; truncate + `…[truncated]` |
| `slim_state(state)` | Dict field quan trọng (xem dưới) |
| `llm_io_payload(system, user, text)` | `{input: {system, user}, output: {text}}` đã redact |

### Wiring

1. **`_wrap_node`** (`domain/agents/graph.py`): khi finish span node, set `metadata.state_snapshot = slim_state(state)` (cùng lúc I/O từ `events` như hiện tại).
2. **`invoke_text`** (`infra/llm/client.py`): thay `system_len`/`user_len`/`text_len` bằng payload từ `llm_io_payload`.
3. **Structured LLM** (nếu cùng pattern length-only): áp dụng tương tự khi có generation span.
4. Giữ fail-safe Langfuse: lỗi update/trace không làm fail request.

## Payload

### LLM generation span

```text
input:  { system, user }     # full sau redact
output: { text }             # full sau redact (+ truncate nếu cần)
metadata: model_name, temperature, token usage (giữ như hiện tại)
```

### Node span — `metadata.state_snapshot`

```text
question, intent, sql, error, repair_count,
row_count, orchestrator_step_index, respond_mode,
selected_tables (nếu có)
```

**Loại trừ:** `rows`, `events`, `chart_png_base64`, `messages`, `schema_excerpt` đầy đủ, binary lớn.

### Node I/O

Giữ `step["input"]` / `step["output"]` từ `node_event` / SSE (`json_safe`) — parity UI.

## Chart (tham chiếu — ngoài thay đổi)

Chart hiện **không lưu file** khi agent render:

- Memory: `AgentState.chart_png_base64`
- SSE → UI: `data:image/png;base64,...`
- Disk chỉ dùng cho ảnh feedback dislike: `data/feedback/attachments/`

v17 **không** đẩy PNG lên Langfuse (chỉ giữ flag/`png_len` nếu đã có).

## Acceptance

| ID | Tiêu chí |
|----|----------|
| AC-1 | Trace 1 lượt SQL: mỗi node lớn có input/output tương đương UI timeline |
| AC-2 | Span LLM có `input.system` + `input.user` (không chỉ `*_len`); secret bị mask trong fixture |
| AC-3 | Mỗi node lớn có `metadata.state_snapshot` với đúng field slim; không có `rows`/`events`/`chart_png_base64` |
| AC-4 | Monitoring fail-safe: tắt/mock Langfuse không làm 500 request |
| AC-5 | Unit tests cho `redact_text` + `slim_state` + LLM payload shape |

## Test plan (phase này)

- Unit: `tests/test_trace_payload.py` (redact, slim, truncate).
- Unit/mock: LLM path ghi full prompt fields sau redact.
- Manual (optional): UI hỏi 1 câu → mở Langfuse so sánh timeline.

## Risks

| Risk | Mitigation |
|------|------------|
| Prompt vẫn chứa PII nghiệp vụ | Redact chỉ secret; chấp nhận theo lựa chọn B |
| Truncate cắt giữa schema | Metadata ghi `truncated: true` / độ dài gốc nếu cần |
| Call site LLM khác quên helper | Grep `system_len` / length-only traces; sửa cùng PR |

## Out of scope / follow-up

- Skill `/ponita` (prompt user còn trống `that does:`) — tách discovery create-skill.
- C-lite full state / lưu chart disk / dual-write từ SSE.
