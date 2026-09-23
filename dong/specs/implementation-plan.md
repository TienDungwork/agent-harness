# Implementation Plan — agent dong v7

**Trạng thái:** Phase 1, 2, 3a, 3b **done**. Baseline v6 vẫn chạy.  
**Nguồn:** `specs/product-spec.md` · pattern `agent-harness/duy`.  
**Quy tắc:** làm **một dòng `[ ]`** mỗi lần → `[x]` + `change-log.md` + cách test ngắn.

---

## Tổng quan

| Phase | Tên | Mục tiêu ngắn |
|-------|-----|----------------|
| 1 | Project setup | Khóa hướng v7; baseline xanh |
| 2 | Core UI | Chart trên chat dễ đọc hơn |
| 3 | Core backend | Classify nhanh + pre/post SQL + text-to-SQL |
| 4 | Connect UI ↔ data | SSE chart + live graph khớp backend |
| 5 | Validation & errors | Lỗi rõ, không crash stream |
| 6 | Local run instructions | README / script chạy Docker |
| 7 | Production demo | Smoke + golden-30 trên LAN 196 |

**Thứ tự:** 1 → 2 → 3 → 4 → 5 → 6 → 7.  
*(Phase 7 thay “ngrok” trong guide — demo nội bộ qua Docker + gateway 196, không bắt buộc ngrok.)*

---

## Phase 1 — Project setup

- [x] Xác nhận `pytest -q` xanh trên baseline v6 (không đổi logic).
- [x] Xác nhận `docker compose` + health vẫn OK (ghi lệnh vào change-log nếu cần).
- [x] README / AGENTS: ghi rõ v7 = text-to-SQL + chart polish + classify nhanh (spec-first).
- [x] Liệt kê file dead sẽ xóa ở cuối Phase 3/7 (`tools.py`, `queries.py`, prompts ReAct, …) — **chỉ list, chưa xóa**.

**Done khi:** điểm bắt đầu rõ; app v6 vẫn chạy.

---

## Phase 2 — Core UI

- [x] Rà soát chỗ hiện chart trong chat (slot / canvas / img PNG).
- [x] Polish hiển thị bar: title, nhãn tiếng Việt, màu rõ, không méo / blank.
- [x] Polish hiển thị pie: legend đọc được, tỷ lệ rõ.
- [x] Placeholder / empty state khi chưa có chart (không che tin nhắn).
- [x] Cập nhật checklist UI smoke (1 câu bar, 1 câu pie).

**Done khi:** UI sẵn sàng nhận payload chart đẹp hơn (có thể mock data trước khi backend xong).

---

## Phase 3 — Core backend / data logic

### 3a — Classify fast path
- [x] Intent `chat` / clarify: LLM trả `answer` ngắn tiếng Việt.
- [x] Có inline answer → route END (không SQL, không docs).
- [x] Intent pipeline (`query_db`, docs, …): xóa `answer` sau parse (chống fake skip).
- [x] Skip orchestrator khi câu đơn `query_db` hoặc docs.
- [x] Skip rewrite khi `chat` hoặc TTL cache hit.
- [x] Cập nhật prompt `resource/prompts/classify/`.
- [x] Pytest: chào → 1 hop; câu số liệu → vẫn vào SQL path.

### 3b — Pre-SQL
- [x] Catalog retrieval scoped: chọn ≤4 bảng từ câu hỏi (học duy).
- [x] `retrieve_schema` chỉ excerpt bảng đã chọn (không dump full catalog).
- [x] Inject `time_range` (hôm nay / hôm qua / tháng) vào prompt generate.
- [x] Chart hint pre-SQL khi có từ khóa biểu đồ (vd. GROUP BY đúng cột).
- [x] Pytest: excerpt nhỏ hơn full catalog; time_range + chart hint có trong context.

### 3c — Text-to-SQL core
- [x] Prompt `resource/prompts/sql_agent/` (+ `production.txt`).
- [x] Node `generate_sql`: LLM → extract SQL; `max_tokens` cap.
- [x] Node `validate_sql` + repair ≤ `SQL_REPAIR_MAX` (default 2).
- [x] Node `execute_sql`: validate lại trước execute; Postgres read-only.
- [x] Graph: `query_db` → pre → generate → validate ↔ repair → execute (bỏ QueryPlan làm path chính).
- [x] Một hàm validate/repair dùng chung (graph + multi nếu còn).
- [x] Pytest: chặn DDL; repair mock; execute mock.

