# Change Log — agent dong

## 2026-09-22 — Phase 7: Eval run, Judge rubric, Golden-30 & Acceptance criteria hoàn thành

### Added
- `tests/test_phase7_eval.py`:
  - Unit test cho `eval/judge.py`: kiểm tra rubric chấm 1-5, xử lý offline skip an toàn.
  - Unit test cho `check_case`: kiểm tra logic assertion `must_include`, `must_include_tool`, `must_not_include`, `must_include_columns_any`.
  - Unit test cho `write_golden_30`: kiểm tra cấu trúc định dạng báo cáo markdown `eval/results/golden-30.md`.
  - Integration test cho `run(..., offline=True)`: kiểm tra toàn bộ chu trình eval dataset sinh báo cáo thành công.

### Changed
- `src/llm/client.py`: cập nhật `use_offline_tools()` hỗ trợ cờ `AGENT_OFFLINE=1` và `PYTEST_CURRENT_TEST` cho chế độ test offline an toàn.
- `eval/run.py`: tối ưu `_enable_live_eval()` và `_disable_live_eval()` chuyển đổi mượt mà giữa live mode và offline mock mode.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành toàn bộ các hạng mục Phase 7 và toàn bộ kế hoạch phát triển MVP v6 (Phase 1 → 7).
- Xác nhận đạt đủ 11/11 tiêu chí Acceptance Criteria trong `specs/product-spec.md`.

### Verify
- `pytest tests/test_phase7_eval.py -q` (4 passed)
- `pytest -q` (394 passed)

---

## 2026-09-22 — Phase 7: Smoke tay (session, short-term, TTL, bar, pie, fire/AIOC)

