# Implementation Plan — agent dong v9: Unified Memory & Context Engineering System (Postgres-backed)

**Trạng thái v9 (Memory):** 100% hoàn thành — 7 Phase bên dưới.  
**Trạng thái v10 (Cấu trúc `src/`):** Hoàn thành — API package + tách `graph.py` (facade ~90 dòng).  
**Trạng thái v13 (Nested Langfuse):** Code + tests — xem § v13.  
**Trạng thái v14 (ai_backend layout):** 14.1–14.4 done — [v14-ai-backend-layout-design.md](v14-ai-backend-layout-design.md); 14.5 optional.  
**Trạng thái v15 (leaf agents + flat graph):** 15.1–15.5 done — [v15-leaf-agents-flat-graph-design.md](v15-leaf-agents-flat-graph-design.md).  
**Trạng thái v16 (hierarchical teams):** 16.1–16.7 code (continuous) — [v16-hierarchical-agents-design.md](v16-hierarchical-agents-design.md) · [v16-hierarchical-agents-plan.md](v16-hierarchical-agents-plan.md).  
**Trạng thái v18 (IAM RBAC):** đang triển khai — [v18-rbac-iam-design.md](v18-rbac-iam-design.md) · [v18-rbac-iam-plan.md](v18-rbac-iam-plan.md).  
**Nguồn:** `specs/product-spec.md`, `specs/superpowers-workflow-vi.md`  
**Quy tắc:** Thực hiện tuần tự từng dòng `[ ]` một, kiểm tra kỹ lưỡng, sau đó đổi thành `[x]` và cập nhật `specs/change-log.md`. Không implement hàng loạt nhiều bước cùng lúc. **Task mới → thêm checklist ở đây trước khi code.**

---

## v18 — IAM RBAC + domain/geo + retrieval rename

**Goal:** Bộ phận chỉ hỏi domain được phép; SQL geo/org; IAM `/auth/me`.  
**Design:** [v18-rbac-iam-design.md](v18-rbac-iam-design.md) · **Plan:** [v18-rbac-iam-plan.md](v18-rbac-iam-plan.md) · **AC:** AC-12.

- [x] 18.1 Spec + AC-12 + index
- [x] 18.2 IAM gate + AccessContext
- [x] 18.3 Domain RBAC
- [x] 18.4 Geo SQL scope
- [x] 18.5 Docs domain filter
- [x] 18.6 Rename knowledge → retrieval
- [x] 18.7 FE headers + smoke

---

## v16 — Hierarchical `analytics_team` | `knowledge_team`

**Goal:** Root graph + team subgraphs + `AgentTurnService` (SSE mới).  
**Design:** [v16-hierarchical-agents-design.md](v16-hierarchical-agents-design.md) · **Plan:** [v16-hierarchical-agents-plan.md](v16-hierarchical-agents-plan.md).

| Task | Mục tiêu |
|:--:|-----------|
| **16.1** | Skeleton `AssistantState` + `build_graph` stub + `nodes` stub |
| **16.2** | Shared prefix / canonical root graph |
| **16.3** | `analytics/` subgraph |
| **16.4** | `knowledge/` subgraph |
| **16.5** | `top_supervisor` + `synth` |
| **16.6** | `AgentTurnService` + SSE + FE |
| **16.7** | Cleanup dead code |

### Phase 16.1 — Skeleton

- [x] `AssistantState` trên `domain/agents/state.py` (re-export vms I/O).
- [x] `nodes.py` stub supervisor/synth; `graph.build_graph` → vms `_build_graph`; `start_graph` stub.
- [x] `tests/test_v16_hierarchy_skeleton.py` PASS.

### Phase 16.2–16.7 — Continuous

- [x] 16.2 Canonical `domain/agents/graph.py`; `vms.graph` shim.
- [x] 16.3 `analytics/` subgraph + root `analytics_team`.
- [x] 16.4 `knowledge/` subgraph + root `knowledge_team`.
- [x] 16.5 `top_supervisor` (+ multi collect); route helpers.
- [x] 16.6 `AgentTurnService` + SSE `complete` + FE bridge.
- [x] 16.7 Docs/changelog; giữ `vms/nodes` (impl); không xóa hết shim nội bộ.

