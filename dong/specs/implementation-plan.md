# Implementation Plan — dong v5

**v4 hoàn tất.** Plan này thay thế checklist 10 phase cũ. Phase 1–7 xong; Đã đạt trạng thái demo-ready.

## Quy tắc làm việc

- Mỗi lần implement **một phase** (hoặc một mục con trong Phase 2).
- Thứ tự: **1 → 2 → … → 7**. Không nhảy cóc.
- Khi xong phase: đánh `[x]`, ghi `specs/change-log.md`, chạy verify theo `specs/test-plan.md`.
- Tham chiếu: `specs/product-spec.md` (flow, schema, acceptance).

## Tổng quan phase

| Phase | Mục tiêu |
|-------|----------|
| **1** | Project setup — repo, env, baseline v4 vẫn chạy |
| **2** | Core backend & data logic — module thuần, pytest offline |
| **3** | Graph mới thay ReAct — nối module + SSE + Langfuse |
| **4** | Validation & error states — guardrail, fallback, thông báo lỗi |
| **5** | Docker run instructions — README + compose + Langfuse |
| **6** | Tests & eval — gom pytest, golden-30 |
| **7** | Demo setup — checklist 5 phút, dọn code thừa |

---

## Phase 1 — Project setup

**Mục tiêu:** Repo sẵn sàng implement v5; v4 vẫn `docker compose up` được.

### Checklist

- [x] Xác nhận cấu trúc `src/`, `frontend/`, `tests/`, `eval/`, `langfuse/` — khớp README v5.
- [x] Cập nhật `.env.example`: nhóm LLM, DB, Langfuse; thêm placeholder v5 (`DOCS_ROOT`, `SQL_REPAIR_MAX`).
- [x] Cập nhật `AGENTS.md`: một phase một task; structured output bắt buộc; Docker-only quick start.
- [x] `.gitignore`: `.env`, `.venv/`, `venv/`, `eval/results/`, `__pycache__/`.
- [x] Liệt kê code/file chết cần xóa ở Phase 7 (`ai/`, script one-off, import không dùng) — **đã xóa ở Phase 7**.
- [x] Baseline pytest v4: `pytest -q` xanh trước khi sửa logic v5.
- [x] Xác nhận `docker compose up --build -d` (app) và `langfuse/docker-compose.yml` (tuỳ chọn) vẫn healthy.

### Cleanup inventory (Phase 7 — đã xóa)

| Path | Lý do |
|------|--------|
| `ai/` | Legacy; `from backend.config` gãy; không import từ `src/` |
| `static/index.html` | UI cũ; đường chính UI là `frontend/` |
| `manual_test.sh` | Script one-off |
| `prep_changelog.sh` | Script one-off |
| `docs/vms/*.md` | Grep markdown v4; v5 dùng YAML cards (`DOCS_ROOT`) |
| `agent-canvas.md` | Doc tham chiếu, không thuộc runtime |

### Xong khi

- Spec v5 đồng bộ README/AGENTS; `.env.example` đủ key v5; Docker demo v4 không regress.

### Verify

```bash
cd agent-harness/dong
pytest -q
docker compose up --build -d
curl -s http://localhost:${BACKEND_PORT:-8000}/api/health
```

---

## Phase 2 — Core backend & data logic

**Mục tiêu:** Logic v5 dưới dạng **module thuần** — test offline, **chưa** thay graph ReAct. Graph wiring ở Phase 3.

### 2.1 Structured output layer

- [x] `src/llm/structured.py`: `invoke_structured(messages, schema) -> BaseModel`.
- [x] Pydantic schemas: `RewrittenQuestion`, `IntentResult`, `QueryPlan`, `DocsAnswer`, `StatAnswer`, `ChartSpec`.
- [x] Config một chỗ (`src/config.py` hoặc tương đương): timeout, model, `SQL_REPAIR_MAX`.
- [x] pytest mock `invoke_structured` — không gọi LAN 196.

### 2.2 Node rewrite & classify (logic)

- [x] `rewrite_question(raw) -> RewrittenQuestion` — prompt tiếng Việt, giữ ý, bổ sung filter/thời gian.
- [x] `classify_intent(rewritten) -> IntentResult` — structured; intent ∈ `query_data|how_to|troubleshoot|concept|out_of_scope`.
- [x] Thay classify free-text v4 bằng structured (hàm/module, chưa bắt buộc gắn graph).

### 2.3 Schema + QueryPlan builder