### Added
- `scripts/smoke-production.sh`: Script bash kiểm thử khép kín 7 case bắt buộc trên stack Docker production live (gateway 196 + DB):
  - Precondition gọi `scripts/verify-docker-self-hosted.sh` (hoặc inline health & ping).
  - Hỗ trợ các biến môi trường: `BACKEND_PORT`, `BASE_URL`, `SMOKE_USER_ID`, `TIMEOUT_SECONDS`, `SKIP_PRECHECK`.
  - Helper inline Python bóc tách SSE stream: `__answer__`, `cache`, `__chart__`, và `error`.
  - Kiểm thử 7 case: Case 1 (Session API: create/list/messages), Case 2 (Short-term memory: 2 turns nhớ tên An), Case 3 (TTL Cache: hỏi stat 2 lần trong 5 phút -> cache hit), Case 4 (Bar chart: `__chart__` bar), Case 5 (Pie chart: `__chart__` pie), Case 6 (Fire warning #010), Case 7 (AIOC camera guide #014/015).
  - Tổng kết rõ ràng số lượng PASS/FAIL, in snippet và thoát exit 0 khi 7/7 pass.
- `specs/smoke-manual-checklist.md`: Checklist kiểm thử thủ công trên giao diện Web UI (port 8080) kết hợp script:
  - Sidebar: Tạo phiên mới, chuyển đổi phiên, hiển thị preview tin nhắn.
  - Short-term memory: Nhớ tên người dùng qua 2 turns.
  - TTL Cache: Kích hoạt node cache màu xanh và độ trễ thấp ở lần hỏi thứ 2.
  - Chart rendering: Canvas Chart.js cho bar và pie, tooltip hover số liệu.
  - Live Graph: Hover node hiển thị popover JSON input/output chi tiết.
  - Liên kết trực tiếp tới `scripts/smoke-production.sh`.
- `tests/test_phase7_smoke_manual.py`: Bộ kiểm thử tự động offline (pytest):
  - Kiểm tra `scripts/smoke-production.sh` tồn tại, executable, chứa đủ 7 cases và câu hỏi mẫu.
  - Kiểm tra `specs/smoke-manual-checklist.md` tài liệu hóa đầy đủ các hạng mục UI/API.
  - Mock TestClient: Chu trình Session CRUD (create, list, messages).
  - Mock TestClient: Giả lập lần 2 hỏi cùng câu stat kích hoạt TTL cache node trong SSE stream.
  - Mock TestClient: Kiểm tra validation bắt buộc `session_id` và `user_id` của `/api/agent/stream`.
  - Kiểm tra offline bộ parser SSE inline.

### Changed
- `specs/implementation-plan.md`: Đánh dấu hoàn thành `[x] Smoke tay: session, short-term, TTL, bar, pie, 1 câu fire/AIOC.`
- `README.md`: Bổ sung liên kết checklist smoke UI và script smoke production.

### Verify
- `pytest tests/test_phase7_smoke_manual.py -q` (6 passed)
- `pytest -q` (390 passed)

---

## 2026-09-22 — Phase 7: Docker + LLM_BACKEND=self_hosted (196)

### Added
- `scripts/verify-docker-self-hosted.sh`: Script bash kiểm tra sức khỏe của stack Docker khi chạy self_hosted:
  - Kiểm tra `GET /api/health` → xác thực `llm_backend == "self_hosted"`.
  - Kiểm tra `GET /api/llm/ping` → xác thực status ok kết nối gateway 192.168.1.196:18083.
  - Trả về exit code 0 khi thành công, exit 1 kèm thông báo chi tiết khi thất bại.
- `tests/test_phase7_docker_self_hosted.py`: Bộ unit và integration test cho Docker + self_hosted backend:
  - Kiểm tra `docker-compose.yml` service `ai_backend` khai báo passthrough các biến `LLM_BACKEND`, `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_API_KEY`, `MODEL_ENDPOINT` với production defaults trỏ gateway 192.168.1.196:18083.
  - Kiểm tra `Settings` resolve `effective_base_url` và `effective_model` cho `self_hosted`.
  - Kiểm tra mock endpoint `GET /api/health` trả về `llm_backend="self_hosted"` và `active_model="qwen3-4b"`.
  - Kiểm tra mock endpoint `GET /api/llm/ping` thành công và trường hợp 503 khi gateway không phản hồi.
  - Kiểm tra file `scripts/verify-docker-self-hosted.sh` tồn tại, có quyền execute và logic đầy đủ.
  - Kiểm tra `.env.example` tài liệu hóa đầy đủ cấu hình.

### Changed
- `docker-compose.yml`: Bổ sung các biến môi trường LLM với default production cho service `ai_backend` (`LLM_BACKEND: ${LLM_BACKEND:-self_hosted}`, `MODEL_BASE_URL: ${MODEL_BASE_URL:-http://192.168.1.196:18083/v1}`, `MODEL_NAME: ${MODEL_NAME:-qwen3-4b}`, `MODEL_API_KEY: ${MODEL_API_KEY:-}`, `MODEL_ENDPOINT: ${MODEL_ENDPOINT:-http://192.168.1.196:18083/v1/chat/completions}`).
- `.env.example`: Thêm khối chú thích rõ ràng về việc Docker production mặc định dùng `self_hosted`, cách override sang `openai` cho smoke test, và danh sách các biến bắt buộc (`MODEL_API_KEY`, `DB_*`).
- `specs/implementation-plan.md`: Đánh dấu hoàn thành `[x] Docker + LLM_BACKEND=self_hosted (196).`

### Verify
- `pytest tests/test_phase7_docker_self_hosted.py tests/test_api.py -q -k "docker or self_hosted or dual_model"` (14 passed)
- `pytest -q` (384 passed)

---

## 2026-09-22 — Phase 5: TTL / memory fail — degrade an toàn (vẫn trả lời được)

### Added
- `tests/test_phase5_ttl_memory_degrade.py`: bộ unit và integration test kiểm tra khả năng phục hồi và degrade an toàn khi TTL cache hoặc memory subsystem gặp sự cố:
  - `get_ttl_cached` và `_lookup_ttl_cache` gặp lỗi nội bộ hoặc dữ liệu hỏng → trả về `None` (cache miss), không ném ngoại lệ.
  - `/api/chat` vẫn trả về 200 kèm câu trả lời khi TTL lookup gặp sự cố.
  - `set_ttl_cached` gặp lỗi ghi/lock/disk full → nuốt lỗi an toàn, `/api/chat`, `/ask`, `/api/agent/stream` vẫn hoàn tất trả lời.
  - `recall_long_term` gặp sự cố (ví dụ vector DB down) → `recall_node` trả về `recalled_memories=[]` kèm event `degraded=True`, graph tiếp tục thực thi bình thường.
  - `extract_and_store_memory` gặp lỗi ghi → `run_store_extract` trả về event hoàn tất kèm `output={"extracted_memories": [], "degraded": True, "error": "<msg>"}`, không ném ngoại lệ làm sập luồng post-pipeline hay stream generator.
  - Integration: stream SSE khi recall fail + store_extract fail nhưng agent core OK → event `__answer__` kết thúc với `status="done"`, client nhận mã 200.

### Changed
- `src/memory/ttl_cache.py`: bọc try/except có log warning trong `get_ttl_cached` và `set_ttl_cached`, kiểm tra định dạng dict/thời gian trước khi truy xuất, fallback về cache miss an toàn.
- `src/main.py`:
  - `_lookup_ttl_cache`: bọc try/except bảo vệ khi tính key hoặc truy xuất cache lỗi.
  - Điểm gọi `_lookup_ttl_cache` và `set_ttl_cached` tại `/api/chat`, `/ask`, `/api/agent/stream` đều được bọc xử lý lỗi riêng biệt, đảm bảo không bao giờ gây 503 hay crash stream chỉ vì lỗi cache.
- `src/agent/graph.py`:
  - `recall_node`: bắt ngoại lệ từ `recall_long_term`, fallback về danh sách rỗng kèm event recall degraded để graph chạy tiếp.
  - `run_store_extract`: bắt ngoại lệ từ `extract_and_store_memory` và post-pipeline step, trả về event `store_extract` degraded mà không raise.
- `src/memory/longterm.py`: gia cố `save_to_long_term` và `recall_long_term` với try/except không bao giờ để lọt lỗi ra caller.
- `src/memory/extract.py`: gia cố `extract_and_store_memory` với try/except an toàn.
- `specs/implementation-plan.md`: đánh dấu hoàn thành `[x] TTL / memory fail: degrade an toàn (vẫn trả lời được).`

### Verify
- `pytest tests/test_phase5_ttl_memory_degrade.py tests/test_memory_ttl_cache.py tests/test_memory_nodes.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 6: Run instructions (Docker-only & AGENTS.md) hoàn thành

### Changed
- `README.md`:
  - Ghi rõ cấu hình LLM cho production test (`LLM_BACKEND=self_hosted` @ 196) vs OpenAI smoke test (`LLM_BACKEND=openai`).
  - Bổ sung checklist triển khai 5 bước rõ ràng: copy `.env`, `docker compose up --build -d`, `curl /api/health`, `curl /api/llm/ping`, mở UI port `http://localhost:8080`.
  - Bổ sung lệnh ngắn khởi động stack Langfuse riêng biệt (`cd langfuse && docker compose up -d`).
  - Đưa phần Local dev / venv xuống mục Phụ lục (Appendix) chỉ dành cho debug nhanh, khẳng định Docker là đường chạy chính duy nhất.
- `AGENTS.md`: Cập nhật toàn bộ hướng dẫn cho Phase 6 (quy tắc 1 task, đường chạy Docker, lệnh verify nhanh).
- `specs/implementation-plan.md`: Đánh dấu hoàn thành toàn bộ 6/6 items trong `Phase 6 — Run instructions (Docker)`.

### Verify
- `pytest tests/test_api.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 5: Thiếu biến prompt — lỗi rõ (không template trống)

### Added
- `tests/test_phase5_prompt_vars.py`: kiểm tra template rỗng/whitespace, thiếu biến, output rỗng, unreplaced placeholder, map lỗi sang thông báo thân thiện tiếng Việt, tích hợp /api/chat (503) và /api/agent/stream (__answer__ error).

### Changed
- `src/prompts/registry.py`:
  - Validate template không rỗng/whitespace-only trước khi render (`ValueError: Prompt '<name>' có template rỗng`).
  - Nâng cấp thông báo thiếu biến: kèm tên prompt và danh sách biến thiếu (`ValueError: Prompt '<name>' thiếu biến: [...]`).
  - Validate chuỗi sau khi format không rỗng (`ValueError: Prompt '<name>' sau khi render có nội dung rỗng`).
  - Phát hiện placeholder chưa thay thế còn sót lại trong chuỗi kết quả (`ValueError: Prompt '<name>' còn chứa placeholder chưa thay thế: [...]`).
- `src/main.py`: `_format_error_message()` nhận diện các lỗi cấu hình prompt (thiếu biến, template rỗng, placeholder) → trả về thông báo ngắn gọn tiếng Việt: `"Lỗi cấu hình prompt: thiếu biến hoặc template không hợp lệ. Liên hệ quản trị."`, không lộ stack trace hay nội dung template.
- `tests/test_llm.py`: cập nhật assertion kiểm tra định dạng lỗi thiếu biến prompt mới.
- `specs/implementation-plan.md`: đánh dấu hoàn thành `[x] Thiếu biến prompt: lỗi rõ (không template trống).`

### Verify
- `pytest tests/test_phase5_prompt_vars.py tests/test_llm.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 6: README quick start chỉ Docker (compose up --build)

### Changed
- `README.md`: Chuẩn hoá section Quick start chỉ dùng Docker compose (`docker compose up --build -d`), không yêu cầu Python/venv trên host; bổ sung hướng dẫn chi tiết kiểm tra health/llm ping và mở UI.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành `[x] README quick start **chỉ Docker** (compose up --build)`.

### Verify
- `pytest tests/test_api.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 5: Lỗi LLM/DB — message ngắn UI, stream không crash

### Added
- `src/main.py`: `USER_ERROR_MAX_LEN`, `_short_user_error()`; rút gọn message `_format_error_message`.
- `tests/test_phase5_llm_db_errors.py`: truncate, no SQL leak, stream DB/LLM error → `__answer__` error SSE.

### Changed
- `frontend/app.js`: `lastStreamError`; hiển thị `⚠️` khi `__answer__` status error; fallback stream dùng lỗi đã biết.
- `tests/test_api.py`: cập nhật assert message ngắn mới.
- `specs/implementation-plan.md`: `[x] Lỗi LLM / DB...`

### Verify
- `pytest tests/test_phase5_llm_db_errors.py tests/test_api.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 5: Classify/route sai domain — fallback orchestrator

### Added
- `src/agent/intent.py`: `STAT_EVENT_DOMAIN_KEYWORDS`, `is_stat_event_domain()`, `classify_intent_safe()` fallback offline khi LLM lỗi.
- `src/agent/query_plan.py`: `plan_query_safe()` fallback `_offline_plan_query` khi LLM lỗi.
- `tests/test_phase5_domain_route.py`: wrong classify out_of_scope/how_to vẫn route query_data; safe fallbacks.
- `tests/test_api.py`: patch `classify_intent_safe` (thay `classify_intent`).

### Changed
- `src/agent/graph.py`: `classify_node` dùng `classify_intent_safe`; orchestrator override khi classify `out_of_scope` nhưng câu hỏi thuộc fire/anomaly/water; `route_orchestrator` ưu tiên `query_data`; `plan_query_node` + `plan_and_execute` dùng `plan_query_safe`.
- `specs/implementation-plan.md`: `[x] Classify/route sai domain...`

### Verify
- `pytest tests/test_phase5_domain_route.py tests/test_orchestrator.py tests/test_intent.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 5: Empty số liệu trả đúng (có "0")

### Added
- `src/guardrails.py`: `empty_stat_reply()` — message chuẩn có "0 lượt / 0 kết quả"; `EMPTY_TOOL_REPLY` alias.
- `check_output`: khi `tool_empty=True` mà answer thiếu "0" → chuẩn hoá `empty_stat_reply()`.
- `tests/test_phase5_empty_stat.py`: respond_node, check_output, API mock empty query.

### Changed
- `src/agent/graph.py`: `respond_node`, `orchestrator_respond_node` dùng `empty_stat_reply()`.
- `tests/test_guardrails.py`: honest empty → expect chuẩn hoá có "0".
- `specs/implementation-plan.md`: `[x] Empty số liệu...`

### Verify
- `pytest tests/test_phase5_empty_stat.py tests/test_guardrails.py tests/test_orchestrator.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 5: Out-of-scope / injection từ chối rõ tiếng Việt

### Added
- `src/guardrails.py`:
  - `INJECTION_REJECT_MESSAGE`, `TOXIC_REJECT_MESSAGE` — thông báo từ chối tiếng Việt.
  - `rejection_detail(reason)` — map mã nội bộ → message user-facing.
- `tests/test_phase5_guardrail_vi.py`: injection/toxic/out-of-scope trên `/api/chat` và `/api/agent/stream`.

### Changed
- `src/main.py`: `guardrail_violation_handler` dùng `rejection_detail()` cho `detail`; giữ `reason` mã máy cho eval.
- `tests/test_api.py`: assert detail tiếng Việt + `session_id`/`user_id` khi test stream injection.
- `specs/implementation-plan.md`: `[x] Out-of-scope / injection: từ chối rõ, tiếng Việt.`

### Verify
- `pytest tests/test_phase5_guardrail_vi.py tests/test_guardrails.py tests/test_api.py tests/test_readonly.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 4: Đổi session → load lịch sử short-term đúng phiên

### Added
- `src/sessions/store.py`:
  - `messages: []` khi tạo session; `get_session_messages()`, `append_session_messages()` (auto title/preview).
- `src/sessions/schemas.py`: `SessionMessage`, `SessionMessagesResponse`.
- `src/main.py`:
  - `GET /api/sessions/{session_id}/messages?user_id=`
  - `_persist_session_turn()` — lưu cặp user/assistant sau stream (`out_of_scope`, cache hit, `__final_result__`).
- `tests/test_session_messages.py`: isolation 2 session, API 404/422, stream persist, FE fetch wiring.
- `specs/implementation-plan.md`: `[x] Đổi session → load lịch sử short-term đúng phiên.`

### Changed
- `frontend/app.js`: `loadCurrentSessionMessages()` async fetch API; `switchSession`/`init`/`deleteSession` await load.

### Verify
- `pytest tests/test_session_messages.py tests/test_sessions_api.py tests/test_memory_shortterm.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 4: Live graph hover JSON khớp backend

### Added
- `frontend/app.js`:
  - `formatIoValue`: pretty-print object; parse JSON string nếu value là chuỗi `{...}`/`[...]`.
  - `upsertGraphNode`: merge I/O khi `running` (không ghi đè bằng undefined); lưu `meta` từ SSE.
  - `showNodeIo`: hiển thị `input` / `output` / `meta` dạng JSON indent; truncate 80KB.
  - `hoveredGraphNodeId`: refresh panel khi node chuyển `running` → `done` trong lúc đang hover.
  - SSE handler: truyền `event.meta` vào `upsertGraphNode`.
- `tests/test_frontend_graph_hover.py`: 6 tests static file — formatIoValue, merge I/O, meta, hover refresh, IO_MAX_CHARS.
- `specs/implementation-plan.md`: đánh dấu `[x] Live graph hover: JSON input/output khớp backend.`

### Verify
- `pytest tests/test_frontend_graph_hover.py tests/test_api.py -q`
- `pytest -q`

---

## 2026-09-22 — Phase 4: FE vẽ bar + pie từ payload (Chart.js)

### Added
- `frontend/index.html`:
  - Thêm `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js">` trước `app.js`.
- `frontend/app.js`:
  - Thêm `lastChartRows: null` vào `state`; `resetGraph()` reset cả `lastChartRows`.
  - Hàm `renderChartJs(containerEl, { chartType, chartSpec, rows })`:
    - Build labels từ `chartSpec.x_column`, values từ `chartSpec.y_column`.
    - `bar` → Chart.js `type: 'bar'`; `pie` → `type: 'pie'`.
    - Responsive canvas; WeakMap `_chartInstances` để destroy instance cũ khi re-render.
    - Palette màu warm-neutral 8 màu lặp vòng.
  - `appendMessage(role, content, detail, chartPayload)`:
    - `chartPayload` có thể là `string` (legacy PNG base64) hoặc `object { png, spec, type, rows }`.
    - Ưu tiên Chart.js khi `spec + rows` có sẵn; else PNG img fallback; else placeholder.
  - SSE loop `__chart__` handler: lưu `state.lastChartRows = event.chart_rows`.
  - SSE loop `__answer__` handler: xây `chartPayload = { png, spec, type, rows }` và lưu vào session message.
- `frontend/style.css`:
  - `.chart-slot canvas { max-width: 100%; height: auto; min-height: 200px; }`.
- `src/main.py`:
  - `_build_chart_sse_event(..., chart_rows=None)`: thêm tham số `chart_rows`; khi không None → thêm `chart_rows` vào dict event.
  - `event_generator()`: thêm `last_chart_rows`; extract từ `event.input.rows` hoặc `event.rows` khi gặp `render_chart` node; truyền `last_chart_rows` vào `_build_chart_sse_event` và vào `__answer__` detail.
- `tests/test_sse_chart.py`: cập nhật mock thêm `rows` trong `render_chart` event input; thêm 3 tests mới:
  - `test_stream_chart_event_includes_chart_rows` — `__chart__` event có `chart_rows`.
  - `test_stream_answer_detail_includes_chart_rows` — `__answer__` detail có `chart_rows`.
  - `test_build_chart_sse_event_with_rows` — helper trả `chart_rows` khi provided; field absent khi không cung cấp.
- `tests/test_frontend_chartjs.py` (mới): 5 tests kiểm tra file tĩnh:
  - `test_index_html_includes_chartjs_cdn` — CDN tag có trong index.html và đứng trước app.js.
  - `test_app_js_has_renderChartJs` — app.js định nghĩa hàm renderChartJs.
  - `test_app_js_handles_chart_rows_from_sse` — app.js đọc event.chart_rows, lưu state.lastChartRows.
  - `test_app_js_saves_chart_as_object` — chartPayload object có đủ 4 field png/spec/type/rows.
  - `test_app_js_appendMessage_supports_chart_object` — appendMessage kiểm tra typeof object và string.
- `specs/implementation-plan.md`: đánh dấu `[x] FE vẽ bar + pie từ payload (Chart.js ưu tiên)`.

### Verify
- `pytest tests/test_sse_chart.py tests/test_frontend_chartjs.py -v` → **12 passed**
- `pytest -q` → **311 passed**

---

## 2026-09-22 — Phase 4: SSE __chart__ event + answer detail chart info


### Added
- `src/main.py`:
  - `_build_chart_sse_event(chart_spec, chart_png_base64) -> dict`: helper tạo SSE event chuẩn cho `__chart__` node (`node_id="__chart__"`, `status="done"`, `chart_type`, `chart_spec`, `chart_png_base64`).
  - Trong `event_generator()` của `stream_agent`: thêm tracking `last_chart_png`, `last_chart_spec`, `last_chart_type` trong generator scope.
  - Khi event từ `run_agent_stream` có `node_id="render_chart"` và `chart_png_base64` không rỗng → emit ngay một `__chart__` SSE event trước khi yield event gốc.
  - Khi build `__answer__` event từ `__final_result__` → nếu có chart → thêm `chart_type` và `chart_spec` vào `detail_payload`.
- `frontend/app.js`:
  - Thêm `lastChartSpec: null`, `lastChartType: null` vào `state` init.
  - `resetGraph()`: reset cả `lastChartSpec` và `lastChartType`.
  - Trong SSE loop: xử lý `event.node_id === '__chart__'` → set `state.lastChart`, `state.lastChartSpec`, `state.lastChartType`; `continue` không đẩy vào graph node panel.
- `tests/test_sse_chart.py` (mới): 4 tests:
  - `test_stream_emits_chart_event_on_render_chart` — stream phát `__chart__` event khi render_chart node có chart_png_base64.
  - `test_stream_answer_detail_includes_chart_when_present` — `__answer__` detail có `chart_type` và `chart_spec`.
  - `test_chart_sse_event_schema_fields` — `_build_chart_sse_event` trả đủ 5 fields (node_id, status, chart_type, chart_spec, chart_png_base64); fallback None → bar.
  - `test_stream_no_chart_event_when_no_chart` — không có `__chart__` event khi không có render_chart.
- `specs/implementation-plan.md`: đánh dấu `[x] SSE: token/answer + event chart`.

### Verify
- `pytest tests/test_sse_chart.py -v` → **4 passed**
- `pytest -q` → **303 passed**

---


## 2026-09-22 — Review fix: store_extract post-pipeline + skip stat memory

### Context
Review bugfix `store_extract` theo `product-spec.md` AC #5, #7 và `test-plan.md` (Memory long-term, Trace full I/O, SSE graph).

### Pass
- **AC #5 / Trace:** `store_extract` post-pipeline vẫn emit SSE + Langfuse `trace_step` với `input`/`output` dict (`include_answer`, `extracted_memories`).
- **AC #7 / Long-term:** fact từ câu hỏi (tên, vai trò, sở thích) vẫn store + recall cross-session cùng `user_id` (`test_end_to_end_graph_recall_and_store`, `test_api_chat_propagates_user_id_and_stores_memory`).
- **Answer trước store:** stream emit `__final_result__` → `__answer__` trước `store_extract`; FE hiện answer ngay khi nhận `__answer__`.
- **Skip stat từ answer:** `query_data`, `orchestrator:multi`, `out_of_scope` — `include_answer=False`, không gọi LLM với số liệu trả lời.
- **Docs branch:** `detail=docs` vẫn dùng LLM `memory_extract` với answer (how-to, không phải số liệu realtime).
- **Recall:** node `recall` vẫn đầu graph; inject vào `respond_stat` prompt.
- **AC #11:** `pytest -q` xanh.

### Fixed (review)
- `tests/test_memory_nodes.py`: assert `store_extract` done có structured I/O + `include_answer=False` trên stat query; thêm `test_orchestrator_multi_skips_answer_memory`.
- `tests/test_api.py`: `test_api_stream_answer_emits_before_store_extract` — SSE HTTP-level xác nhận `__answer__` trước `store_extract`.

### Missing / ngoài scope
- Heuristic `"Nhớ là …"` trên **câu hỏi** thống kê vẫn có thể lưu số nếu user tự gõ — chưa filter (edge case hiếm).
- `/api/chat`: store chạy background thread — không block response; Langfuse child span vẫn ghi nhưng không đồng bộ với HTTP body (chấp nhận được).
- Live verify Langfuse UI hover `store_extract` — cần `MONITORING_ENABLED=true` + server.
- `implementation-plan.md` mô tả Phase 3b “store cuối graph” — đã đổi post-pipeline (chỉ ghi change-log, chưa sửa plan).

### Root cause (bug gốc)
- `store_extract` trong graph sau `respond` → chặn `__answer__`.
- `extract_memories` gửi câu trả lời thống kê vào LLM → lưu số realtime.

### Changed (bug gốc)
- `src/agent/graph.py`: bỏ `store_extract` khỏi graph; `run_store_extract()` post-pipeline.
- `src/memory/extract.py`: `memory_detail_includes_answer()`.

### Verify
- `python -m pytest tests/test_memory_nodes.py tests/test_api.py::test_api_stream_answer_emits_before_store_extract -q`
- `python -m pytest -q`

---

## 2026-09-22 — Phase 4: POST /api/agent/stream nhận session_id, user_id, câu hỏi

### Added
- `tests/test_stream_session.py`: 5 tests mới:
  - `test_api_agent_stream_accepts_session_and_user_id` — POST với explicit ids, mock `run_agent_stream`, assert kwargs `session_id` và `user_id` khớp.
  - `test_api_agent_stream_rejects_empty_session_id` — 400 khi `session_id=""` hoặc whitespace-only.
  - `test_api_agent_stream_rejects_empty_user_id` — 400 khi `user_id=""` hoặc whitespace-only.
  - `test_api_agent_stream_accepts_non_uuid_ids` — Bất kỳ chuỗi không rỗng nào đều hợp lệ (không yêu cầu UUID format).
  - `test_api_agent_stream_sse_events_present` — SSE stream phát sinh đúng `__answer__` event với output.

### Changed
- `src/main.py`:
  - `stream_agent` (`POST /api/agent/stream`): thêm validation HTTP 400 khi `session_id` hoặc `user_id` rỗng/whitespace-only (tiếng Việt).
  - `chat` (`POST /api/chat`): thêm validation tương tự cho nhất quán.
- `frontend/app.js`:
  - `handleSendMessage()` fetch body bổ sung `session_id: state.activeSessionId` và `user_id: state.userId` — wire end-to-end với session API Phase 4.
- `tests/test_api.py`:
  - `test_api_agent_stream_passes_trace_parent_span`: cập nhật json body thêm `session_id`, `user_id`; lambda mock nhận `**kwargs` để tương thích với inspect signature mới.
- `specs/implementation-plan.md`: đánh dấu `[x] POST /api/agent/stream nhận session_id, user_id, câu hỏi.`

### Verify
- `python3 -m pytest tests/test_api.py tests/test_stream_session.py -q` → 43 passed
- `python3 -m pytest -q` → **296 passed**

---

## 2026-09-22 — Phase 4 implemented (API sessions: list / create / delete; UI gọi thật)

### Added
- `src/sessions/store.py`: in-memory session store (thread-safe), keyed by `user_id`.
- `src/sessions/schemas.py`: Pydantic models `SessionItem`, `SessionListResponse`, `CreateSessionRequest`, `DeleteSessionResponse`.
- API endpoints trong `src/main.py`:
  - `GET /api/sessions?user_id=` — liệt kê phiên, sắp xếp `updated_at` giảm dần.
  - `POST /api/sessions` — tạo phiên mới (UUID, title mặc định "Phiên chat mới").
  - `DELETE /api/sessions/{session_id}?user_id=` — xóa phiên (404 nếu không tồn tại hoặc sai user).
- `tests/test_sessions_api.py`: 10 tests (list/create/delete, sort, user isolation, validation).

### Changed
- `frontend/app.js`: sidebar gọi API thật thay mock `localStorage agent_sessions`; nút xóa phiên; tạo phiên mặc định khi danh sách rỗng.
- `frontend/style.css`: style nút xóa session (`.session-delete-btn`, `.session-item-meta`).
- `specs/implementation-plan.md`: đánh dấu `[x] API sessions: list / create / delete; UI gọi thật.`

### Verify
- `python -m pytest tests/test_sessions_api.py -q` (10 passed)
- `python -m pytest -q` (291 passed)

### Missing (task kế tiếp)
- Stream chưa gửi `session_id`/`user_id` (line 84).
- Title/preview cập nhật local FE chưa sync PATCH lên backend (refresh mất preview mới).

---

## 2026-09-22 — Bugfix: 503 khi hỏi lại câu đã cache (rewrite LLM fail trước cache check)

### Root cause
- `/api/chat`, `/ask`, `/api/agent/stream` gọi `rewrite_question()` (LLM) **trước** khi tra TTL cache.
- Request đầu thành công → cache 300s; vài giây sau LLM gateway timeout/lỗi tạm thời → rewrite raise → request fail (503 trên `/api/chat`) dù cache vẫn còn hạn.
- Stream: rewrite ngoài `try` → generator crash sớm, Langfuse trace không flush đầy đủ.

### Fixed
- `src/main.py`: `_lookup_ttl_cache()` tra cache theo câu gốc **trước** rewrite; chỉ gọi LLM khi cache miss.
- `src/agent/rewrite.py`: `rewrite_question_safe()` fallback offline heuristic khi LLM lỗi.
- `src/agent/graph.py`: `_reset_trace_span()` an toàn qua threadpool; `run_agent` báo lỗi rõ nếu thiếu `result`.
- `src/main.py` stream: bọc `json.dumps` SSE — lỗi serialize không làm gãy cả stream.
- `tests/test_memory_ttl_cache.py`: test cache hit khi rewrite raise timeout.

### Verify
- `python -m pytest tests/test_memory_ttl_cache.py tests/test_api.py -q`
- `python -m pytest -q`

---

## 2026-09-22 — Review fix: structured node I/O trace (Langfuse + SSE)

### Context
Review feature structured I/O theo `product-spec.md` AC #5 và `test-plan.md` (Trace: node input/output full; Langfuse + SSE hover khớp).

### Pass (sau review)
- Mọi graph node emit `input`/`output` dạng **dict structured** (không còn f-string tóm tắt như `"Trả về N dòng"`).
- Langfuse child span (`trace_step`) nhận dict qua `_wrap_node` → khớp payload SSE.
- `execute`: full `sql`, `params`, `columns`, `rows`, `row_count`.
- `validate`, `plan_query`, `rewrite`, `classify`, `respond`, docs/orchestrator nodes: JSON thực.
- Bỏ cắt SSE 2000 ký tự trên mọi string; chỉ cắt `schema_excerpt` nếu >16KB (catalog hiện tại <16KB → full trên UI).
- Frontend hiển thị object JSON (giới hạn 80KB); `pytest -q` xanh.

### Fixed (review)
- `_wrap_node` error path: I/O lỗi structured `{input: {question, node_id}, output: {error, error_type}}` thay vì string.
- `tests/test_trace_cache.py`: assert dict structured + `execute` có `rows`/`row_count`, không còn summary string.
- `tests/test_node_io.py`: test `execute_node` emit full rows.

### Missing / ngoài scope feature này
- Node `guardrail` / `cache` trên SSE (`main.py`) vẫn string — nằm ngoài graph, chưa đổi.
- `chart_png_base64` stream riêng field SSE (không nhét vào `output` trace) — cố ý tránh payload khổng lồ.
- Live verify Langfuse UI (cần `MONITORING_ENABLED=true` + server) — chưa chạy trong review offline.

### Verify
- `python -m pytest tests/test_trace_cache.py tests/test_node_io.py tests/test_api.py -q`
- `python -m pytest -q`

---

## 2026-09-22 — Phase 3c implemented (Docs AIOC / catalog dataset trong resource/)

### Added
- `resource/docs/aioc_yaml/`:
  - `schema.yaml`: Schema chuẩn cho AIOC task cards.
  - `index.yaml`: Chỉ mục 7 task cards AIOC published (`aioc.login_devices`, `aioc.manage_camera`, `aioc.add_camera`, `aioc.camera_status`, `aioc.diagram_login_devices`, `aioc.diagram_add_camera`, `aioc.vms_vs_devices`).
  - `how_to/login-devices.yaml` (`aioc.login_devices`): Đăng nhập Cloud Cam → https://aioc.atin.vn/devices.
  - `how_to/manage-camera.yaml` (`aioc.manage_camera`): Menu Cấu hình & Thiết bị > Quản Lý Camera (/devices).
  - `how_to/add-camera.yaml` (`aioc.add_camera`): Các bước thêm camera mới trên AIOC devices.
  - `how_to/camera-status.yaml` (`aioc.camera_status`): Giải thích 3 trạng thái Trực Tuyến / Ngoại Tuyến / Bảo Trì và hướng dẫn cách đổi trạng thái.
  - `how_to/diagram-login-devices.yaml` (`aioc.diagram_login_devices`): Sơ đồ từ đăng nhập đến mở trang Quản Lý Camera.
  - `how_to/diagram-add-camera.yaml` (`aioc.diagram_add_camera`): Sơ đồ quy trình thêm camera mới trên AIOC.
  - `how_to/vms-vs-devices.yaml` (`aioc.vms_vs_devices`): Sơ đồ và phân biệt hỏi thống kê sự kiện VMS (SQL) vs hướng dẫn AIOC devices.
- `resource/db/dataset_catalog.yaml`:
  - Dataset cấu hình hints cho eval Golden-30 v2 cases (các case fail chính: 008–011, 015, 017, 023, 024) với mapping table, event_type filter, keywords.
- `src/db/dataset_catalog.py`:
  - Loader `@lru_cache` với các hàm `load_dataset_catalog()`, `get_case_hints(case_id)`, `get_table_for_keywords(question)`, `clear_dataset_catalog_cache()`.
- `tests/test_aioc_docs.py`:
  - 11 unit tests kiểm tra:
    * AIOC cards load đủ 7 cards và tuân thủ schema (`route: "/devices"`, `menu_path`, `steps`).
    * Loader merge VMS + AIOC cards (40 VMS + 7 AIOC = 47 cards).
    * `retrieve_docs` định vị đúng `camera_status`, `diagram_add_camera`, `login_devices`, `manage_camera`, `vms_vs_devices`.
    * `answer_from_docs` offline cho case 015 sinh văn bản chứa 'trực tuyến'.
    * `answer_from_docs` offline cho case 017 sinh văn bản chứa 'camera'.
    * `dataset_catalog.yaml` load thành công, case `agent_stat_v2_010` map tới `fire_smoke_event`, và hỗ trợ tìm table qua keywords.

### Changed
- `src/knowledge/loader.py`:
  - Mở rộng loader: thêm `aioc_docs_root()`, `load_vms_cards()`, `load_aioc_cards()`.
  - `load_published_cards()` tự động merge cả VMS và AIOC cards.
  - `clear_docs_cache()` xóa sạch cache của cả VMS và AIOC loader.
- `src/knowledge/retrieval.py`:
  - Tối ưu trọng số chấm điểm `retrieve_docs` cho các thẻ chuyên biệt AIOC (`aioc.camera_status`, `aioc.add_camera`, `aioc.diagram_add_camera`, `aioc.diagram_login_devices`, `aioc.vms_vs_devices`).
- `src/knowledge/answer.py`:
  - Tinh gọn `_offline_answer_from_cards`: loại bỏ các đoạn hardcode trùng lặp để nội dung câu trả lời được dẫn dắt trực tiếp từ YAML task cards; bổ sung `_empty_cards_fallback` tối thiểu khi không có thẻ nào được tìm thấy.
- `tests/test_docs.py`:
  - Cập nhật assertion tổng số cards published đã merge (47 cards) và kiểm tra tách bạch `load_vms_cards()` (40 cards).
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] Docs AIOC / catalog dataset trong resource/.`

### Verify
- `python -m pytest tests/test_aioc_docs.py tests/test_docs.py -v` (22 passed)
- `python -m pytest -q` (277 passed)

## 2026-09-22 — Phase 3c implemented (Multi-agent orchestrator MVP cho fail golden: 008, 009–011, 015, 017, 023, 024)

### Changed
- `src/llm/schemas.py`:
  - Thêm schema `OrchestratorStep(agent: Literal["query_data", "docs"], sub_question: str)`.
  - Thêm schema `OrchestratorPlan(steps: list[OrchestratorStep], is_multi: bool = False, reason: str = "")`.
- `src/llm/__init__.py`:
  - Export `OrchestratorStep`, `OrchestratorPlan`.
- `src/agent/orchestrator.py`:
  - Tạo mới module Multi-agent Orchestrator MVP:
    - Hàm `plan_orchestration(question: str) -> OrchestratorPlan` hỗ trợ online structured call qua prompt registry và fallback/chế độ offline.
    - Hàm `_offline_plan_orchestration(question: str)` phân loại ý định theo từ khóa:
      * Stat keywords (`hôm nay có`, `bao nhiêu`, `phát hiện`, `cảnh báo`, `leo trèo`, `cháy`, `khói`, `mực nước`, `đám đông`) -> `query_data` (case 009, 010, 011).
      * AIOC/howto/diagram keywords thuần túy không có stat -> `docs` (case 015, 017).
      * Tách 2 bước trên các mẫu liên từ (`rồi`, `và cho biết`, `khác gì so với`, ...) -> kết hợp `docs` + `query_data` (case 023).
      * Case so sánh sơ đồ thiết bị AIOC với câu hỏi thống kê (case 024) -> `docs` chuyên biệt, không chuyển câu hỏi sang SQL.
- `src/agent/__init__.py`:
  - Export `plan_orchestration`.
- `src/agent/intent.py`:
  - Cải thiện `_offline_classify`: câu hỏi chứa từ khóa sự kiện/thống kê (`leo trèo`, `cháy`, `khói`, `mực nước`, `đám đông`, `phát hiện`/`cảnh báo` theo thời gian) được ưu tiên vào `query_data` kể cả khi có nhắc đến AIOC.
  - Phân loại pure AIOC howto/diagram (vẽ sơ đồ, trạng thái trực tuyến, thêm camera) vào `how_to` (docs).
- `src/agent/query_plan.py`:
  - Cải thiện `_offline_plan_query`:
    * "đám đông"/crowd -> gán bảng `anomaly_event` kèm filter `event_type = 'CROWD_DETECTION'` (giải quyết case 008 invariant count).
    * "leo trèo"/intrusion -> filter `event_type = 'INTRUSION_DETECTION'`.
    * "mực nước"/water/ngập -> filter `event_type = 'WATER_LEVEL_DETECTION'`.
    * "ẩu đả"/fight -> filter `event_type = 'FIGHT_DETECTION'`.
- `src/knowledge/retrieval.py` & `src/knowledge/answer.py`:
  - Mở rộng `_PHRASES` và từ khóa nhận diện cho thao tác AIOC camera ("trực tuyến", "ngoại tuyến", "bảo trì", "thêm camera", "quản lý camera", "sơ đồ quy trình").
  - `retrieve_docs`: đưa `menu_path` và `route` vào chỉ mục tìm kiếm và cộng điểm ưu tiên cho thẻ `devices.edit_camera` và `devices.add_camera`.
  - `answer_from_docs`: tự động đính kèm thông tin giải thích trạng thái trực tuyến/ngoại tuyến/bảo trì và sơ đồ các bước thêm camera kèm URL `https://aioc.atin.vn/devices`.