**Done khi:** `pytest tests/test_v16_*.py` + `test_graph_nodes_and_structure` xanh.

---

## v15 — Leaf `sql_agent` / `docs_agent` + flat `vms/graph.py`

**Goal:** Package giống `ai_backend` leaf; wiring flat; không đổi hành vi.  
**Design:** [v15-leaf-agents-flat-graph-design.md](v15-leaf-agents-flat-graph-design.md) · **Plan chi tiết:** [v15-leaf-agents-flat-graph-plan.md](v15-leaf-agents-flat-graph-plan.md) · **AC:** product-spec AC-11.

| Phase v15 | Mục tiêu |
|:--:|-----------|
| **15.1** | Spec + AC + checkbox |
| **15.2** | Skeleton + move sql/docs agents |
| **15.3** | Gộp `core/` → `vms/graph.py`; nodes/tools |
| **15.4** | Rewire + xóa package cũ |
| **15.5** | Docs + pytest subset |

### Phase 15.1 — Spec

- [x] Design `v15-leaf-agents-flat-graph-design.md` + AC-11 + index SDD.
- [x] User review / approve written spec trước khi code.
- [x] Writing-plans: `v15-leaf-agents-flat-graph-plan.md`.

**Done khi:** Spec reviewed.

### Phase 15.2 — sql_agent / docs_agent

- [x] Tạo `sql_agent/`, `docs_agent/` (`graph.py` re-export only, `state.py`, `tools.py`).
- [x] Move `vms/sql/*` + docs nodes/adapters; không `compile()`.

**Done khi:** Import package mới OK.

### Phase 15.3 — Flat graph

- [x] Gộp `vms/core/*` → `vms/graph.py`; giữ `_build_graph` / `run_agent` / `_wrap_node`.
- [x] `routing` / `respond` / `render_chart` / helpers → `vms/nodes` + `vms/tools`.
- [x] Xóa `vms/core/`.

**Done khi:** App boot; node names không đổi.

### Phase 15.4 — Rewire

- [x] Sửa import repo + tests; xóa `vms/sql`, `vms/routing`, `vms/respond`, `vms/adapters` nếu trống.
- [x] Grep sạch path cũ trong `.py`.

**Done khi:** Grep sạch.

### Phase 15.5 — Docs + verify

- [x] `src/README.md` + `change-log.md`.
- [x] Pytest subset (nodes structure, camera, greeting offline, v13) — **17 passed**.

**Done khi:** AC-11 pass.

---

## v14 — Align layout với `vn-stock-swarm/src/ai_backend`

**Goal:** `vms/` + `multi_agent/` + `application/` + `shared/settings/`; dọn specs core; không đổi hành vi.  
**Design:** [v14-ai-backend-layout-design.md](v14-ai-backend-layout-design.md) · **AC:** product-spec AC-10.

| Phase v14 | Mục tiêu |
|:--:|-----------|
| **14.1** | Specs hygiene (core + archive) |
| **14.2** | Package skeleton |
| **14.3** | Move + rewire + shims |
| **14.4** | Docs + pytest |
| **14.5** | Drop shims (optional) |

### Phase 14.1 — Specs hygiene

- [x] Archive `v7-chart-ui-audit.md`, `v7-dead-code-inventory.md`, `nested-trace-v13-design.md` (AC v13 đã ở product-spec / § v13).
- [x] Cập nhật `specs/README.md` + `sdd-guide-vi.md` danh sách file core.
- [x] Ghi `change-log.md` (design/hygiene).

**Done khi:** `specs/` chỉ còn core + `archive/` + `v14-ai-backend-layout-design.md`.

### Phase 14.2 — Package skeleton

- [x] Tạo `domain/agents/vms/`, `domain/agents/multi_agent/`, `application/`, `shared/settings/`.
- [x] `__init__.py` tối thiểu; chưa move logic nặng.

**Done khi:** Import package rỗng OK.

### Phase 14.3 — Move + rewire

- [x] Move graph/state/nodes/sql/routing/respond/adapters/core → `vms/`.
- [x] Move orchestrator → `multi_agent/`.
- [x] Tách turn orchestration mỏng → `application/` (nếu routes/main đang phình).
- [x] `shared/settings` từ `config.py` + shim `shared.config`.
- [x] Shim `domain.agents.graph` → `vms.graph`.
- [x] Sửa import toàn repo / tests.