### 3d — Post-SQL & chart
- [x] `try_format_simple_answer()`: COUNT 1 dòng → template VI; skip respond LLM.
- [x] Chart detect (bar / pie / line nếu dễ).
- [x] Chart fallback SQL (học duy) khi GROUP BY sai / thiếu hàng.
- [x] Render chart đẹp: nhãn VI, title, màu/grid (PNG kiểu duy và/hoặc data cho Chart.js).
- [x] `respond` chỉ gọi LLM khi template không đủ; `max_tokens` cap.
- [x] Pytest: simple count không gọi respond LLM; chart meta / PNG không rỗng.

### 3e — Cleanup backend (sau khi path mới xanh)
- [x] Xóa / ngắt: `tools.py`, `queries.py`, `answer.py`, prompts ReAct không dùng.
- [x] Gỡ QueryPlan / `query_builder` khỏi path production.
- [x] Cập nhật `graph.mmd` / tên node Langfuse.

**Done khi:** chào hỏi 1 hop; số liệu đi text-to-SQL; chart backend đẹp hơn; dead code path chính đã gỡ.

---

## Phase 4 — Connect UI to data

- [x] SSE event chart mang đủ type + data/PNG cho FE.
- [x] Wire FE: nhận SSE → vẽ bar + pie trong bubble chat.
- [x] Live graph hover: I/O node SQL / chart khớp backend.
- [x] Session + stream vẫn gửi `session_id` / `user_id` (không regress v6).
- [x] Pytest / smoke: hỏi “vẽ biểu đồ…” → UI có chart.

**Done khi:** end-to-end hỏi → trả lời + chart trên UI.

---

## Phase 5 — Validation and error states

- [x] SQL invalid / hết lần repair → message ngắn tiếng Việt; không crash stream.
- [x] LLM timeout / DB fail → message ngắn (giữ pattern v6).
- [x] Classify lỗi → fallback an toàn (không im lặng).
- [x] Empty số liệu → trả lời đúng (có `"0"` khi rule yêu cầu).
- [x] Pytest: stream `__answer__` error thân thiện.

**Done khi:** case lỗi ổn định; pytest xanh.

---

## Phase 6 — Local run instructions

- [x] README: quick start **chỉ Docker** (`compose up --build`).
- [x] Ghi rõ: production = `self_hosted` @ 196; OpenAI = smoke.
- [x] Checklist: `.env`, health, llm ping, mở UI, smoke script.
- [x] Langfuse optional: lệnh ngắn trong README.
- [x] Cập nhật `AGENTS.md` khớp phase này.

**Done khi:** người mới chạy được app bằng Docker + `.env`, không cần `pip install` trên host.

---

## Phase 7 — Production demo (Docker + 196)

- [x] `./scripts/verify-docker-self-hosted.sh` OK.
- [x] `./scripts/smoke-production.sh` pass (session, TTL, bar, pie, fire/AIOC) — 7/7.
- [x] Smoke tay UI: chào hỏi nhanh + 1 chart đẹp — checklist `specs/smoke-manual-checklist.md` (bar/pie đã verify qua smoke API; UI tay: xin chào + biểu đồ cột trên `:3001`).
- [x] `python eval/run.py` → `eval/results/golden-30.md`.
- [x] Fix phản hồi “sự kiện phương tiện” + lọc `organization_id` SQL (bug live 2026-09-23).
- [ ] Target ≥28/30; ghi delta vào change-log — **27/30** (residual: 018, 021, 023).
- [x] Đối chiếu đủ acceptance criteria trong `product-spec.md` — xem change-log 2026-09-23 Phase 7 verify.
- [x] Finalize README / AGENTS: trạng thái v7 production verified (eval residual ghi rõ).

**Done v7 khi:** acceptance criteria đạt — **còn 1 tiêu chí eval (≥28/30).**

---

## Không làm trong các phase trên

- Web search, MCP, swarm, Ollama.
- ngrok bắt buộc (demo LAN 196 đủ).
- ClickHouse path mới; UI redesign toàn bộ.
- Thêm thư viện chart nặng nếu stack hiện có đủ sau polish.