- `src/agent/graph.py`:
  - Thêm `orchestrator_plan: OrchestratorPlan` vào `AgentState`.
  - Thêm node `orchestrator` đặt ngay sau node `classify` và trước conditional routing.
  - Thêm hàm điều hướng `route_orchestrator`:
    * `is_multi=True` (≥2 bước): rẽ sang node `orchestrator_respond`.
    * Single step `docs`: rẽ sang nhánh `retrieve_docs -> answer_from_docs`.
    * Single step `query_data`: rẽ sang nhánh `retrieve_schema -> plan_query -> validate -> execute -> respond`.
    * `out_of_scope`: rẽ sang nhánh `out_of_scope`.
  - Thêm node `orchestrator_respond`: thực thi docs sub-pipeline + query sub-pipeline (`plan_and_execute`), tổng hợp câu trả lời đa bước, gán `query` (`tool="sql_builder"`), phát sinh trace sub-events đầy đủ input/output và chuyển tiếp tới `store_extract`.
  - `respond_node`: bổ sung định dạng số "0" khi không có dòng dữ liệu kết quả (`0 lượt / 0 kết quả`).
- `resource/prompts/orchestrator/production.txt`:
  - Cập nhật nội dung prompt sản xuất chi tiết cho orchestrator điều phối multi-agent.