**Done khi:** App boot; graph node names không đổi.

### Phase 14.4 — Docs + verify

- [x] Cập nhật `src/README.md`.
- [x] `pytest -q` (ghi fail pre-existing nếu có).
- [x] `change-log.md` entry code merge.

**Done khi:** AC-10 checklist pass.

**Verify note:** Node names LangGraph giữ nguyên; camera registry + greeting offline + audit archive path + `test_v13_*` xanh. Full suite chậm/có fail pre-existing (SQL offline heuristic `anomaly_event`, frontend memory badge string) — không phải regression layout v14.

### Phase 14.5 — Drop shims (optional)

- [x] Xóa shim `domain.agents.orchestrator` (grep sạch → chỉ còn `multi_agent`).
- [ ] Xóa shim `domain.agents.graph` / `state` + `shared.config` sau khi grep sạch.

**Done khi:** Không còn shim.

---

## v10 — Cấu trúc `src/` (pattern llm-engineer-demo)

**Goal:** Entry FastAPI mỏng, API tách package, giữ hành vi + test patch ổn định; tùy chọn tách `graph.py` khi có task riêng.

**Architecture:** `src/main.py` mount router; `src/api/*` routes + helpers; agent vẫn `src/agent/graph.py`.

| Phase v10 | Mục tiêu |
|:--:|-----------|
| **10.1** | Tách FastAPI khỏi `main.py` |
| **10.2** | Docs + SDD đồng bộ |
| **10.3** | Test suite xanh (API + orchestrator) |
| **10.4** | (Tùy chọn) Tách module trong `graph.py` |

### Phase 10.1 — API package

- [x] Tạo `src/api/`: `errors`, `cache_helpers`, `sse_helpers`, `session_helpers`, `schemas`.
- [x] Routers: `routes_meta`, `routes_sessions`, `routes_memory`, `routes_feedback`, `routes_agent`.
- [x] `src/main.py` ~70 dòng: CORS, `include_router`, static UI, `GuardrailViolation` handler, re-export hooks test (`_cache`, schemas, …).
- [x] `routes_agent` gọi `src.agent.graph.run_agent` / `run_agent_stream` (mock test đúng module).
- [x] Xóa trùng feedback + exception handler trong `routes_agent.py`.

**Done khi:** `pytest tests/test_product_api_gateway.py tests/test_feedback_api.py -q` pass.

### Phase 10.2 — Docs & spec index

- [x] Cập nhật `src/README.md` (mục `api/`).
- [x] Ghi `specs/change-log.md` (refactor API).
- [x] Cập nhật `specs/sdd-guide-vi.md` bảng API → `src/main.py` + `src/api/`.
- [x] Cập nhật `specs/README.md` trạng thái v10.
- [x] Không đổi AC endpoint — layout ghi trong `src/README.md`.

**Done khi:** Dev mới đọc specs + `src/README` biết chỗ sửa route mà không mở `graph.py`.

### Phase 10.3 — Regression tests

- [x] `test_same_thread_docs_then_stat_clears_respond_mode` — `recall_node` reset `rewritten=None` mỗi lượt.
- [x] Orchestrator + API gateway: 149 passed (subset graph + gateway).
- [x] Full suite `PYTHONPATH=. pytest -q`: **765 passed**, 24 failed (chủ yếu deployment smoke / Postgres thật / vài mock path cũ — ghi change-log).

**Done khi:** Hai test orchestrator trên pass; không regression API gateway.

### Phase 10.4 — Tách `graph.py`

- [x] Modules: `state`, `graph_runtime`, `graph_wiring`, `graph_run`, `graph_helpers`, `nodes_*`.
- [x] `graph.py` facade + re-export patch hooks (`classify_intent_safe`, `execute_sql`, `_memory_context_block`, …).

**Done khi:** `graph.py` < ~400 dòng — đạt (~90 dòng facade).

### Phase 11 — Layout `src/` (vn-stock `ai_backend`)