- [x] Port tối thiểu: catalog dataset + `describe_table` (từ duy, rút gọn).
- [x] `build_schema_excerpt(tables) -> str` cho prompt.
- [x] `plan_query(question, schema_excerpt) -> QueryPlan` (structured LLM).
- [x] `src/db/query_builder.py`: `QueryPlan` → SQL parameterized (`%s`).
- [x] `validate_sql(sql)`: SELECT-only, whitelist table/column, chặn DML/DDL.
- [x] `execute_sql(sql, params) -> rows` — Postgres read-only (+ ClickHouse tuỳ chọn).
- [x] Repair hook: input lỗi validate/execute → tối đa `SQL_REPAIR_MAX` lần replan (logic hàm, graph gọi ở Phase 3).

### 2.4 Docs YAML (duy)

- [x] `DOCS_ROOT` trỏ tới YAML cards (`VMS_doc` — copy/symlink từ duy).
- [x] Loader + keyword retrieval (top-k cards).
- [x] `retrieve_docs(query) -> cards`.
- [x] `answer_from_docs(question, cards) -> DocsAnswer` (structured).

### 2.5 Chart

- [x] `src/chart/render.py`: matplotlib Agg → PNG base64 từ rows + `ChartSpec`.
- [x] `should_render_chart(question, stat_answer) -> bool` — từ keyword hoặc `StatAnswer.chart_requested`.
- [x] `plan_chart(rows, question) -> ChartSpec` (structured, tuỳ chọn nếu không hardcode MVP).

### Xong khi (Phase 2)

- pytest offline cover: structured parse, rewrite/classify schema, plan→SQL, validator reject `DELETE`, docs retrieval, chart non-empty base64 (toàn bộ Phase 2 đã hoàn tất offline cover bao gồm chart).
- **Chưa** yêu cầu full SSE graph hay thay ReAct.

### Verify

```bash
pytest -q -k "structured or rewrite or query or docs or chart or validator"
find tests -name 'test_*.py' | wc -l   # mục tiêu < 10 khi Phase 6 gom xong
```

---

## Phase 3 — Graph mới thay ReAct

**Mục tiêu:** Pipeline LangGraph thay subgraph ReAct; giữ SSE live graph.

### Checklist

- [x] StateGraph: `START → rewrite → classify → [route]` theo `product-spec.md`.
- [x] Nhánh `query_data`: `retrieve_schema → plan_query → validate → execute → [render_chart] → respond → END`.
- [x] Nhánh docs: `retrieve_docs → answer_from_docs → END`.
- [x] Nhánh `out_of_scope`: từ chối một câu → END.
- [x] Gỡ ReAct (`chon_tool`/`chay_tool`) khỏi đường chính; deprecate 9 tool cố định v4.
- [x] `respond`: structured `StatAnswer`; template fallback nếu LLM lỗi.
- [x] `run_agent_stream` + queue SSE: mỗi node emit `running` / `done` + input/output rút gọn.
- [x] SSE chart: event `render_chart` kèm `chart_png_base64`.
- [x] Frontend: hiển thị `<img>` PNG dưới câu trả lời.
- [x] Langfuse: span nested per node; tên span khớp `node_id`; flush stream path (ContextVar v4).
- [x] Cache key: câu **sau rewrite** (ghi rõ trong config/code).
- [x] Cập nhật `graph.mmd` / diagram export.

### Xong khi

- Một lượt hỏi đi full pipeline qua `/api/agent/stream`; UI graph thấy `rewrite` → … → `respond` hoặc `answer_from_docs`.
- Không còn span `chon_tool`/`chay_tool` trên đường chính.

### Verify

- Live: 3 câu mẫu — đếm xe IN, how-to VMS, “vẽ biểu đồ lượt xe theo loại”.
- Langfuse: trace `chat` + nested spans khớp graph.

---

## Phase 4 — Validation and error states

**Mục tiêu:** Mọi nhánh lỗi có hành vi rõ — user, API, log, test.

### Checklist

- [x] **Guardrail:** injection → HTTP 400; out-of-scope (thời tiết, chính trị, …) → từ chối trước graph.
- [x] **LLM structured parse fail:** fallback message tiếng Việt; không crash stream; log/trace ghi lỗi.
- [x] **Classify `out_of_scope`:** câu trả lời ngắn, không gọi DB/docs.
- [x] **QueryPlan invalid:** validator reject → repair loop → sau `SQL_REPAIR_MAX` trả lỗi thân thiện (không leak SQL).
- [x] **DB lỗi / timeout:** message user-facing; span Langfuse `error`.
- [x] **Empty result set:** `respond` nói rõ “không có dữ liệu”, không bịa số.
- [x] **Docs không match card:** `DocsAnswer` với `card_ids` rỗng hoặc “không tìm thấy hướng dẫn”.
- [x] **Chart không render được:** bỏ qua chart, vẫn trả text answer.
- [x] **API stream:** client disconnect không làm worker treo; SSE error event nếu graph fail giữa chừng.
- [x] pytest: injection, OOS, validator reject, empty rows, parse fallback (mock).