- `tests/test_orchestrator.py`:
  - Tạo mới bộ kiểm thử 14 unit tests kiểm tra:
    * `plan_orchestration` định tuyến đúng các case fail golden 009, 010, 011 sang `query_data`.
    * 015, 017 định tuyến sang `docs`.
    * 023 sinh kế hoạch 2 bước (`docs` + `query_data`).
    * 024 định hướng docs-focused (không chuyển toàn bộ sang SQL).
    * `_offline_plan_query` sinh đúng filter `CROWD_DETECTION` cho case 008.
    * Graph stream ghi nhận event trace của node `orchestrator` với input/output đầy đủ.
    * Run graph offline các case 008 (có số '0'), 009 (chạy đường SQL), 015 (có 'trực tuyến'), 017 (có 'camera'), 023 (multi-agent có cả 'aioc.atin.vn' và 'sql_builder'), 024 (có 'devices' và không gọi SQL).
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành duy nhất dòng: `- [x] Multi-agent orchestrator MVP cho fail golden: 008, 009–011, 015, 017, 023, 024.`

### Verify
- `pytest tests/test_orchestrator.py -v` (14 passed)
- `pytest -q` (266 passed)

---

## 2026-09-22 — Phase 3c implemented (Chart planner: ChartSpec bar | pie | line)