- [x] `domain/` (`agents`, `knowledge`), `infra/` (db, memory, llm, chart, monitoring, prompts, session), `shared/` (config, guardrails, feedback).
- [x] `api/routers`, `api/models`, `api/helpers`.
- [x] Sửa path `resource/` sau khi đổi depth (`catalog`, `prompts`, `camera_registry`).
- [x] Cập nhật import toàn repo + `src/README.md`.

**Done khi:** `from src.main import app` OK; pytest orchestrator + API gateway pass.

---

## v13 — Nested Langfuse `trace_step` toàn graph

**Goal:** Span con trong mọi node giống nhánh SQL — xem [archive/nested-trace-v13-design.md](archive/nested-trace-v13-design.md).  
**AC:** `product-spec.md` AC-9; test AC-T1–T3 trong `test-plan.md`.

| Phase v13 | Mục tiêu |
|:--:|-----------|
| **13.1** | Guardrails input/output + recall |
| **13.2** | rewrite + classify + respond_inline |
| **13.3** | orchestrator + orchestrator_collect |
| **13.4** | execute_sql batch + answer_from_docs + respond |
| **13.5** | Tests observability + manual Langfuse |

### Phase 13.1 — Guardrails + recall

- [x] `guardrail_input_node`: `trace_step` `check_input`, `redact_pii`.
- [x] `recall_node`: `trace_step` `recall_long_term` (kể cả disabled).
- [x] `guardrail_output_node`: `build_evidence`, `check_output`.

**Done khi:** AC-T1 cover guardrail_input + recall; pytest observability pass.

### Phase 13.2 — Rewrite / classify / inline

- [x] `rewrite_node`: `sliding_window`, `compact_history`, `rewrite_question`.
- [x] `classify_node`: `classify_intent`.
- [x] `respond_inline_node`: `inline_response`.

**Done khi:** AC-T1 cover rewrite + classify.

### Phase 13.3 — Orchestrator

- [x] `orchestrator_node`: một span trong `plan_passthrough` | `plan_orchestration` | `dispatch_batch`.
- [x] `orchestrator_collect_step_node`: `collect_step`.

**Done khi:** Multi-hop trace mock có substeps orchestrator.

### Phase 13.4 — SQL batch + docs + respond

- [x] `execute_sql_node` batch: per-item `apply_org_scope`, `revalidate_sql`, `postgres_query`.
- [x] `answer_from_docs_node`: `compress_docs` khi nén.
- [x] `respond_node`: substeps nhánh inline / out_of_scope / multi (`synthesize_multi`).

**Done khi:** AC-T2 pass; không regression respond tests.

### Phase 13.5 — Verification + docs

- [x] Mở rộng `tests/test_product_observability_errors.py` (AC-T1–T2; AC-T3: 41 pass, 6 fail cache/API cũ).
- [ ] Manual Langfuse §4.2 design doc.
- [x] `change-log.md` khi merge code; đánh dấu `[x]` các task 13.x.

**Done khi:** `pytest tests/test_product_observability_errors.py -q` pass; AC-9 đạt.

---

## Tổng quan các Phase

| Phase | Tên Phase | Mục tiêu chính |
|:-----:|-----------|----------------|
| **Phase 1** | Project setup | Xác nhận baseline test suite (pass 100%), thiết kế schema PostgreSQL `user_memories` và module `db.py` |
| **Phase 2** | Core UI | Cập nhật giao diện chat: hiển thị huy hiệu thông tin đã nhớ (Memory Badge), trạng thái Cache Hit, và nút Reset Memory |
| **Phase 3** | Core backend or data logic | Xây dựng các module cốt lõi: `longterm.py` (Postgres persistence), `context.py` (Sliding Window, 40% rule, Tool compression), `shortterm.py`, `ttl_cache.py`, `extract.py` |
| **Phase 4** | Connect UI to data | Tích hợp memory và context vào luồng LangGraph (`graph.py`), kết nối API reset memory và truyền metadata qua SSE stream |
| **Phase 5** | Validation and error states | Kiểm thử các trạng thái biên: fallback in-memory khi DB offline, cô lập `user_id`, hết hạn TTL cache và nén ngữ cảnh |
| **Phase 6** | Local run instructions | Cập nhật file `.env.example`, tài liệu `README.md` với các câu lệnh chạy local và chạy unit test suite |
| **Phase 7** | ngrok demo setup | Hướng dẫn expose app ra internet bằng ngrok và kịch bản demo kiểm chứng độ bền vững của Memory |