### Xong khi

- `product-spec` acceptance #7 (read-only) + error paths có test; demo không “white screen” khi LLM/DB lỗi.

### Verify

```bash
pytest -q -k "guardrail or validator or error or empty"
```

---

## Phase 5 — Docker run instructions

**Mục tiêu:** Người mới chỉ cần README + compose để chạy app (và Langfuse tuỳ chọn).

### Checklist

- [x] README **Deploy**: prerequisites = Docker + Compose; **không** `.venv` trong quick start.
- [x] README: copy `.env.example` → `.env`; bảng biến LLM / DB / Langfuse / v5 (`DOCS_ROOT`).
- [x] README: lệnh `docker compose up` (app) vs `langfuse/docker compose up` (Langfuse tuỳ chọn).
- [x] README: bảng URL (frontend, backend health, Langfuse); credentials Langfuse local.
- [x] README: `LANGFUSE_HOST` — local vs Docker backend (`host.docker.internal`).
- [x] `docker-compose.yml`: app `frontend` + `ai_backend`; không nhúng Langfuse.
- [x] `langfuse/README.md` — compose riêng, không script wrapper.
- [x] Troubleshooting ngắn: UI sai API URL, không thấy trace, LLM ping fail, DB read-only.
- [x] Dev local uvicorn: mục **tuỳ chọn**, tách khỏi quick start.

### Xong khi

- Reviewer không cần hỏi thêm có thể `docker compose up` và mở UI; doc khớp file compose thực tế.

### Verify

- Làm theo README từ máy sạch (chỉ Docker): health OK, UI mở được.

---

## Phase 6 — Tests & eval

**Mục tiêu:** pytest gọn (< 10 file); golden-30 live + judge.

### Checklist

- [x] Gom/cập nhật tests: structured, rewrite, classify, query builder, docs, chart, stream, guardrail, errors.
- [x] `pytest -q` xanh offline (mock LLM/DB).
- [x] `test ! -d backend` — không thư mục backend legacy.
- [x] `eval/run.py` chạy `eval/datasets/agent_stat/v2.yaml` → `eval/results/golden-30.md`.
- [x] `eval/run.py --judge`: cột judge 1–5; **không** set `PYTEST_CURRENT_TEST` khi live.
- [x] CI/local doc: thời gian chạy golden (~15–30 phút), cần LAN 196 + DB.

### Xong khi

- `pytest -q` pass; golden-30 đủ 30 dòng `mode: live` (khi chạy live).

### Verify

```bash
pytest -q
find tests -name 'test_*.py' | wc -l
python eval/run.py --help
# Live (khi LLM/DB sẵn sàng):
python eval/run.py --judge
```

---

## Phase 7 — Demo setup

**Mục tiêu:** Demo 5 phút reproducible; repo sạch cho handoff.

### Checklist

- [x] Demo script/checklist trong README (hoặc `docs/demo-checklist.md` nếu README dài):
  1. `docker compose up --build -d` (+ Langfuse tuỳ chọn)
  2. Health + `/api/llm/ping`
  3. Câu số liệu (filter `vehicle_type`)
  4. Câu how-to VMS
  5. Câu biểu đồ → PNG trên UI
  6. Langfuse trace `chat` + nested spans
  7. Hover graph: input/output từng node
- [x] Xóa code/file đã liệt kê Phase 1 (`ai/`, dead script) sau khi test cover.
- [x] README **Current state**: v5 implemented; link acceptance `product-spec.md`.
- [x] `specs/change-log.md` ghi milestone v5 demo-ready.

### Xong khi

- Người demo lần đầu hoàn thành checklist ≤ 5 phút (trừ thời gian build image lần đầu).

---

## Không làm trong v5 MVP

- Full port web search duy.
- RAG vector, multi-agent, MCP.
- Text-to-SQL tự do không qua QueryPlan/validator.
- Ghi DB; graph editor kéo-thả; semantic cache.
- ApexCharts phức tạp (chỉ PNG MVP).

## Map phase cũ (10) → mới (7)

| Cũ | Mới |
|----|-----|
| Phase 1 Baseline | Phase 1 |
| Phase 2 Structured | Phase 2.1 |
| Phase 3 Rewrite | Phase 2.2 |
| Phase 4 QueryPlan | Phase 2.3 |
| Phase 5 Docs | Phase 2.4 |
| Phase 6 Chart | Phase 2.5 |
| Phase 7 Graph | Phase 3 |
| Phase 8 Respond/Langfuse | Phase 3 (+ cache) |
| Phase 9 Tests/eval | Phase 6 |
| Phase 10 Docker polish | Phase 5 + Phase 7 |