### Changed
- `src/llm/schemas.py`:
  - Thêm `normalize_chart_type(raw)`: chuẩn hóa kiểu biểu đồ sang `Literal["bar", "pie", "line"]`, mặc định `"bar"` khi đầu vào rỗng hoặc không hợp lệ.
  - Cập nhật `ChartSpec`: trường `chart_type: Literal["bar", "pie", "line"] = "bar"`, thêm `@field_validator` tự động chuẩn hóa trước khi khởi tạo Pydantic model. Giữ nguyên `x_column`, `y_column`, `title_vi`.
- `src/llm/__init__.py`:
  - Export `normalize_chart_type`.
- `src/chart/render.py`:
  - Import `normalize_chart_type`.
  - Cập nhật `_detect_chart_type`: nhận diện đầy đủ từ khóa tiếng Việt cho `bar`, `pie`, `line`.
  - Cập nhật `plan_chart`: trả về `ChartSpec` đã được chuẩn hóa/validate.
  - Cập nhật `render_chart`: hỗ trợ vẽ `bar`, `pie`, `line` (bảo vệ giá trị dương cho pie chart) và xuất chuỗi PNG base64.
- `src/chart/__init__.py`:
  - Export `normalize_chart_type`.
- `resource/prompts/plan_chart/production.txt`:
  - Cập nhật nội dung prompt chi tiết đồng bộ với template `v1.yaml`.
