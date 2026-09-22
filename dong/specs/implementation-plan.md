# Implementation Plan — dong v6

**Trạng thái:** Hoàn thành toàn bộ Phase 1 → 7 (MVP v6 sẵn sàng production demo & eval).
**Nguồn:** `specs/product-spec.md`. Một dòng checklist mỗi lần delegate; xong thì `[x]` + ghi `specs/change-log.md`.

## Quy tắc

- Đọc product-spec trước khi làm.
- Chỉ làm **một dòng `[ ]`** mỗi lần (không gom cả phase).
- Giữ app đơn giản; không thêm thư viện nếu không cần.
- Không đổi kiến trúc ngoài spec.
- Sau mỗi dòng: nói cách test ngắn.

## Tổng quan

| Phase | Tên | Mục tiêu ngắn |
|-------|-----|----------------|
| 1 | Project setup | `resource/`, dọn code, env/Docker sẵn sàng |
| 2 | Core UI | Sidebar sessions + chỗ vẽ chart + live graph |
| 3 | Core backend | Prompt LLMOps, LLM switch, memory, multi-agent graph |
| 4 | Connect UI ↔ backend | Session API, stream, chart SSE |
| 5 | Validation & errors | Guardrail, empty/fail, lỗi LLM/DB rõ |
| 6 | Run instructions | README Docker-only + checklist chạy local stack |
| 7 | Production demo & eval | Ping 196, golden-30 ≥28/30, báo cáo |

**Thứ tự:** 1 → 2 → 3 → 4 → 5 → 6 → 7 (trong phase 3: 3a → 3b → 3c).

---

## Phase 1 — Project setup

- [x] Tạo `resource/{prompts,docs,db,eval}`.
- [x] Chuyển `docs/vms_yaml/` → `resource/docs/vms_yaml/`; cập nhật path docs.
- [x] Chuyển `prompts/` → `resource/prompts/`; cập nhật registry default path.
- [x] Gom catalog/schema tĩnh vào `resource/db/`.
- [x] Xóa / ngắt dead path không dùng production (ReAct legacy, tool thừa khỏi entry).
- [x] `.env.example`: `LLM_BACKEND`, self_hosted 196, `OPENAI_API_KEYS`, `MEMORY_TTL_SECONDS=300`.
- [x] Dockerfile / compose COPY `resource/`; `pytest -q` vẫn xanh.

**Done khi:** cấu trúc `resource/` đúng; app vẫn start được qua Docker/pytest.

---

## Phase 2 — Core UI

- [x] Cột trái: danh sách session (thay 8 domain tag).
- [x] Nút New session; chọn session; preview 1 dòng + thời gian.
- [x] Domain chips chuyển vào khung chat (gợi ý nhanh).
- [x] Layout giữ: `[Sessions] | [Chat] | [Live graph]`.
- [x] Placeholder biểu đồ trong chat (sẵn chỗ render bar/pie).
- [x] `localStorage`: `user_id` ổn định + `session_id` hiện tại.

**Done khi:** UI session dùng được (mock list OK nếu API chưa có); không còn domain tag chiếm sidebar.

---

## Phase 3 — Core backend / data logic

### 3a — Prompt & LLM
- [x] Chuẩn hóa YAML prompt (ngắn) + `production.txt` alias.
- [x] Prompt tối thiểu: rewrite, classify, plan_query, answer_docs, respond_stat, plan_chart, orchestrator, memory_extract, judge_eval.
- [x] Agent chỉ gọi `registry.render(...)` — không hardcode prompt dài.
- [x] `LLM_BACKEND=openai|self_hosted`; rotation `OPENAI_API_KEYS`; `/api/llm/ping`.

### 3b — Memory
- [x] Short-term theo `session_id` (checkpointer MVP).
- [x] Long-term theo `user_id` (in-memory hoặc Qdrant MVP).
- [x] TTL cache 300s: hit trước graph khi trùng câu.
- [x] Node recall (đầu) + store/extract (cuối).

### 3c — Graph & quality
- [x] Trace mỗi node: **full** input + output (Langfuse + metadata session/user).
- [x] Chart planner: `ChartSpec` bar | pie (| line nếu dễ).
- [x] Multi-agent orchestrator MVP cho fail golden: 008, 009–011, 015, 017, 023, 024.
- [x] Docs AIOC / catalog dataset trong `resource/`.

**Done khi:** pytest memory/prompt/LLM mock xanh; 1 request stream có node I/O đầy đủ (test hoặc log).

---

## Phase 4 — Connect UI to data

- [x] API sessions: list / create / delete; UI gọi thật.
- [x] `POST /api/agent/stream` nhận `session_id`, `user_id`, câu hỏi.
- [x] SSE: token/answer + event chart (`chart_type` + spec hoặc image).
- [x] FE vẽ bar + pie từ payload (Chart.js ưu tiên).
- [x] Live graph hover: JSON input/output khớp backend.
- [x] Đổi session → load lịch sử short-term đúng phiên.

**Done khi:** end-to-end trên Docker: hỏi → trả lời + chart; đổi session không lẫn lịch sử.

---

## Phase 5 — Validation and error states

- [x] Out-of-scope / injection: từ chối rõ, tiếng Việt.
- [x] Empty số liệu: trả đúng (ví dụ phải có `"0"` khi rule yêu cầu).
- [x] Classify/route sai domain (fire/anomaly/water): fallback hoặc orchestrator, không im lặng.
- [x] Lỗi LLM / DB: message ngắn trên UI; không crash stream.
- [x] Thiếu biến prompt: lỗi rõ (không template trống).
- [x] TTL / memory fail: degrade an toàn (vẫn trả lời được).

**Done khi:** các case lỗi trên có hành vi ổn định; pytest/guardrail xanh.

---

## Phase 6 — Run instructions (Docker)

- [x] README quick start **chỉ Docker** (`compose up --build`).
- [x] Ghi rõ: production test dùng `self_hosted` @ 196; OpenAI = smoke.
- [x] Checklist: `.env`, health, llm ping, mở UI port.
- [x] Langfuse optional: lệnh ngắn trong README.
- [x] Venv chỉ appendix “dev nhanh” (không phải đường chính).
- [x] Cập nhật `AGENTS.md` cho khớp phase này.

**Done khi:** người mới chạy được app chỉ bằng Docker + `.env`, không cần `pip install` trên host.

---

## Phase 7 — Production demo & eval

- [x] Docker + `LLM_BACKEND=self_hosted` (196).
- [x] Smoke tay: session, short-term, TTL, bar, pie, 1 câu fire/AIOC.
- [x] `python eval/run.py` (live) → ghi `eval/results/golden-30.md`.
- [x] `python eval/run.py --judge` (rubric kiểu llm-engineer-demo).
- [x] Target **≥28/30** pass (baseline 22/30); ghi delta change-log.
- [x] Xác nhận acceptance criteria trong product-spec (mục 1–11).

**Done khi:** báo cáo golden cập nhật; ping 196 OK; đủ tiêu chí acceptance.

---

## Không làm trong các phase trên

- Ollama, Langfuse cloud prompt sync, MCP/swarm, ghi DB, graph editor, ngrok (không cần cho demo nội bộ LAN 196).