---

## Phase 1 — Project setup

- [x] Chạy và xác nhận baseline test suite `PYTHONPATH=. pytest -q` hiện tại đạt 100% pass (≥613 tests).
- [x] Thiết kế module `src/memory/db.py`: quản lý kết nối PostgreSQL an toàn từ `src/config.py` (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME_ITS`).
- [x] Viết hàm `init_memory_db()` tự động tạo bảng `user_memories` và index trong PostgreSQL nếu chưa tồn tại:
  ```sql
  CREATE TABLE IF NOT EXISTS user_memories (
      id SERIAL PRIMARY KEY,
      user_id VARCHAR(64) NOT NULL,
      fact TEXT NOT NULL,
      category VARCHAR(32) DEFAULT 'general',
      created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
  );
  CREATE INDEX IF NOT EXISTS idx_user_memories_uid ON user_memories(user_id);
  CREATE INDEX IF NOT EXISTS idx_user_memories_uid_created ON user_memories(user_id, created_at DESC);
  ```
- [x] Đảm bảo cơ chế an toàn: Nếu `DB_HOST` rỗng hoặc chưa kết nối được DB, `init_memory_db()` chỉ log warning, không chặn luồng khởi động app.

**Done khi:** Baseline test xanh 100%, module `src/memory/db.py` sẵn sàng khởi tạo bảng PostgreSQL với cơ chế an toàn không crash.

---

## Phase 2 — Core UI

- [x] **Memory & Context Status Bar (Thanh trạng thái bộ nhớ)**:
  - Thêm khu vực hiển thị thông tin người dùng thu nhỏ trên giao diện chat trong `frontend/index.html` và `frontend/style.css` (ví dụ: hiển thị tên hoặc số lượng facts đã nhớ của phiên hiện tại).
- [x] **Nút Đặt lại bộ nhớ (Reset Memory)**:
  - Bổ sung nút icon "Làm mới ngữ cảnh / Xóa bộ nhớ" trên thanh công cụ chat để người dùng có thể chủ động reset facts cá nhân khi cần bắt đầu phiên làm việc mới.
- [x] **Huy hiệu Cache Hit**:
  - Chuẩn bị thẻ thông báo nhỏ (badge) bên cạnh bubble câu trả lời khi kết quả được trả về từ TTL Cache (giúp người dùng và kỹ sư nhận biết phản hồi tức thì từ cache).

**Done khi:** Giao diện frontend có đầy đủ vị trí hiển thị memory status, nút reset memory và huy hiệu cache hit.

---

## Phase 3 — Core backend or data logic

- [x] **Long-Term Memory (`src/memory/longterm.py`)**:
  - Loại bỏ hoàn toàn mã thừa `vector=[0.0]`.
  - Triển khai `save_to_long_term(user_id, fact, category="general")`: ghi fact vào PostgreSQL.
  - Triển khai `recall_long_term(user_id, query, k=3)`: truy vấn facts của `user_id` từ PostgreSQL, tính điểm tương đồng từ khóa (token overlap) và trả về top-k fact.
  - Triển khai `clear_long_term(user_id)`: xóa fact trong PostgreSQL theo `user_id` hoặc xóa toàn bộ.
  - Triển khai cơ chế Fallback in-memory: tự động lưu và đọc từ RAM (`_FALLBACK_STORE`) khi không có kết nối DB.
- [x] **Context Engineering Engine (`src/memory/context.py` - theo mẫu `llm-engineer-demo`)**:
  - `_text_of(m)` và `_role_of(m)`: trích xuất text và role chuẩn từ dict hoặc BaseMessage.
  - `sliding_window(messages, max_messages=20)`: giữ N message gần nhất, bảo tồn system message gốc.
  - `estimate_tokens(messages)` & `context_usage(messages, window_tokens)`: đo lường tải context (hỗ trợ tiktoken / 4 ký tự/token).
  - `should_compact(messages, window_tokens, threshold=0.40)` & `should_compact_route(...)`: kiểm tra điều kiện và tạo conditional edge nén chủ động theo nguyên tắc 40-60%.
  - `summarize_text(old_messages)` & `summarize_old_messages(messages, keep_recent=6)`: tóm tắt hội thoại cũ thành 3-5 câu mang tiền tố `[Tóm tắt hội thoại trước]: ...`.
  - `create_compaction_diff(messages, keep_recent=6)`: tạo diff RemoveMessage và SystemMessage nén để persist vào state LangGraph.
  - `compress_tool_result(raw_result, query, max_tokens=300)`: nén bảng SQL hoặc tài liệu VMS dài trước khi đưa vào context.
  - `reinject_instructions(messages, instructions)`: tái chèn quy tắc cốt lõi ở cuối prompt chống instruction fade-out (`[Nhắc lại chỉ dẫn]: ...`).
  - `latest_human_query(messages)` (`_latest_human_query`): quét ngược tìm câu hỏi user/human gần nhất cho tool retrieval / memory recall.
  - `detect_repetition(messages, window=4)` (`_detect_repetition`): circuit breaker phát hiện và ngắt vòng lặp tool call lặp lại liên tiếp.
- [x] **Short-Term Checkpointer (`src/memory/shortterm.py`)**:
  - Triển khai `get_checkpointer()`: cung cấp checkpointer phiên cho LangGraph, hỗ trợ fallback sang `MemorySaver()` trong RAM.
- [x] **TTL Response Cache (`src/memory/ttl_cache.py`)**:
  - Triển khai `make_cache_key(question, route)` băm SHA-256 chuẩn hóa.
  - Triển khai `get_ttl_cached(key)` và `set_ttl_cached(key, data, ttl=300)` thread-safe với `threading.Lock()`.
  - Triển khai `cleanup_expired()` và `get_cache_size()` dọn dẹp và theo dõi cache.
- [x] **Fact Extraction (`src/memory/extract.py`)**:
  - Triển khai `_heuristic_extract(question)` regex tiếng Việt (tên, vai trò, camera phụ trách, lưu ý).
  - Triển khai `extract_and_store_memory(user_id, question, answer)`: gọi LLM trích xuất fact cuối lượt và lưu vào PostgreSQL.
  - Triển khai `extract_from_messages(user_id, messages)` quét trực tiếp lịch sử tin nhắn và `memory_detail_includes_answer` lọc số liệu realtime.

**Done khi:** Toàn bộ 5 module backend trong `src/memory/` hoàn thiện, độc lập, có thể test unit test không phụ thuộc lẫn nhau.

---

## Phase 4 — Connect UI to data

- [x] **Tích hợp vào Luồng Agent Graph (`src/agent/graph.py`)**:
  - Thêm node `recall_memory_node` ở đầu graph: lấy facts của `user_id` từ PostgreSQL và nạp vào system prompt (`Thông tin đã biết về user:\n- ...`).
  - Áp dụng `context.sliding_window` và `context.reinject_instructions` trước khi gọi mô hình.
  - Áp dụng `context.compress_tool_result` nén kết quả bảng SQL hoặc Docs dài trước khi trả về graph state.
  - Thêm node `extract_memory_node` ở cuối graph: trích xuất thông tin mới và lưu vào PostgreSQL.
- [x] **Tích hợp TTL Cache vào Router/Orchestrator**:
  - Kiểm tra TTL Cache trước khi thực thi graph: nếu Cache Hit, trả về ngay câu trả lời kèm cờ `cache_hit: true`.
  - Nếu Cache Miss: chạy graph, nhận kết quả và lưu vào TTL Cache với hạn 300s.
- [x] **API Endpoint Quản lý Memory (`src/main.py`)**:
  - Bổ sung endpoint `DELETE /api/memory?user_id=...` để frontend gọi khi người dùng bấm nút Reset Memory.
  - Bổ sung endpoint `GET /api/memory?user_id=...` để frontend hiển thị các facts hiện tại của user.
- [x] **Kết nối Frontend (`frontend/app.js`)**:
  - Ghép nút Reset Memory gọi API `DELETE /api/memory`.
  - Hiển thị badge `⚡ Cache Hit` khi payload phản hồi có `cache_hit: true`.

**Done khi:** Giao diện frontend và backend kết nối thông suốt, luồng tương tác thực hiện đầy đủ vòng đời memory.

---

## Phase 5 — Validation and error states

- [x] **Kiểm thử Graceful Degradation (DB Offline)**:
  - Giả lập ngắt kết nối PostgreSQL (đổi `DB_HOST=invalid`): kiểm tra toàn bộ ứng dụng vẫn phản hồi bình thường nhờ fallback in-memory, log warning nhẹ, không trả về lỗi HTTP 500.
- [x] **Kiểm thử Cô lập dữ liệu (User Isolation)**:
  - Tạo 2 phiên chat với 2 `user_id` khác nhau: xác nhận thông tin của User A không bao giờ xuất hiện trong context của User B.
- [x] **Kiểm thử Ngưỡng nén 40% & Tool Compression**:
  - Kiểm tra khi ngữ cảnh vượt 40% window, hệ thống tự động sinh `[Tóm tắt hội thoại trước]: ...`.
  - Kiểm tra bảng SQL dài trên 300 tokens được nén cô đọng trước khi sinh câu trả lời.
- [x] **Kiểm thử TTL Cache Expiration**:
  - Kiểm tra câu hỏi thứ 2 trong vòng 300s trả về ngay lập tức (< 5ms); sau 300s tự động hết hạn và gọi lại pipeline thông thường.

**Done khi:** Toàn bộ các trạng thái biên, lỗi mất kết nối và logic bảo mật dữ liệu được kiểm thử chặt chẽ, không có lỗi tiềm ẩn.

---

## Phase 6 — Local run instructions

- [x] Cập nhật file `.env.example`:
  - Khai báo đầy đủ các biến cấu hình cho Memory:
    ```env
    # ── Memory & Context Engineering (v9) ───────────────────────────────────
    MEMORY_ENABLED=true
    MEMORY_SHORT_TERM_ENABLED=true
    MEMORY_LONG_TERM_ENABLED=true
    MEMORY_TTL_SECONDS=300
    MEMORY_MAX_MESSAGES=20
    MEMORY_COMPACT_THRESHOLD=0.40
    ```
- [x] Cập nhật file `README.md`:
  - Thêm tài liệu hướng dẫn chi tiết các lệnh chạy local trên máy (không dùng Docker và dùng Docker).
  - Cung cấp danh sách các lệnh chạy unit test cho gói Memory:
```bash
    PYTHONPATH=. pytest tests/test_product_memory_context.py tests/test_product_memory_cache.py tests/test_product_memory_postgres.py -v
    ```

**Done khi:** Tài liệu hướng dẫn rõ ràng, bất kỳ developer nào cũng có thể tự cài đặt, chạy và test app trên máy cá nhân.

## Phase 7 — ngrok demo setup

- [x] Hướng dẫn cài đặt và cấu hình ngrok expose ứng dụng an toàn ra internet:
  - Hướng dẫn cài đặt ngrok trên Windows, macOS, Linux, thiết lập Authtoken và cấu hình mở tunnel ra internet cho cổng dịch vụ (`8000` cho FastAPI backend hoặc `8080` cho Docker frontend).
  - Cung cấp script tự động chạy ngrok (`scripts/run_ngrok_demo.sh` và `scripts/run_ngrok_demo.bat`) kèm hỗ trợ truyền cổng linh hoạt và xử lý host header rewrite.
  - Cập nhật tài liệu hướng dẫn vào `README.md` (Mục 6: Expose Internet qua ngrok).
- [x] Kịch bản demo kiểm chứng độ bền vững của Memory & Context Engineering v9:
  - Xây dựng tài liệu hướng dẫn kịch bản demo 7 bước tương tác trực tiếp trên web UI theo chuẩn `specs/test-plan.md` mục 3 (Nhận diện danh tính, Short-Term memory, Long-Term persistence qua reload/tab mới, Sliding Window 10+ turns, Tool result compression, TTL Cache hit < 5ms, và Graceful degradation khi DB offline).
  - Cung cấp script kiểm chứng tự động toàn bộ 7 bước kịch bản demo `scripts/verify_memory_demo.py` để xác minh 100% độ tin cậy của luồng demo trước khi thuyết trình.

**Done khi:** Ứng dụng có thể expose an toàn ra internet qua ngrok và kịch bản demo hoạt động hoàn hảo 100%.