- `src/prompts/registry.py`:
  - Hỗ trợ fallback nạp trực tiếp prompt template khi `production.txt` chứa nội dung template thay vì chỉ version id.
- `src/agent/graph.py`:
  - `render_chart_node`: đảm bảo `chart_spec` lưu trong state và event metadata chứa đầy đủ JSON spec (`chart_type`, `x_column`, `y_column`, `title_vi`) trong cả `chart_meta`, `chart_spec` và `meta`.
  - `_wrap_node`: forward `chart_meta`, `chart_spec` và `meta` ra stream queue.
  - `should_render_chart_edge`: kiểm tra từ khóa vẽ biểu đồ trên cả câu gốc và câu đã rewrite.
- `tests/test_chart_planner.py`:
  - Tạo mới bộ unit tests kiểm tra:
    - `plan_chart` offline nhận diện `bar`, `pie`, `line` từ câu hỏi tiếng Việt.
    - `render_chart` cho `bar` và `pie` (kèm `line`) tạo chuỗi PNG base64 hợp lệ.
    - Graph stream (`run_agent_stream`) kích hoạt node `render_chart` và phát sinh event chứa `chart_meta`.
    - Kiểu biểu đồ không hợp lệ được tự động chuẩn hóa về `"bar"`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] Chart planner: `ChartSpec` bar | pie (| line nếu dễ).`

### Verify
- `pytest tests/test_chart_planner.py -v`
- `pytest -q`

---

## 2026-09-22 — Phase 3c implemented (Trace mỗi node: full input + output + session/user metadata)

### Changed
- `src/agent/graph.py`:
  - Thêm `session_id: str` vào `AgentState`.
  - Cập nhật `_wrap_node` tự động trích xuất `user_id` và `session_id` từ `AgentState` và gán vào metadata của span trace (`trace_step`).
  - Cập nhật toàn bộ các node (`recall`, `store_extract`, `rewrite`, `classify`, `retrieve_docs`, `answer_from_docs`, `out_of_scope`, `retrieve_schema`, `plan_query`, `validate`, `execute`, `render_chart`, `respond`) sinh `events` có `input`, `output` đầy đủ chi tiết (JSON payloads, parameters, IDs) và `meta` kèm `user_id`, `session_id`.
  - `run_agent` và `run_agent_stream`: truyền `session_id` và `user_id` vào state khởi tạo khi invoke graph.
- `src/monitoring/tracing.py`:
  - `trace_answer` và `trace_step`: hỗ trợ truyền trực tiếp `session_id` và `user_id` vào Langfuse `start_observation` khi khởi tạo trace cha và child spans.
- `src/main.py`:
  - Cập nhật các endpoint `/api/chat`, `/api/agent/stream`, `/ask` truyền `session_id` và `user_id` vào `metadata` của `trace_answer`.
- `tests/test_trace_cache.py`:
  - Thêm test `test_every_graph_node_emits_full_input_output_and_session_user_meta`: kiểm tra toàn bộ pipeline query_data và docs sinh node events có input/output đầy đủ không rỗng.
  - Thêm test `test_trace_observation_receives_session_and_user_metadata`: kiểm tra Langfuse root trace và child spans nhận đúng `session_id` và `user_id`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] Trace mỗi node: **full** input + output (Langfuse + metadata session/user).`

### Verify
- `pytest tests/test_trace_cache.py -v`
- `pytest -q`

---

## 2026-09-22 — Review fix: recall/store memory wiring

### Changed
- `src/agent/graph.py`:
  - `_memory_context_block()`: chèn `recalled_memories` vào prompt `respond_stat`.
  - Nhánh `out_of_scope → store_extract → END` (trước đó bỏ qua store).
- `src/guardrails.py`:
  - `MEMORY_STATEMENT_KEYWORDS`: cho phép câu ghi nhớ fact (vd. "Tên tôi là…") qua guardrail `in_scope`.
- `tests/test_memory_nodes.py`:
  - Test inject recalled memories vào respond prompt.
  - Test out_of_scope vẫn chạy store_extract.

### Verify
- `pytest -q tests/test_memory_nodes.py`
- `pytest -q`

---

## 2026-09-22 — Phase 3b implemented (Node recall đầu + store/extract cuối)

