# v17 — Rich Langfuse traces + MinIO charts + no-dict-`.get`

**Status:** Design approved (chat 2026-11-10) — chờ user review file này rồi mới writing-plans / code.  
**Approach:** Implement theo **hướng 2** — một phase, nhiều task có thứ tự (không big-bang một diff).  
**Rule liên quan:** `.cursor/rules/no-dict-get.mdc`

## Goal

1. **Langfuse:** trace bước lớn parity UI (input/output/metadata) + full system/user prompt (redact nhẹ) + `state_snapshot` slim.  
2. **MinIO chart:** sau render PNG → upload `chatbot-images` / prefix `chatbot/` → SSE/API trả `chart_url` (public-read); TTL **10 ngày**; base64 chỉ khi upload fail.  
3. **Code style:** trong toàn bộ `dong/src`, đọc field dict bằng `obj['key']` — migrate hết `.get` hiện có (trừ ngoại lệ hẹp trong rule).

UI (SSE) và Langfuse ghi **song song** từ `_wrap_node` / `trace_step` — không copy qua lại.

## Non-goals

- Không đổi topology LangGraph.  
- Không đẩy chart PNG / full `rows` / full `events` lên Langfuse.  
- Không snapshot full `AgentState`.  
- Không bắt buộc golden-30 trong phase (optional smoke).  
- Không dùng MinIO Langfuse (`:9190`) cho chart chatbot.

## Quyết định đã chốt

| # | Quyết định |
|---|------------|
| 1 | Prompt Langfuse: **B** — full + redact nhẹ + truncate ~20–32 KB/field |
| 2 | State: **B** — slim `metadata.state_snapshot` |
| 3 | Trace helper: hướng **2** — `trace_payload` |
| 4 | Chart access: **B** — public-read trên prefix |
| 5 | Bucket/prefix: **`chatbot-images`** / **`chatbot/`** |
| 6 | SSE chart: **C** — ưu tiên `chart_url`; base64 chỉ khi upload fail |
| 7 | TTL object: **10 ngày** (MinIO lifecycle trên prefix `chatbot/`) |
| 8 | Scope phase: **A** — gộp MinIO + migrate `.get` vào v17 |
| 9 | Cách làm: **2** — task tuần tự (trace → MinIO → migrate `.get`) |

## Thứ tự implement (hướng 2)

```text
Task A  trace_payload + wire _wrap_node / invoke_text (+ structured)
    ↓
Task B  MinIO client + upload chart + chart_url SSE/FE + lifecycle 10d
    ↓
Task C  Migrate .get → ['key'] theo cụm package + pytest từng cụm
```

Mỗi task có PR/commit riêng (hoặc commit rõ trong cùng branch `dong`); không trộn migrate `.get` vào cùng diff MinIO nếu tránh được.

---

## Phần 1 — Langfuse rich traces

### Module

`src/infra/monitoring/trace_payload.py`

| Hàm | Việc |
|-----|------|
| `redact_text(s)` | Mask Bearer / `sk-…` / password-like; truncate + `…[truncated]` |
| `slim_state(state)` | Field slim (dưới) |
| `llm_io_payload(system, user, text)` | input/output đã redact |

### Wiring

1. `_wrap_node`: `metadata.state_snapshot = slim_state(state)`; I/O từ `events` như SSE.  
2. `invoke_text` (+ structured generation): full `system`/`user`/`text` qua helper.  
3. Fail-safe Langfuse giữ nguyên.

### `state_snapshot` fields

```text
question, intent, sql, error, repair_count,
row_count, orchestrator_step_index, respond_mode,
selected_tables (nếu có)
```

Loại: `rows`, `events`, `chart_png_base64`, `messages`, `schema_excerpt` đầy đủ.

---

## Phần 2 — MinIO chart (10 ngày)

### Cấu hình (`.env` / `.env_sample`)

```text
MINIO_ENDPOINT=http://192.168.1.198:9200
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=chatbot-images
MINIO_CHART_PREFIX=chatbot
MINIO_PUBLIC_BASE_URL=http://192.168.1.198:9200   # URL FE đọc (path-style)
CHART_OBJECT_TTL_DAYS=10
```

Credential **không** hardcode trong source.

### Object key

```text
chatbot/{session_id}/{uuid}.png
```

### Flow

```text
render_chart → png bytes/base64
    → upload MinIO (bucket chatbot-images, key chatbot/...)
    → success: SSE/API chart_url = public URL; không gửi base64 (hoặc bỏ png trong event)
    → fail: giữ chart_png_base64 như cũ (fallback C)
```

FE: `img src = chart_url` khi có; không thì data-URI base64.

### Lifecycle

- Rule MinIO trên bucket `chatbot-images`, filter prefix `chatbot/`, **Expiration Days = 10**.  
- Document lệnh `mc ilm` / Console trong plan; có thể làm tay 1 lần + ghi README/spec.

### Langfuse

- Chỉ `chart_url` / `png_len` / uploaded flag — **không** upload PNG lên Langfuse.

---

## Phần 3 — Migrate no-dict-`.get`

### Rule

`.cursor/rules/no-dict-get.mdc` — `obj['key']`; cấm `.get` trên dict nghiệp vụ.

### Ngoại lệ

- `os.environ.get` / `os.getenv`  
- Biên thư viện bắt buộc `.get` (ghi chú ngắn tại call site)

### Cách migrate (theo cụm)

Ước ~50 file / hàng trăm chỗ. Thứ tự gợi ý:

1. `infra/monitoring`, `infra/llm` (sát Task A)  
2. `infra/*` còn lại  
3. `domain/agents/**`  
4. `application/`, `api/**`, `shared/**`  
5. Grep cuối: không còn `.get(` trái phép trong `src/`

Hành vi: chỗ từng `get(k, default)` → đảm bảo key luôn có trong state/payload **hoặc** `'k' in obj` rồi `obj['k']` — **không** đổi semantics âm thầm thành crash trên path happy; path optional phải explicit.

---

## Acceptance

| ID | Tiêu chí |
|----|----------|
| AC-1 | Node lớn trên Langfuse: I/O ≈ UI timeline |
| AC-2 | LLM span: `input.system` + `input.user` (redacted); không chỉ `*_len` |
| AC-3 | `state_snapshot` slim; không `rows`/`events`/`chart_png_base64` |
| AC-4 | Langfuse fail-safe không 500 request |
| AC-5 | Unit `trace_payload` |
| AC-6 | Chart upload → `chart_url` trỏ `.../chatbot-images/chatbot/...`; FE load được |
| AC-7 | Upload fail → vẫn có base64 trên SSE |
| AC-8 | Lifecycle 10 ngày documented + áp dụng trên prefix `chatbot/` |
| AC-9 | Grep `src`: không còn dict `.get` trái rule; pytest cụm migrate pass |

## Risks

| Risk | Mitigation |
|------|------------|
| Migrate `.get` đổi semantics | Task C tách; test theo package; `'k' in` khi optional |
| Bucket private mặc định | Cấu hình public-read **prefix** `chatbot/` (hoặc policy bucket theo ops) |
| MinIO down | Fallback base64 (C) |
| Prompt PII | Redact secret only (đã chọn B) |

## Out of scope / follow-up

- Skill `/ponita` (`that does:` còn trống).  
- Presigned URL / proxy chart.  
- Lưu chart vào `ai-images` (không dùng — dùng `chatbot-images`).