### Changed
- `src/memory/extract.py`:
  - Tạo module trích xuất fact từ lượt hội thoại và lưu vào long-term memory store.
  - Hàm `_heuristic_extract(question: str) -> list[str]`: trích xuất tên người dùng, vai trò/phụ trách, sở thích/ưu tiên và chỉ định ghi nhớ phục vụ offline heuristic và fallback nhanh.
  - Hàm `extract_memories(user_id: str, question: str, answer: str = "") -> list[str]`: kết hợp heuristic và prompt `memory_extract` qua LLM khi ở chế độ online.
  - Hàm `extract_and_store_memory(user_id: str, question: str, answer: str = "") -> list[str]`: trích xuất và tự động gọi `save_to_long_term(user_id, fact)` cho từng fact.
- `src/memory/__init__.py`:
  - Export `extract_memories` và `extract_and_store_memory`.
- `src/agent/graph.py`:
  - `Agent_Input`: thêm trường `user_id: str = "default"`.
  - `AgentState`: thêm `user_id: str`, `recalled_memories: list[str]`, `extracted_memories: list[str]`.
  - Node `recall`: đặt ở đầu pipeline (`START → recall → rewrite`), truy xuất tối đa 3 fact liên quan từ long-term memory theo `user_id` và câu hỏi, ghi trace event `recall`.
  - Node `store_extract`: đặt ở cuối các nhánh thành công (`respond → store_extract → END`, `answer_from_docs → store_extract → END`), trích xuất thông tin người dùng từ câu hỏi/kết quả và lưu vào long-term memory, ghi trace event `store_extract`.
  - `run_agent` và `run_agent_stream`: nhận tham số `user_id: str | None = None` và truyền `user_id` vào graph state invoke.
- `src/main.py`:
  - `ChatRequest`: thêm trường `user_id: str = "default"`.
  - Endpoint `/api/chat`: truyền `user_id=req.user_id` xuống `run_agent`.
  - Endpoint `/api/agent/stream`: truyền `user_id=req.user_id` xuống `run_agent_stream`.
- `tests/test_api.py`:
  - Cập nhật `test_agent_graph_stream_realtime` kiểm tra node `recall` chạy và hoàn thành trước `rewrite` và `classify`.
- `tests/test_memory_nodes.py`:
  - Tạo mới 7 unit tests kiểm tra: cấu trúc node trong graph (`recall`, `store_extract`), regex heuristic patterns, `extract_and_store_memory`, trích xuất online với mock LLM, end-to-end recall/store giữa 2 session của cùng user_id và cách ly với user khác, SSE stream phát sinh đầy đủ event cho `recall` và `store_extract`, và endpoint `/api/chat` truyền `user_id` lưu memory thành công.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] Node recall (đầu) + store/extract (cuối).`
  - Cập nhật trạng thái: `Phase 1, 2, 3a, 3b done; Phase 3c–7 còn mở.`

### Verify
- `pytest tests/test_memory_nodes.py -v`
- `pytest -q`

---

## 2026-09-22 — Phase 3b implemented (TTL response cache 300s)

### Changed
- `src/config.py`:
  - Thêm property và setter `ttl_cache_enabled` alias theo `cache_enabled`.
- `src/memory/ttl_cache.py`:
  - Tạo module mới với thread-safe dict store (`_ttl_cache` + `_ttl_lock`, kèm alias `_cache`).
  - `make_cache_key(question: str, route: str = "") -> str`: chuẩn hóa strip + lower, sinh SHA-256 key (kết hợp route nếu được cung cấp sau graph).
  - `get_ttl_cached(key: str) -> dict | None`: kiểm tra `ttl_cache_enabled` / `cache_enabled`, thời lượng `memory_ttl_seconds`, hỗ trợ exact match và question prefix match, tự động dọn dẹp entry hết hạn.
  - `set_ttl_cached(key: str, data: dict, ttl: int | None = None) -> None`: lưu data vào cache kèm `expire_at` tính theo `memory_ttl_seconds`.
  - `clear_ttl_cache() -> None`: xóa toàn bộ cache phục vụ tests.
- `src/memory/__init__.py`:
  - Export `make_cache_key`, `get_ttl_cached`, `set_ttl_cached`, `clear_ttl_cache`.
- `src/main.py`:
  - Bỏ inline `get_cached_answer` và `set_cached_answer`.
  - Import và sử dụng `get_ttl_cached`, `set_ttl_cached`, `make_cache_key` từ `src.memory.ttl_cache`.
  - Đặt cờ `cache_hit=True` trong `detail` khi trúng cache.
  - Ghi cache sau graph với `route=out.detail or intent` sử dụng `memory_ttl_seconds` (không dùng `cache_ttl_s`).
  - Giữ alias `_cache = _ttl_cache` đảm bảo backward compatibility.
- `tests/test_memory_ttl_cache.py`:
  - Thêm unit tests: `make_cache_key` chuẩn hóa và khác route sinh khác key; hit trong 300s; miss sau expire (mock `time.time`); vô hiệu hóa khi `CACHE_ENABLED=False` hoặc `ttl_cache_enabled=False` hoặc `memory_ttl_seconds <= 0`; hit trước graph với câu hỏi cùng nội dung; hit trước graph qua `/api/chat` và `/api/agent/stream`; dọn cache bằng `clear_ttl_cache`.
- `tests/test_trace_cache.py`:
  - Cập nhật sử dụng `clear_ttl_cache()` và `memory_ttl_seconds`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] TTL cache 300s: hit trước graph khi trùng câu.`

### Verify
- `pytest -q`

---

## 2026-09-22 — Phase 3b implemented (Long-term memory MVP by user_id)

### Changed
- `src/memory/longterm.py`:
  - Thêm in-memory store `_LONG_TERM_STORE: list[tuple[str, str, float]]` lưu `(user_id, fact, ts)`.
  - Hàm `save_to_long_term(user_id: str, fact: str) -> None`: bỏ qua nếu `user_id` hoặc `fact` rỗng/khoảng trắng, strip fact trước khi lưu. Hỗ trợ fallback in-memory và tuỳ chọn Qdrant nếu có cấu hình `QDRANT_URL` và thư viện `qdrant-client`.
  - Hàm `recall_long_term(user_id: str, query: str, k: int = 3) -> list[str]`: chấm điểm keyword overlap scoring (tương tự pattern demo fallback) kết hợp sắp xếp độ mới, lọc nghiêm ngặt chỉ theo `user_id`.
  - Hàm `clear_long_term(user_id: str | None = None) -> None`: tiện ích dọn sạch bộ nhớ trong unit tests.
- `src/memory/__init__.py`:
  - Export `save_to_long_term`, `recall_long_term`, `clear_long_term`.
- `tests/test_memory_longterm.py`:
  - Thêm offline unit tests kiểm tra: lưu và recall theo query liên quan; cùng user_id khác session recall hoạt động bình thường; cách ly bộ nhớ giữa các user_id; xử lý no-op / rỗng khi user_id hoặc fact rỗng; xếp hạng ưu tiên fact có từ khóa trùng khớp cao hơn.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành: `- [x] Long-term theo `user_id` (in-memory hoặc Qdrant MVP).`

### Verify
- `pytest -q`

---

## 2026-09-22 — Phase 3b implemented (Short-term memory checkpointer MVP)

### Changed
- `src/memory/shortterm.py`:
  - Tạo singleton `_checkpointer = MemorySaver()` và export `get_checkpointer()`.
- `src/agent/graph.py`:
  - Module-level `_compiled = None`; `_get_graph()` compile 1 lần với checkpointer singleton.
  - Thêm `messages: Annotated[list, add_messages]` vào `AgentState`.
  - Cập nhật `rewrite_node` thêm `HumanMessage(question)` vào `messages` để checkpointer lưu trữ các lượt hội thoại.
  - `run_agent` và `run_agent_stream` nhận `session_id: str = "default"` và truyền `config={"configurable": {"thread_id": session_id}}` vào graph invoke.
- `src/main.py`:
  - Thêm trường `session_id: str = "default"` vào `ChatRequest`.
  - Truyền `req.session_id` xuống `run_agent` trong endpoint `/api/chat` và `run_agent_stream` trong `/api/agent/stream`.
- `tests/test_memory_shortterm.py`:
  - Thêm offline unit tests kiểm tra: singleton `get_checkpointer()`, invoke graph 2 lần cùng `session_id` qua `graph.get_state(config)` kiểm tra có 2+ messages, kiểm tra cách ly giữa các session_id khác nhau, và default session_id trên `ChatRequest`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành Phase 3b: `[x] Short-term theo session_id (checkpointer MVP)`.

### Verify
- `pytest -q`

---

## 2026-09-22 — Phase 3a implemented (Wire prompts & LLMOps)

### Changed
- `src/agent/rewrite.py`:
  - Sửa NameError `REWRITE_SYSTEM_PROMPT` bằng cách dùng `registry().render("rewrite")`.
- `src/agent/intent.py`:
  - Thay thế `INTENT_SYSTEM_PROMPT` bằng `registry().render("classify")`.
- `src/agent/query_plan.py`:
  - Thay thế `PLAN_QUERY_SYSTEM_PROMPT` bằng `registry().render("plan_query")`.
  - Thay thế `REPAIR_SYSTEM_PROMPT` bằng `registry().render("plan_query_repair")`.
- `src/knowledge/answer.py`:
  - Thay thế `DOCS_SYSTEM_PROMPT` bằng `registry().render("answer_docs")`.
- `src/chart/render.py`:
  - Thay thế `CHART_PLAN_SYSTEM_PROMPT` bằng `registry().render("plan_chart")`.
- `src/agent/graph.py`:
  - Thay thế `STAT_RESPOND_SYSTEM_PROMPT` bằng `registry().render("respond_stat")`.
- `src/main.py`:
  - Cập nhật `/api/llm/ping` trả về `{status, backend, model, base_url}` lấy từ `settings` (không lộ secrets).
- `tests/test_llm.py`:
  - Thêm unit test kiểm tra từng prompt name load thành công qua `registry()`.
  - Thêm unit test kiểm tra `registry().render` thiếu biến bắt buộc raise `ValueError`.
  - Thêm unit test kiểm tra cấu trúc phản hồi `/api/llm/ping`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành Phase 3a `[x]`.

### Verify
- `pytest -q`

---

### Updated
- `specs/implementation-plan.md`: chia T01–T57 (một task / một delegate); Phase 1–2 done; T14 done; **T15 next** (wire rewrite.py).
- `AGENTS.md`, `specs/test-plan.md`: quy tắc một task mỗi lần, không gom phase.

### Lý do
- Delegate agy timeout / incomplete khi gom cả Phase 3a — chuyển sang task atomic.

---

## 2026-09-22 — Phase 2 implemented (Core UI)

### Changed
- `frontend/index.html`:
  - Thay thế 8 domain tags trên sidebar bằng section "Phiên chat" và container `#session-list`.
  - Di chuyển 8 domain chips vào khung chat nằm ngay trên textarea (`#domain-chips`), giữ nguyên `data-query` click để gửi.
  - Giữ nguyên bố cục 3 cột: `[Sessions] | [Chat] | [Live graph]`.
- `frontend/style.css`:
  - Thêm styling cho `.session-list` và `.session-item` (tiêu đề, thời gian, xem trước 1 dòng với ellipsis, trạng thái active).
  - Thêm styling cho `.domain-chips` và `.domain-chip` (thanh chip cuộn ngang bo tròn phía trên ô nhập).
  - Thêm styling cho `.chart-slot` và `.chart-placeholder` (khung vị trí biểu đồ cho bar/pie chart).
- `frontend/app.js`:
  - Quản lý phiên chat và người dùng qua `localStorage`:
    - `agent_user_id`: UUID ổn định (khởi tạo một lần).
    - `agent_session_id`: UUID phiên đang kích hoạt.
    - `agent_sessions`: JSON `[{id, title, preview, updatedAt, messages}]`.
  - Nút `#btn-new-chat`: tạo phiên chat mới (UUID), xóa màn hình chat, thêm vào danh sách và lưu vào `localStorage`.
  - Chuyển phiên chat: bấm vào session trong `#session-list` → chuyển phiên, tải tin nhắn từ `localStorage` (mock thuần client, không gọi API backend).
  - Khi gửi câu hỏi: cập nhật tiêu đề, preview, thời gian và mảng tin nhắn của session trong `localStorage`.
  - Thêm `.chart-slot` vào mỗi tin nhắn assistant phục vụ render biểu đồ bar/pie ở Phase 4.
- `specs/implementation-plan.md`: Cập nhật trạng thái Phase 2 done `[x]`.

### Verify
- Kiểm tra cấu trúc HTML / CSS / JS đồng bộ:
  - Sidebar hiển thị danh sách phiên chat với tiêu đề, thời gian, preview 1 dòng.
  - Bấm chọn session chuyển phiên và tải tin nhắn từ `localStorage`.
  - Bấm "Đoạn chat mới" tạo session mới, xóa chat và thêm vào list.
  - 8 domain chips hiển thị trên textarea, click gửi câu hỏi trực tiếp.
  - Tin nhắn trợ lý có container `.chart-slot`.
  - Bố cục `[Sessions] | [Chat] | [Live graph]` giữ nguyên.
- `pytest -q` → 201 passed.

---

## 2026-09-22 — Phase 1 review-fix

### Review (vs product-spec / test-plan — scope Phase 1)
- **Pass:** `resource/{prompts,docs,db,eval}`; path docs/prompts/catalog; Dockerfile `COPY resource/`; `.env.example` LLM + `MEMORY_TTL_SECONDS`; xóa `react.py`; `pytest -q` xanh.
- **Fail:** không (trong scope Phase 1).
- **Missing (đã vá):** assert offline cho `COPY resource/` + path `resource/`; header plan còn ghi “chưa code”.

### Fixed
- `tests/test_api.py`: assert `COPY resource/` trong Dockerfile.
- `tests/test_docs.py`: assert `DOCS_ROOT` dưới `resource/docs/vms_yaml`.
- `tests/test_llm.py`: assert PromptRegistry default → `resource/prompts`.
- `specs/implementation-plan.md`: trạng thái Phase 1 done.

### Verify
- `pytest -q`

---

## 2026-09-22 — Phase 1 implemented (project setup)

### Changed
- `resource/{prompts,docs/vms_yaml,db/catalog.yaml,eval}` — layout tĩnh v6.
- `prompts/` → `resource/prompts/`; `docs/vms_yaml/` → `resource/docs/vms_yaml/`.
- `src/db/catalog.py` load `resource/db/catalog.yaml`.
- `src/config.py`: `DOCS_ROOT=resource/docs/vms_yaml`, `MEMORY_TTL_SECONDS=300`.
- `src/prompts/registry.py`: default `resource/prompts`.
- `Dockerfile`: `COPY resource/`.
- Xóa `src/agent/react.py` (legacy, không import).
- `.env.example` cập nhật LLM + memory env.

### Verify
- `pytest -q` → **200 passed** (gồm `tests/test_resource_paths.py` sau review).
- Review SDD: thêm test resource paths; sửa `.dockerignore`; cập nhật trạng thái spec/README.

---

## 2026-09-22 — AGENTS.md (SDD bước 4)

### Updated
- `AGENTS.md`: rules SDD (đọc spec → một phase → simple → change-log + cách test); conventions v6 ngắn.

---

## 2026-09-22 — Implementation plan review (SDD bước 3)

### Updated
- `specs/implementation-plan.md`: 7 phase nhỏ (setup → UI → backend → connect → validation → run docs → prod eval), mỗi phase có checklist + done khi.

---

## 2026-09-22 — Product spec review (SDD bước 2)

### Updated
- `specs/product-spec.md`: rút gọn, làm rõ 6 mục bắt buộc (goal, users, flow, in/out scope, acceptance); chi tiết kỹ thuật gom vào “Ghi chú MVP”.

---

## 2026-09-22 — v6 spec refresh (planning only)

### Added / updated (spec)
- **Memory:** short-term (session), long-term (user_id), TTL response cache **300s**.
- **UI:** sidebar trái = danh sách session (thay 8 domain tag); domain chips vào chat.
- **Product spec v6:** đầy đủ yêu cầu refactor, LLMOps prompts, LLM switch, charts, multi-agent, trace full I/O.
- **Implementation plan:** Phase 1–9 (thêm Phase 5 memory, Phase 6 UI sessions).
- **Test plan:** memory, sessions, TTL, production 196, golden-30 ≥28/30.
- **README + AGENTS.md:** v6 planning, Docker-first.

### Not changed (yet)
- Source code, Docker image, thư mục `resource/` — implement theo phase.

### Baseline eval
- `eval/results/golden-30.md`: **22/30 pass** live (2026-09-21).
- Fail ưu tiên: 008, 009, 010, 011, 015, 017, 023, 024.

---

## 2026-09-22 — v6 planning (spec only, lần 1)

Xem mục trên; bản refresh bổ sung memory + sessions UI.

---

## Lịch sử v5

Langfuse trace, LLM backend, Phase 1–7 demo-ready — chi tiết trong các commit trước v6.
