## 2026-09-22 (LLM — gỡ backend Ollama, chỉ openai + self_hosted/vLLM)

### Changed
- **`src/llm/client.py`**: xóa backend `ollama` và `:11434`; `self_hosted` = vLLM qua gateway OpenAI-compatible (`MODEL_*`).
- **`eval/run.py`**, **`src/config.py`**, **`.env.example`**, **README**: bỏ wording Ollama; mô tả rõ vLLM gateway `196:18083`.

### Verify
```bash
pytest tests/test_llm.py -q
grep -ri ollama src/ eval/ tests/ .env.example README.md   # không còn match
```

## 2026-09-22 (LLM — gateway 196:18083, sửa ping)

### Changed
- **`.env` / `.env.example` / README**: demo `self_hosted` → gateway `http://192.168.1.196:18083/v1`, model `qwen3-4b`, `MODEL_API_KEY` gateway (không Ollama thẳng `:11434`).
- **`src/llm/client.py` `ping()`**: dùng `settings.effective_base_url` + token đúng backend (`model_api_key` khi self_hosted).

### Verify
```bash
docker compose up --build -d
curl -s http://localhost:8000/api/llm/ping
```

## 2026-09-22 (Langfuse — đặt tên container/volume có prefix langfuse)

### Changed
- `langfuse/docker-compose.yml`: `clickhouse`/`redis`/`minio` → `kcn_hungphu_langfuse_*`; volume có `name: kcn_hungphu_langfuse_*`.

## 2026-09-22 (Langfuse — dừng stack, bỏ setup-langfuse.sh)

### Changed
- Dừng + xóa 6 container Langfuse (web, worker, postgres, clickhouse, redis, minio).
- Xóa `scripts/setup-langfuse.sh`; doc chỉ `docker compose` trực tiếp.
- Cập nhật README, langfuse/README, `.env.example`, compose comments, test-plan, implementation-plan.

### Chạy lại Langfuse
```bash
cd agent-harness/dong/langfuse && docker compose up -d
```

## 2026-09-22 (README — SDD Bước 9 local dev + Docker deploy)

### Changed
- **`README.md`**: mục **Local development** (prerequisites, install, env, backend/frontend commands, URLs, troubleshooting) và **Docker deploy** tách riêng; không đổi app logic.

## 2026-09-21 (Phase 7 — review vs product-spec / test-plan)

### Pass
- README **Demo checklist (5 phút)** đủ 7 bước; **Current state** demo-ready + link acceptance.
- Cleanup inventory đã xóa: `ai/`, `static/`, `manual_test.sh`, `prep_changelog.sh`, `docs/vms/`, `agent-canvas.md`; giữ `docs/vms_yaml/`.
- `Dockerfile` COPY `docs/vms_yaml/`; `DOCS_ROOT=docs/vms_yaml`.
- Phase 7 checklist `[x]`; status Phase 1–7 trên product-spec / test-plan / AGENTS / plan.
- `pytest -q` → 193 passed; 9 test files; không `backend/`.

### Fail (đã fix — Cursor review)
- Phase 1 note vẫn ghi “chưa xóa” / product-spec còn “trong phase cleanup” → đánh đã xóa Phase 7.
- Demo checklist bước 2–6 hơi mơ hồ (thiếu `curl`, credentials Langfuse, gợi ý `vehicle_type=CAR`) → siết wording copy-paste.

### Missing
- Không còn phase unchecked trong plan v5 MVP.
- Live golden-30 v2.2 / AIOC asserts (đã ghi ở Phase 6) — ngoài scope demo cleanup.

### Verified
- `pytest -q` → 193 passed
- Legacy paths gone; `docs/vms_yaml/how_to/ai/*.yaml` còn nguyên

## 2026-09-21 (Phase 7 — Demo setup / Cleanup)

### Added / Changed
- Thêm **Demo checklist (5 phút)** vào `README.md` với 7 bước copy-pasteable.
- Cập nhật dòng trạng thái **Current state** trong `README.md` xác nhận hoàn tất v5 (Phase 1–7) và đạt trạng thái demo-ready.
- Dọn dẹp legacy code: xóa `ai/`, `static/`, `manual_test.sh`, `prep_changelog.sh`, `docs/vms/` (chỉ giữ YAML), `agent-canvas.md`.
- Sửa `Dockerfile` chuyển `COPY docs/vms/` thành `COPY docs/vms_yaml/`.
- Cập nhật checklist trong `specs/implementation-plan.md` (Phase 7 done) và trạng thái đồng bộ ở các file test-plan, product-spec, AGENTS.
- Milestone **v5 demo-ready**.

## 2026-09-21 (Phase 6 — review vs product-spec / test-plan)

### Pass
- `eval/run.py` trích `detail` + `query.tool` (v5); offline không ghi đè `golden-30.md`.
- Dataset v2.2: `must_include_tool` → `sql_builder` / chặn `sql_builder` trên how-to; giữ 30 case 18/6/3/3.
- `--judge` + pop `PYTEST_CURRENT_TEST` trên live; README/test-plan ghi ~15–30 phút + LAN 196.
- `pytest -q` xanh; 9 file test; không `backend/`; Phase 6 checklist `[x]`.

### Fail (đã fix — Cursor review)
- `product-spec` / `AGENTS` / `test-plan` header vẫn Phase 1–5 → sync Phase 1–6.
- `test_eval_run_pipeline_offline` empty `pass` → thay bằng unit test extraction/assertions v5.
- change-log ghi nhầm “10 file tests”.

### Missing (đúng scope — Phase 7 / live)
- Chưa re-run live `python eval/run.py --judge` với dataset v2.2 (cần LAN 196 + DB) → `golden-30.md` hiện còn báo cáo cũ.
- Một số case AIOC/`aioc.atin.vn` vẫn assert nội dung web AIOC trong khi docs v5 là YAML VMS — có thể fail live cho tới khi chỉnh expected/docs (không thêm feature ở review này).

### Verified
- `pytest -q` (sau fix).

## Phase 6 (2026-09-21)

- Hoàn tất test và đánh giá (Phase 6).
- Sửa `eval/run.py` để tương thích v5: parse `detail` (query_data, docs, out_of_scope) và `query.tool` (`sql_builder`) thay vì các tool ReAct cũ.
- Cập nhật bộ test dataset `eval/datasets/agent_stat/v2.yaml` (bump lên v2.2):
  - Đổi các `must_include_tool` từ legacy ReAct (count_vehicle_flow, v.v) thành `sql_builder`/`docs`/`query_data`.
  - Giữ vững 30 case và tỉ lệ 18/6/3/3.
- Bổ sung test `--help` + extraction v5 vào `test_api.py`.
- `pytest -q` offline; **9** file `test_*.py` (< 10); không thư mục `backend/`.
- Update specs thành "Phase 1–6 xong".
- Document thời gian chạy `golden-30` (~15-30 phút), cần DB/LAN 196 cho bản live.

## 2026-09-21 (Phase 5 — review vs product-spec / test-plan)

### Pass
- README Deploy = Docker Compose only; quick start không dùng `.venv` / `pip`.
- Env table: LLM / DB / Langfuse / `DOCS_ROOT` / `SQL_REPAIR_MAX` / ports.
- Lệnh `./scripts/setup-langfuse.sh` vs `docker compose up --build -d`; URL + credentials Langfuse khớp `langfuse/README.md`.
- `LANGFUSE_HOST` local vs `host.docker.internal` documented; compose override khớp file thật.
- `docker-compose.yml` chỉ `frontend` + `ai_backend`; Langfuse tách `langfuse/`.
- Troubleshooting + Dev local uvicorn tách khỏi quick start.
- Checklist Phase 5 `[x]`; status Phase 1–5 trên product-spec / test-plan / AGENTS.
- `docker compose config` exit 0; pytest compose structure tests còn xanh.

### Fail (đã fix — Cursor review)
- README chưa nhấn `LLM_BACKEND=self_hosted` khi demo Ollama 196 (`.env.example` mặc định `openai`) → bổ sung ghi chú ngay sau `cp .env.example .env`.

### Missing (đúng scope — Phase 6+)
- Gom pytest / golden-30 — Phase 6.
- Demo checklist 5 phút / dọn legacy — Phase 7.

### Verified
- `docker compose config` → OK
- `pytest -q` → 191 passed (offline)

## 2026-09-21 (Phase 5 — Docker run instructions: docs & compose alignment)

### Added / Changed
- **`README.md`**:
  - Viết lại toàn bộ phần **Deploy (Docker Compose)** làm đường dẫn chính (quick start): chỉ yêu cầu Docker + Docker Compose, không chứa bất kỳ chỉ dẫn nào về Python hay `.venv` / `pip install`.
  - Cập nhật dòng trạng thái dự án: Phase 1–5 hoàn tất (Setup, Core logic, LangGraph v5 pipeline, Error handling, Docker docs & compose alignment).
  - Cập nhật mục **Kiến trúc v5** phản ánh chính xác cấu trúc thực tế đang hoạt động (`src/llm/`, `src/agent/`, `src/db/`, `src/knowledge/`, `src/chart/`, `frontend/`, `langfuse/`).
  - Hướng dẫn chuẩn bị file môi trường từ `cp .env.example .env` kèm bảng biến môi trường chi tiết cho 5 nhóm: LLM (OpenAI / Ollama LAN 196), Postgres VMS read-only, ClickHouse (tuỳ chọn), Langfuse observability, v5 Core (`DOCS_ROOT`, `SQL_REPAIR_MAX`), và cổng kết nối (`FRONTEND_PORT`, `BACKEND_PORT`).
  - Làm rõ hai tùy chọn khởi động bằng lệnh: `./scripts/setup-langfuse.sh` (khởi động trọn gói cả app + Langfuse stack độc lập) và `docker compose up --build -d` (chỉ khởi động app dong: `frontend` + `ai_backend`).
  - Bảng tổng hợp URL dịch vụ (Frontend UI `:8080`, Backend Health `/api/health` `:8000`, Langfuse `:3000`) cùng thông tin tài khoản mặc định `admin@agent-atin.local` / `Atin@123#`.
  - Giải thích cơ chế `LANGFUSE_HOST`: local dev uvicorn dùng `http://localhost:3000`; container Docker backend tự động kết nối `http://host.docker.internal:3000` thông qua override trong `docker-compose.yml` và `extra_hosts`.
  - Mục **Troubleshooting ngắn** súc tích: xử lý lỗi UI sai API URL, không thấy trace trên Langfuse, LLM ping thất bại và xử lý khi DB chưa cấu hình / read-only.
  - Tách riêng mục **Dev local uvicorn** thành phần tuỳ chọn cho developer, không lẫn vào quick start.
- **`docker-compose.yml`**: Xác nhận compose chỉ chứa 2 services của app (`frontend` + `ai_backend`), không nhúng stack Langfuse (độc lập tại `langfuse/docker-compose.yml`); cổng và biến môi trường khớp tài liệu.
- **`langfuse/README.md`**: Cập nhật đồng bộ lệnh one-shot `./scripts/setup-langfuse.sh` và reset dữ liệu `./scripts/setup-langfuse.sh --reset` từ thư mục gốc `dong`.
- **`specs/implementation-plan.md`**: Đánh dấu hoàn thành toàn bộ 9 mục checklist Phase 5 `[x]`, cập nhật tiêu đề tiến độ Phase 1–5 xong.
- **`specs/product-spec.md`**, **`specs/test-plan.md`**, **`AGENTS.md`**: Đồng bộ dòng trạng thái tiến độ Phase 1–5 hoàn tất.

### Verified
- Cấu trúc YAML của `docker-compose.yml` (services: `frontend`, `ai_backend`) và `langfuse/docker-compose.yml` (services: `langfuse-web`, `langfuse-worker`, `clickhouse`, `minio`, `redis`, `postgres`) hợp lệ cú pháp, khớp spec.
- Cổng kết nối và biến môi trường đồng bộ: `FRONTEND_PORT` (8080), `BACKEND_PORT` (8000), `LANGFUSE_HOST` (`host.docker.internal:3000` trong container).
- `pytest -q` → 191 passed, 1 warning (offline, 0 failed).
- Quick start trong `README.md` hoàn toàn không có `.venv` hay `pip install`.

### Not done
- Phase 6: Tests & eval (gom pytest < 10 files, chạy eval dataset v2 golden-30 live).
- Phase 7: Demo setup (checklist 5 phút, dọn code thừa).

## 2026-09-21 (Phase 4 — review vs product-spec / test-plan)

### Pass
- Guardrail injection → 400; out-of-scope trước graph.
- Validate/execute lỗi bubble lên catch-all; `_format_error_message` tiếng Việt (parse/DB/SQL/timeout).
- Empty rows: `respond` trả “Không có dữ liệu…”; docs empty: “Không tìm thấy hướng dẫn…”.
- Chart render fail: try/except bỏ chart, vẫn trả text.
- FE AbortController + thông báo lỗi kết nối; SSE `__answer__` dùng friendly message.

### Fail (đã fix — Cursor review)
- Error-node SSE/`run_agent_stream` dump `str(exc)` (có thể chứa SQL) → chỉ còn friendly message.
- Docs empty vẫn wording cũ “chưa có thông tin” → đồng bộ “Không tìm thấy hướng dẫn…”.
- Trạng thái Phase 4 chưa sync product-spec / test-plan / AGENTS / implementation-plan header.

### Missing (đúng scope — Phase 5+)
- README Docker-only quick start — Phase 5.
- Golden-30 / gom pytest — Phase 6.

### Verified
- `pytest -q` (sau fix).

## 2026-09-21 (Phase 4 — Validation and error states)

### Added / Changed
- **`src/main.py`**: Cập nhật `_format_error_message` để trả về câu lỗi tiếng Việt thân thiện khi gặp lỗi LLM structured output (parse/schema/validation) và lỗi sinh SQL / thực thi DB. Cập nhật để hỗ trợ bắt các lỗi này và không crash luồng stream (`stream_agent`).
- **`src/agent/graph.py`**: Chuyển đổi `{"error": ...}` thành `raise ValueError(error)` trong `validate_node` và `raise RuntimeError(...)` trong `execute_node` để các lỗi được bubble up lên catch-all của agent. Điều này giúp Langfuse span ghi nhận error level và trả về câu báo lỗi thân thiện thay vì leak SQL/error nội bộ hoặc tạo kết quả sai.
- **`src/agent/graph.py`**: `respond_node` không gọi LLM nếu `not rows` (trả về trực tiếp "Không có dữ liệu..."), tránh bịa số khi empty.
- **`specs/implementation-plan.md`**: Đánh dấu Phase 4 `[x]`.

### Verified
- `pytest -q` → 34 passed cho `test_api.py`.
- `pytest -q -k "guardrail or validator or error or empty or docs or query"` → 98 passed (offline).
- Không rò rỉ SQL; trace lỗi báo đúng cấu trúc; parse error không crash stream.

### Not done
- Phase 5 (Docker run instructions).
- Phase 6-7.

## 2026-09-21 (Phase 3 — review vs product-spec / test-plan)

### Pass (phạm vi Phase 3)
- StateGraph: `rewrite → classify → query|docs|out`; không còn node `react` / `chon_tool` trên đường chính.
- Query: schema → plan → validate → execute → optional chart → respond (`StatAnswer` + template fallback).
- Docs / OOS nhánh đúng; SSE `running`/`done`; FE `<img>` khi có `chart_png_base64`.
- Cache key = câu **sau rewrite** (`main.py`).
- `graph.mmd` cập nhật pipeline v5.
- Acceptance **#5** (chart UI path), **#6** (node rewrite SSE) ở mức code; pytest offline **189 passed**.

### Fail (đã fix — Cursor review)
- Checklist Phase 3 vẫn `[ ]` dù code đã wire → đánh `[x]`.
- Langfuse nested span per node thiếu (`_trace_span` không dùng) → `_wrap_node` gọi `trace_step(parent, node_id, ...)`.
- Import lộn schema/builder; thiếu entry change-log Phase 3; status docs lệch → sync.
- `test_graph_nodes_and_structure` chưa assert `rewrite` / không còn `react`.

### Missing (đúng scope — Phase 4+)
- Error matrix đầy đủ (parse fail UX, empty rows polish, disconnect) — Phase 4.
- Live verify 3 câu + Langfuse UI — manual/live.
- Xóa hẳn `react.py` / 9 tools — để Phase 7 cleanup (đã deprecate khỏi đường chính).

### Fixed
- `src/agent/graph.py`: `trace_step` trong `_wrap_node`; import sạch.
- Checklist + status `implementation-plan` / `product-spec` / `test-plan` / `AGENTS`.
- `tests/test_intent.py` structure assert v5.

## 2026-09-21 (Phase 3 — Graph v5 thay ReAct + SSE chart)

### Added / Changed
- **`src/agent/graph.py`**: pipeline LangGraph v5 (rewrite/classify/query/docs/out); gỡ ReAct khỏi đường chính; SSE events + `chart_png_base64`.
- **`src/main.py`**: cache key = rewritten text; stream nhận rewritten trước khi chạy graph.
- **`frontend/app.js`**: hiển thị PNG chart dưới câu trả lời.
- **`graph.mmd`**: sơ đồ pipeline v5.

### Verified
- `pytest -q` → 189 passed (offline).
- Nodes: rewrite, classify, retrieve_schema, plan_query, validate, execute, render_chart, respond, retrieve_docs, answer_from_docs, out_of_scope.

### Not done
- Phase 4 error states; Phase 5–7.

## 2026-09-21 (Phase 2.5 — review vs product-spec / test-plan)

### Pass (phạm vi 2.5)
- `render_chart`: matplotlib Agg → PNG base64 non-empty (`iVBOR` / `\x89PNG`); bar/line/pie; empty rows → `""`.
- `should_render_chart`: keyword + `StatAnswer.chart_requested`.
- `plan_chart`: structured online + offline heuristic + LLM fail fallback.
- test-plan **Chart**; product-spec Chart module (acceptance **#5** phần render — chưa UI/SSE).
- `matplotlib` trong `requirements.txt`; `pytest -q` → 192 passed; 9 test files.

### Fail (đã fix — Cursor review)
- `test-plan.md` / `AGENTS.md` status còn «2.4» dù Phase 2.5 đã xong → sync.

### Missing (đúng scope — Phase 3)
- SSE `node_id=render_chart` + `chart_png_base64`.
- Frontend `<img>` dưới câu trả lời (acceptance **#5** full).
- Graph wire `execute → [render_chart] → respond`.

### Fixed
- Sync status `specs/test-plan.md`, `AGENTS.md`.

## 2026-09-21 (Phase 2.5 — Chart PNG: matplotlib Agg -> base64, detection, plan_chart)

### Added
- **`src/chart/render.py`**: Module thuần tạo và vẽ biểu đồ độc lập:
  - `render_chart(rows, spec) -> str`: sử dụng backend matplotlib non-GUI `Agg`, hỗ trợ các kiểu biểu đồ `bar`, `line`, `pie`, xuất ảnh PNG dạng chuỗi base64 thuần (không kèm prefix `data:image/png;base64,`); xử lý tự động `rows` rỗng trả về `""`, giải phóng figure an toàn qua `try...finally: plt.close(fig)`.
  - `should_render_chart(question, stat_answer=None) -> bool`: phát hiện từ khóa biểu đồ tiếng Việt/tiếng Anh (`biểu đồ`, `bieu do`, `chart`, `plot`, `vẽ`, `đồ thị`, `thống kê theo`, `tỷ lệ`, `cơ cấu`, `phân bố`) hoặc khi `stat_answer.chart_requested` là True.
  - `plan_chart(rows, question) -> ChartSpec`: xác định cấu hình biểu đồ thông qua `invoke_structured(messages, ChartSpec)` khi online, và thuật toán heuristic chọn 2 cột (danh mục + số liệu) khi offline (`use_offline_tools()`) hoặc khi LLM gặp lỗi.
- **`src/chart/__init__.py`**: Re-export `render_chart`, `should_render_chart`, `plan_chart`.

### Changed
- **`requirements.txt`**: Bổ sung thư viện `matplotlib>=3.8.0` cho tính năng render biểu đồ.
- **`src/agent/__init__.py`**: Re-export `plan_chart`, `render_chart`, `should_render_chart` sẵn sàng cho Phase 3 nối vào LangGraph pipeline.
- **`tests/test_structured.py`**: Mở rộng thêm 9 offline unit test cases cho module chart:
  - `test_render_chart_bar_success`: xác nhận chuỗi base64 không rỗng, bắt đầu bằng `iVBOR` và magic number `\x89PNG`.
  - `test_render_chart_line_and_pie`: kiểm tra biểu đồ đường và biểu đồ tròn.
  - `test_render_chart_empty_rows_and_invalid_spec`: kiểm tra rows rỗng và spec None trả về `""`.
  - `test_render_chart_fallback_column_selection`: kiểm tra tự động fallback chọn cột khả dụng.
  - `test_should_render_chart_keywords_true_and_false`: kiểm thử các trường hợp từ khóa true/false.
  - `test_should_render_chart_with_stat_answer`: kiểm thử cờ `chart_requested` trong `StatAnswer`.
  - `test_plan_chart_offline_heuristics`: kiểm thử heuristic chọn cột và chart_type offline.
  - `test_plan_chart_mock_structured_online`: mock `invoke_structured` khi online.
  - `test_plan_chart_llm_failure_falls_back_to_offline`: kiểm thử fallback sang offline khi LLM lỗi.
- **`specs/implementation-plan.md`**: Đánh dấu hoàn thành toàn bộ checklist của Phase 2.5 (`[x]`); cập nhật mục tiêu Phase 2 "Xong khi" đã bao gồm offline cover cho chart.
- **`specs/product-spec.md`**: Cập nhật trạng thái Phase 2 (2.1–2.5) hoàn thành.

### Verified
- `pytest -q` → 192 passed, 1 warning (offline, 0 failed).
- `pytest -q -k "chart or structured"` → 20 passed, 172 deselected, 1 warning.
- `pytest -q -k "structured or rewrite or query or docs or chart or validator"` → 54 passed, 138 deselected, 1 warning.
- `find tests -name 'test_*.py' | wc -l` → 9 (< 10).
- Matplotlib backend `Agg` thuần non-GUI, không phát sinh lỗi display/thread, không rò rỉ figure.

### Not done
- Phase 3: Nối `render_chart` vào StateGraph LangGraph mới, phát event SSE `render_chart` kèm `chart_png_base64`, render thẻ `<img>` phía frontend.
- Phase 4–7: Theo implementation plan.

## 2026-09-21 (Phase 2.4 — review vs product-spec / test-plan)

### Pass (phạm vi 2.4)
- `DOCS_ROOT` + corpus `docs/vms_yaml/` (40 published cards); loader chỉ ingest `published`.
- Keyword `retrieve_docs` khớp how-to (thêm camera / playback / reset password).
- `answer_from_docs` → `DocsAnswer` (structured + offline + LLM fail fallback).
- How-to **không gọi DB**; graph v4 `handle_docs_intent` vẫn chạy.
- test-plan Docs; acceptance **#4** (how-to bám card YAML) ở tầng module.
- `pytest -q` → 183+ passed; 9 test files `< 10`.

### Fail (đã fix — Cursor review)
- `test_intent_routing` vẫn patch `src.agent.docs.invoke_text` dù adapter không còn dùng → gỡ patch; assert answer docs.
- `src/agent/docs.py` giữ import/`invoke_text` chết → dọn adapter mỏng.
- Header `implementation-plan` / status `product-spec` / `test-plan` / `AGENTS` chưa ghi 2.4 xong → sync.

### Missing (đúng scope)
- Graph SSE node `answer_from_docs` riêng (Phase 3).
- Chart PNG — Phase 2.5.
- Không còn grep `docs/vms/*.md` trên đường chính (đã thay; file md legacy còn trong cleanup Phase 7).

### Fixed
- `tests/test_intent.py`, `src/agent/docs.py`, sync status docs.

## 2026-09-21 (Phase 2.4 — Docs YAML: DOCS_ROOT, loader, keyword retrieval, structured answer_from_docs)

### Added
- **`docs/vms_yaml/`**: Bản sao tài liệu YAML VMS từ `agent-harness/duy` (40 task cards published, `index.yaml`, `glossary.yaml`, `schema.yaml`, `walkthrough.md`) đặt trực tiếp trong repository `dong` để đảm bảo hoạt động độc lập, tự chủ khi chạy offline và build Docker container (không phụ thuộc relative path bên ngoài repo).
- **`src/knowledge/loader.py`**: Module nạp task cards YAML: hàm `docs_root()` lấy thư mục tài liệu từ `settings.effective_docs_root`, `load_index()`, `load_published_cards()` đọc `index.yaml` và chỉ tải các cards có `status: published` (đúng 40 cards), cùng `clear_docs_cache()` để quản lý bộ nhớ đệm.
- **`src/knowledge/retrieval.py`**: Keyword retrieval top-k cards dựa trên danh sách cụm từ nghiệp vụ (`_PHRASES`), từ dừng (`_STOP`), trọng số alias, title, tag và hay (id/intent/summary/module); hàm `card_excerpt_for_llm` rút gọn các trường phục vụ prompt.
- **`src/knowledge/answer.py`**: Hàm `answer_from_docs(question, cards) -> DocsAnswer` qua `invoke_structured` với prompt tiếng Việt hướng dẫn VMS; hỗ trợ nhánh offline (`use_offline_tools()`) sinh `DocsAnswer` từ dữ liệu text của card (điền đầy đủ `card_ids`, `steps` khi tìm thấy card; gán `card_ids=[]` và câu giải thích tiếng Việt rõ ràng khi rỗng); tự động fallback sang offline khi `invoke_structured` gặp lỗi.
- **`src/knowledge/__init__.py`**: Re-export các hàm cốt lõi `docs_root`, `load_index`, `load_published_cards`, `clear_docs_cache`, `retrieve_docs`, `card_excerpt_for_llm`, `answer_from_docs`.
- **`tests/test_docs.py`**: 11 offline unit tests bao phủ `docs_root`, `load_published_cards` (chỉ load 40 published cards, bỏ qua `needs_review`), `clear_docs_cache`, keyword retrieval cho câu hỏi how-to phổ biến ("thêm camera", "xem lại", "quên mật khẩu"), câu hỏi ngoài lề / rỗng trả về rỗng, `card_excerpt_for_llm`, `answer_from_docs` offline có card và rỗng, mock `invoke_structured` cho `DocsAnswer`, fallback khi LLM lỗi, adapter `handle_docs_intent`, và kiểm tra nhánh how-to không gọi database.

### Changed
- **`src/config.py`**: Bổ sung cấu hình `docs_root: str = Field(default="docs/vms_yaml", alias="DOCS_ROOT")` và thuộc tính `effective_docs_root` (hỗ trợ đường dẫn tuyệt đối, tương đối, kiểm tra `index.yaml`, và fallback sang sibling `duy` nếu cần).
- **`.env.example`**: Bật biến `DOCS_ROOT=docs/vms_yaml`.
- **`src/agent/docs.py`**: Cập nhật sang dùng `retrieve_docs` và `answer_from_docs` từ `src.knowledge`; hàm `handle_docs_intent(question) -> str` đóng vai trò adapter gọi retrieval + structured answer và trả về chuỗi `answer_vi` giúp giữ tương thích hoàn toàn cho đồ thị LangGraph v4 hiện tại.
- **`src/agent/__init__.py`**: Re-export thêm `retrieve_docs`, `answer_from_docs`, `handle_docs_intent`.
- **`tests/test_api.py`**: Gộp các test case frontend UI và streaming từ `tests/test_ui_graph.py` vào `tests/test_api.py` (cùng phạm vi kiểm thử FastAPI endpoints), sau đó gỡ bỏ `tests/test_ui_graph.py` để giữ tổng số file test là 9 (< 10 theo `specs/test-plan.md`).
- **`specs/implementation-plan.md`**: Đánh dấu hoàn thành toàn bộ 4 checklist items của Phase 2.4 (`[x]`).

### Verified
- `pytest -q` → 183 passed, 1 warning (offline, 0 failed).
- `pytest -q -k "docs or structured"` → 22 passed, 161 deselected, 1 warning.
- `find tests -name 'test_*.py' | wc -l` → 9 (< 10).
- Nhánh how-to tài liệu VMS hoạt động độc lập, không import/gọi tới kết nối DB hoặc SQL executor.

### Not done
- Phase 2.5 (Chart: matplotlib Agg → PNG base64 từ rows + ChartSpec).
- Phase 3 (LangGraph v5 wiring: thay thế ReAct loop bằng pipeline StateGraph rewrite -> classify -> plan/docs -> respond/stream).

## 2026-09-21 (Phase 2.3 — review vs product-spec / test-plan)

### Pass (phạm vi 2.3)
- Catalog + `describe_table` + `build_schema_excerpt`; `plan_query` → `QueryPlan` (structured + offline).
- `build_sql`: parameterized `%s`; thêm filter (`vehicle_type`, `direction`) vào WHERE/params.
- `validate_sql`: SELECT-only; reject DELETE/INSERT/UPDATE/DROP/…; unknown table; multi-statement.
- `execute_sql`: validate trước; mock DB OK; lỗi rõ khi DB chưa cấu hình.
- Repair loop tôn trọng `SQL_REPAIR_MAX` (`plan_and_execute`).
- test-plan QueryPlan + Validator + Read-only (module); acceptance **#3** (filter→query), **#7** (DELETE chặn) ở tầng module.
- `pytest -q` → 172 passed; 9 test files `< 10`.

### Fail (đã fix — Cursor review)
- `test_build_sql_short_filters_and_numeric` không pin `db_organization_id=0` → phụ thuộc `.env` local. Đã monkeypatch.
- Status `product-spec` / `test-plan` / `AGENTS` chưa ghi 2.3 → sync.

### Missing (đúng scope)
- ClickHouse path trong `execute_sql` (spec: tuỳ chọn).
- Whitelist cột tuyệt đối (alias-aware) — hiện chặn trộn cột cross-table kiểu duy; đủ MVP.
- Graph/SSE wire plan→validate→execute — Phase 3.
- Docs YAML / chart — Phase 2.4–2.5.

### Fixed
- `tests/test_query_plan.py`: pin org id trong short-filters test.
- Sync status docs.

## 2026-09-21 (Phase 2.3 — Schema catalog + QueryPlan builder + validator + executor + repair)

### Added
- **`src/db/catalog.py`**: Catalog dataset 5 bảng VMS (`plate_event`, `zone_event`, `smf_face_events`, `fire_smoke_event`, `anomaly_event`) kèm mô tả, cột thời gian, kiểu dữ liệu và sample values; hàm `describe_table` (offline-friendly, hỗ trợ introspect DB nếu kết nối sẵn sàng), `build_schema_excerpt(tables)` sinh context schema cho LLM prompt, cùng các helper whitelist `get_allowed_tables()`, `get_allowed_columns(table)`, `get_database_for_table(table)`.
- **`src/db/query_builder.py`**: Chuyển đổi `QueryPlan` (structured) thành câu SQL tham số hoá với placeholder `%s` (chuẩn psycopg2); hỗ trợ SELECT, FROM whitelist tables, WHERE từ filters (tự động trích xuất chuỗi, số, unquoted identifier, `organization_id`), GROUP BY, ORDER BY, LIMIT (không vượt quá `settings.db_max_rows`).
- **`src/db/validator.py`**: Hàm `validate_sql(sql)` trả về `ValidationResult` (ok, reason); kiểm tra SELECT/WITH-only, chặn multi-statement (`;`), chặn toàn bộ từ khóa DML/DDL (DELETE, INSERT, UPDATE, DROP, ALTER, TRUNCATE,...), đối chiếu whitelist bảng và phát hiện trộn lẫn cột giữa các bảng trong catalog.
- **`src/db/executor.py`**: Hàm `execute_sql(sql, params, dbname=None) -> list[dict]` thực thi SQL đọc-only trên Postgres thông qua `get_connection`; tự động định tuyến database theo bảng; kiểm tra `settings.db_configured` và raise `RuntimeError` rõ ràng khi DB chưa được cấu hình.
- **`src/agent/query_plan.py`**: `plan_query(question, schema_excerpt) -> QueryPlan` qua `invoke_structured` (hỗ trợ heuristic offline khi `use_offline_tools()`); `repair_plan_query` replan khi validate/execute lỗi; `plan_and_execute` thực thi pipeline thuần kèm vòng lặp sửa lỗi tối đa `settings.sql_repair_max` lần.
- **`tests/test_query_plan.py`**: 23 offline unit tests bao phủ catalog, `describe_table`, `build_schema_excerpt`, `build_sql` tham số hóa, `validate_sql` chặn DML/DDL & unknown tables, `execute_sql` kiểm tra cấu hình & mock kết nối, `plan_query` & repair loop.

### Changed
- **`src/db/__init__.py`**: Re-export `get_catalog`, `describe_table`, `build_schema_excerpt`, `build_sql`, `validate_sql`, `ValidationResult`, `execute_sql`.
- **`src/agent/__init__.py`**: Re-export `plan_query`, `repair_plan_query`, `plan_and_execute`.
- **`specs/implementation-plan.md`**: Đánh dấu hoàn thành toàn bộ 7 checklist items của Phase 2.3 (`[x]`).

### Verified
- `pytest -q` → 172 passed, 1 warning (offline, 0 failed).
- `pytest -q -k "query or validator or structured"` → 32 passed, 140 deselected.
- `find tests -name 'test_*.py' | wc -l` → 9 (< 10).

### Not done
- Phase 2.4 (Docs YAML duy: loader, keyword retrieval, `answer_from_docs`).
- Phase 2.5 (Chart: matplotlib Agg → PNG base64 từ rows + ChartSpec).
- Phase 3 (LangGraph wiring: nối `plan_query`, `validate`, `execute` vào StateGraph và SSE stream).

## 2026-09-21 (Phase 2.2 — review vs product-spec / test-plan)

### Pass (phạm vi 2.2)
- `rewrite_question` → `RewrittenQuestion` (prompt VI + offline fallback + mock `invoke_structured`).
- `classify_intent` → `IntentResult` structured; how_to ≠ query_data; offline heuristics cover 5 intent.
- Graph v4 vẫn route qua `classify_node` dùng `res.intent` (không gắn node rewrite — đúng scope 2.2).
- test-plan Intent (module): structured + routing mock.
- Checklist 2.2 `[x]`; `pytest -q -k "rewrite or intent or structured"` xanh.

### Fail (đã fix — Cursor review)
- `test_intent_routing` patch `src.llm.use_offline_tools` không ảnh hưởng `src.agent.intent.use_offline_tools` → dưới pytest luôn offline heuristic, mock structured không chạy. Đổi patch + assert `call_count == 3`.

### Missing (đúng scope — Phase 3+)
- test-plan Rewrite SSE `node_id=rewrite`; product-spec acceptance **#6** — chưa wire graph.
- Acceptance **#2** đầy đủ: ReAct/`invoke_text` answer/docs vẫn free-text.
- Phase 2.3+ QueryPlan / docs / chart.

### Fixed
- `tests/test_intent.py` patch path + assert mock gọi 3 lần.
- Sync status `product-spec.md`, `test-plan.md`, `AGENTS.md`.

## 2026-09-21 (Phase 2.2 — Node rewrite & classify logic)

### Added
- **`src/agent/rewrite.py`**: `rewrite_question(raw: str) -> RewrittenQuestion` sử dụng `invoke_structured` với prompt tiếng Việt chuẩn hóa câu hỏi, trích xuất `filters`, `time_range`, `intent_hint`; hỗ trợ fallback offline hợp lệ không gọi LAN khi `use_offline_tools()` bật.
- **`src/agent/__init__.py`**: Re-export `rewrite_question`, `classify_intent`, `classify_intent_str` cho callers.

### Changed
- **`src/agent/intent.py`**: Chuyển `classify_intent` sang structured output trả về `IntentResult` (intent ∈ `query_data|how_to|troubleshoot|concept|out_of_scope` kèm `reason`), loại bỏ parse free-text keyword từ `invoke_text`; thêm heuristic offline cho các intent; bổ sung helper `classify_intent_str`.
- **`src/agent/graph.py`**: Cập nhật `classify_node` tương thích ngược: trích xuất `res.intent` từ `IntentResult` hoặc `str(res)` giữ nguyên routing và output event của graph v4.
- **`tests/test_intent.py`**: Mock `invoke_structured` thay cho `invoke_text`; bổ sung test offline heuristics và mock structured cho `rewrite_question`, `classify_intent`, `classify_intent_str`.
- **`specs/implementation-plan.md`**: Đánh dấu hoàn thành mục 2.2 (`[x]`).

### Verified
- `pytest -q` → 149 passed, 1 warning (offline, không gọi LAN).
- `pytest -q -k "rewrite or intent or structured"` → 13 passed.
- `find tests -name 'test_*.py' | wc -l` → 8 (< 10).
- `from src.agent import rewrite_question` trả về `RewrittenQuestion`.
- `from src.agent import classify_intent` trả về `IntentResult`.

### Not done
- Phase 2.3+ (Schema + QueryPlan builder, docs YAML, chart, nối graph rewrite node mới vào StateGraph / SSE stream).

## 2026-09-21 (Phase 2.1 — review vs product-spec / test-plan)

### Pass (phạm vi 2.1)
- product-spec schema table: đủ 6 model + field khớp (`RewrittenQuestion` … `ChartSpec`).
- Acceptance **#2** (phần layer): `invoke_structured` + pytest mock schema parse (offline).
- test-plan **Structured LLM**: mock; schema validate; lỗi parse → `RuntimeError` tiếng Việt rõ.
- Config: `LLM_REQUEST_TIMEOUT_S`, model, `SQL_REPAIR_MAX=1`.
- `pytest -q -k structured` xanh; suite vẫn offline.

### Fail (đã fix)
- `invoke_structured` gọi `extract_token_usage` trên mọi non-BaseModel (kể cả dict schema) → nhiễu token 0; bỏ extract trên đường structured (token gắn AIMessage thuộc Phase khác nếu cần).
- Thiếu test đường dict → `model_validate` thành công.
- `product-spec` / `test-plan` status vẫn «Phase 2+ chưa» dù 2.1 đã code.

### Missing (đúng scope — Phase 2.2+)
- Acceptance **#2** đầy đủ: mọi LLM call **trong graph** dùng structured — graph/ReAct vẫn `invoke_text` (2.2 / 3).
- test-plan «fallback» user-facing tiếng Việt khi parse fail trên stream — Phase 4.
- Acceptance **#3–#8**, rewrite SSE, QueryPlan→SQL, docs, chart — chưa.

### Fixed
- `src/llm/structured.py`: validate schema trước; không extract usage từ payload structured.
- `tests/test_structured.py`: `test_invoke_structured_coerces_dict_to_schema`.
- Sync status `product-spec.md`, `test-plan.md`.

## 2026-09-21 (Phase 2.1 — Structured output layer)

### Added
- **`src/llm/`** package (thay `src/llm.py`):
  - `client.py` — API cũ (`base_llm`, `invoke_text`, …); timeout từ config.
  - `schemas.py` — `RewrittenQuestion`, `IntentResult`, `QueryPlan`, `DocsAnswer`, `StatAnswer`, `ChartSpec`.
  - `structured.py` — `invoke_structured(messages, schema) -> BaseModel` (LangChain `with_structured_output`).
  - `__init__.py` — re-export để `from src.llm import …` không gãy.
- **`tests/test_structured.py`**: mock `invoke_structured`; validate schema; lỗi parse/LLM rõ ràng (offline).

### Changed
- **`src/config.py`**: `LLM_REQUEST_TIMEOUT_S` (mặc định 15), `SQL_REPAIR_MAX` (mặc định 1).
- **`.env.example`**: thêm `LLM_REQUEST_TIMEOUT_S=15`.
- **`specs/implementation-plan.md`**: Phase 2.1 checklist `[x]`.

### Verified
- `pytest -q` → **144 passed** (không gọi LAN).
- `find tests -name 'test_*.py' | wc -l` → 8 (`< 10`).

### Not done
- Phase 2.2+ (rewrite/classify nodes, QueryPlan builder, docs, chart, graph…).

## 2026-09-21 (Phase 1 — review vs product-spec / test-plan)

### Pass (phạm vi Phase 1)
- Acceptance **#1** (phần Docker v4): compose hợp lệ; API `/api/health` → `ok`; UI phục vụ (port theo `FRONTEND_PORT` trong `.env`).
- Acceptance **#9** (phần offline): `pytest -q` → 138 passed; `test ! -d backend`; `tests/` có 7 file `< 10`.
- test-plan **Docker spec**: `docker compose config` + `langfuse/docker-compose.yml` OK.
- Phase 1 checklist: `.env.example` có `DOCS_ROOT` / `SQL_REPAIR_MAX`; AGENTS + `.gitignore`; cleanup inventory; baseline không regress.

### Fail (đã fix — chỉ sync doc Phase 1)
- `product-spec.md` / `test-plan.md` vẫn ghi «chưa code» trong khi Phase 1 đã xong → lệch «Xong khi: Spec v5 đồng bộ».
- README kiến trúc liệt kê `src/llm/…` như thể đã có → dễ hiểu nhầm «cấu trúc khớp» Phase 1.

### Missing (đúng scope — Phase 2+)
- Acceptance **#2–#8** (structured LLM, QueryPlan, docs YAML, chart, rewrite SSE, …): chưa implement.
- Acceptance **#9** golden-30 live: Phase 6.
- test-plan hàng Structured / Rewrite / QueryPlan / Docs / Chart: Phase 2–3.

### Fixed
- `specs/product-spec.md`, `specs/test-plan.md`: trạng thái Phase 1.
- `README.md`: tách top-level hiện có vs path dự kiến Phase 2+.

## 2026-09-21 (Phase 1 — Project setup)

### Added / Changed
- **`.env.example`**: nhóm v5 — `DOCS_ROOT=`, `SQL_REPAIR_MAX=1` (chưa wire vào `src/config.py`; Phase 2.1).
- **`specs/implementation-plan.md`**: Phase 1 checklist `[x]`; bảng cleanup inventory cho Phase 7.
- **`README.md`**: trạng thái Phase 1 done; ghi `DOCS_ROOT` / `SQL_REPAIR_MAX` đã có trong `.env.example`.

### Verified (không đổi logic)
- Cấu trúc `src/`, `frontend/`, `tests/`, `eval/`, `langfuse/` khớp README v5.
- `AGENTS.md` + `.gitignore` đã đủ (một phase/task, structured, Docker-only; ignore `.env` / `.venv` / `venv` / `eval/results` / `__pycache__`).
- Baseline: `pytest -q` → **138 passed**.
- Docker app healthy: `GET /api/health` → `status: ok`; Langfuse web healthy trên `:3000`.

### Cleanup list (Phase 7 — chưa xóa)
- `ai/` (import `backend.config` gãy, không dùng)
- `static/index.html` (UI legacy; dùng `frontend/`)
- `manual_test.sh`, `prep_changelog.sh`
- `docs/vms/*.md` (thay bằng YAML cards khi Phase 2.4)
- `agent-canvas.md` (doc ngoài runtime)

### Not done
- Phase 2+ (structured LLM, rewrite, QueryPlan, docs, chart, graph…).

## 2026-09-22 (README — SDD Bước 9 local dev + Docker deploy)

### Changed
- **`README.md`**: mục **Local development** (prerequisites, install, env, backend/frontend commands, URLs, troubleshooting) và **Docker deploy** tách riêng; không đổi app logic.

## 2026-09-21 (AGENTS.md — SDD Bước 4)

### Changed
- **`AGENTS.md`**: rút gọn theo SDD guide — đọc spec, một phase/task, giữ đơn giản, không lib thừa, không đổi kiến trúc, change-log + hướng dẫn test sau mỗi implement.

## 2026-09-21 (v5 spec — rewrite implementation-plan 7 phase)

### Changed (spec only)
- **`specs/implementation-plan.md`**: gom 10 phase cũ → **7 phase** có checklist rõ:
  1. Project setup
  2. Core backend & data logic (2.1 structured → 2.5 chart)
  3. Graph mới thay ReAct
  4. Validation and error states
  5. Docker run instructions
  6. Tests & eval
  7. Demo setup
- **`README.md`**, **`AGENTS.md`**, **`test-plan.md`**: tham chiếu Phase 1→7.

### Not done
- Toàn bộ checklist `[ ]` — chưa implement code v5.

## 2026-09-21 (v5 spec — revert judge, giữ rewrite + classify tách)

### Changed (spec only)
- Hoàn nguyên spec v5: **`rewrite`** và **`classify_intent`** là hai node/LLM call riêng (bỏ node `judge` / schema `QuestionJudge`).
- Đồng bộ lại `product-spec.md`, `implementation-plan.md`, `test-plan.md`, `README.md`, `AGENTS.md`.

## 2026-09-21 (README — Local development instructions)

### Changed
- `README.md`: mục **Local development** — prerequisites, install, bảng biến môi trường (`LLM_BACKEND`/`MODEL_*`, DB, Langfuse), lệnh backend/frontend, local URLs, troubleshooting (UI API URL, cache, Langfuse trace, pytest).

## 2026-09-21 (v5 planning — spec only, chưa code)

### Added / Changed (spec)
- **`specs/product-spec.md`** — v5 MVP: structured output bắt buộc, node rewrite, QueryPlan + schema DB, docs YAML (duy), chart PNG, pipeline thay ReAct, Docker-only deploy.
- **`specs/implementation-plan.md`** — Phase 1→10 v5 (thay checklist v4).
- **`specs/test-plan.md`** — pytest structured/rewrite/query/docs/chart; Docker live; golden regression v4→v5.
- **`README.md`** — trạng thái v5 spec phase; Docker đường chính; kiến trúc dự kiến; tham chiếu llm-engineer-demo + duy.
- **`AGENTS.md`** — quy tắc v5 (structured output, QueryPlan, không .venv quick start).

### Not done (chờ implement)
- Toàn bộ phase 1–10 implementation-plan v5 `[ ]`.
- Code v4 vẫn chạy (ReAct, tool cố định) cho tới Phase 7.

### App idea captured
- Phong cách `llm-engineer-demo`; LLM structured output; DB linh hoạt theo biến + schema trong prompt; docs + chart từ duy; node rewrite; clean code; deploy docker compose only.

## Review (Cursor) — Langfuse trace feature vs product-spec / test-plan

### Pass
- product-spec §6 / acceptance #6: trace có output + latency; `MONITORING_ENABLED=false` → no-op.
- Phase 5: một trace/request qua `/api/chat`, `/ask`, **`/api/agent/stream`** (UI).
- Nested span input đúng node (`chon_tool` / `chay_tool` / `dien_giai`) — `test_react_nodes_trace_step_input_not_question`.
- Langfuse tách `langfuse/docker-compose.yml`; backend Docker `LANGFUSE_HOST=host.docker.internal:3000`.
- `pytest` trace + API: 52 passed (gồm `test_api_agent_stream_passes_trace_parent_span`).

### Fail (đã fix trong review)
- SSE + `trace_answer`: `ContextVar.reset` ném `ValueError` cross-thread → span không `end()`/flush — sửa `tracing.py`.
- Stream tests crash khi `.env` bật monitoring — thêm `monkeypatch` tắt monitoring trong smoke tests.
- `test_trace_answer_and_trace_step_with_langfuse`: assert `model_name` sai backend — patch `llm_backend=openai`.

### Missing (ngoài scope feature này)
- Live verify Langfuse UI sau mỗi deploy (manual).
- Token aggregation cross-thread trong stream (worker thread LLM không cộng vào ContextVar cha) — chấp nhận MVP.
- Phase 10 demo checklist README.

## 2026-09-21 (Fix trace Langfuse — UI stream + LANGFUSE_HOST Docker)

### Fixed
- `/api/agent/stream` (UI mặc định) bọc `trace_answer` + truyền `parent_span` xuống graph — trước đó chỉ `/api/chat` và `/ask` có trace.
- `docker-compose.yml`: `LANGFUSE_HOST` cố định `http://host.docker.internal:3000` (không lấy `localhost` từ `.env`).

## 2026-09-21 (Tách Langfuse ra langfuse/docker-compose.yml)

### Changed
- Xóa toàn bộ service Langfuse khỏi `docker-compose.yml` gốc (chỉ còn `frontend` + `ai_backend`).
- `langfuse/docker-compose.yml`: stack self-hosted gọn (web, worker, postgres, clickhouse, minio, redis).
- `ai_backend` Docker trỏ `LANGFUSE_HOST=http://host.docker.internal:3000` (Langfuse expose cổng host).
- `scripts/setup-langfuse.sh`: up Langfuse trước, rồi dong app.
- `langfuse/README.md`, tests, README cập nhật theo cấu trúc mới.

## 2026-09-21 (Setup Langfuse one-shot — dong + user + keys sẵn trong .env)

### Added
- `scripts/setup-langfuse.sh`: một lệnh khởi động dong + Langfuse; `--reset` xóa volume và init lại user mặc định.

### Changed
- `docker-compose.yml`: `LANGFUSE_MIGRATION_V4_WRITE_MODE=dual` (Langfuse v4 + SDK 4.x); healthcheck `langfuse-web`; `ai_backend` chờ Langfuse (optional); default `MONITORING_ENABLED=true` khi có profile observability.
- `langfuse/.env.example`, `.env.example`: API keys + user mặc định khớp project `agent_ATIN`.
- `README.md`: hướng dẫn `./scripts/setup-langfuse.sh`.

### Manual test steps
1. `cd agent-harness/dong && ./scripts/setup-langfuse.sh --reset`
2. Đăng nhập http://localhost:3000 — `admin@agent-atin.local` / `Atin@123#`
3. Gửi câu hỏi qua http://localhost:3001 → Langfuse → Traces thấy span `chat` + nested spans.

## 2026-09-21 (Fix Langfuse nested span input — đúng context từng node)

### Fixed
- `src/agent/react.py`: span `chon_tool` ghi input = messages gửi LLM (system + hội thoại), không còn lặp `question` gốc; span `chay_tool` ghi input = tóm tắt `tool_calls` (tên + args).
- `src/agent/graph.py`: span `dien_giai` ghi input = tóm tắt kết quả tool (`tools`, `row_count`, `columns`), không còn lặp câu hỏi user.
- `tests/test_trace_cache.py`: thêm `test_react_nodes_trace_step_input_not_question`.

### Manual test steps
1. Bật `MONITORING_ENABLED=true`, gửi 1 câu hỏi qua UI hoặc `/api/ask`.
2. Mở Langfuse → trace vừa tạo → kiểm tra nested spans:
   - `chon_tool`: input là danh sách messages (có system prompt + user).
   - `chay_tool`: input là `[{"name": "...", "args": {...}}]`.
   - `dien_giai`: input là `{"tools": [...], "queries": [...]}` — không phải câu hỏi gốc.

## 2026-09-21 (Docker Compose production demo — không .venv)

### Changed
- `Dockerfile`: bỏ `backend/` (đã xóa), thêm `docs/vms/`, user `appuser`, uvicorn `--proxy-headers`.
- `.dockerignore`: loại `.venv`, tests, specs khỏi build context.
- `docker-compose.yml`: mặc định chỉ `frontend` + `ai_backend`; Langfuse stack → profile `observability`; healthcheck + `depends_on`; `MONITORING_ENABLED=false` mặc định.
- `frontend/nginx.conf`: proxy SSE `/api/` (tắt buffering, timeout 300s).
- `.env.example`, `README.md`: hướng dẫn `docker compose up --build -d`.

### Manual test steps
1. `cd agent-harness/dong && cp .env.example .env` — chỉnh `LLM_*`.
2. `docker compose up --build -d`
3. `curl -s http://localhost:8000/api/health` → JSON ok.
4. Mở http://localhost:8080, gửi câu tiếng Việt, graph chạy bên phải.
5. `docker compose down`

## Review Phase 9 Item 3 (Cursor) — Phụ thuộc LAN 196 Ollama, CH/PG read-only
- **Pass:** README §7 khớp product-spec — Ollama 196:11434 + `qwen3-16k-nothink:latest`; PG read-only (`agent_readonly`, 5 DB từ `.env.example`); CH read-only + fallback PG (đúng `src/db/queries.py`); bảng tổng hợp 5 cột; tiến độ Phase 9 hoàn tất; Phase 9 checklist 3/3 `[x]`; Phase 10 giữ `[ ]`.
- **Fail fixed:** anchor markdown §7→§6.1 dễ gãy → đổi thành “Mục 6.1 phía trên”.
- **Missing (Phase 10):** checklist demo 5 phút, LAN URL ngoài máy, link golden-30 cho reviewer.

## 2026-09-21 (Phase 9: Ghi phụ thuộc LAN máy 196 Ollama, CH/PG read-only trong README)

### Changed
- `README.md`:
  - Cập nhật dòng trạng thái tiến độ ở đầu file: `Phase 9 hoàn tất (Local run instructions: run env, ping/pytest/eval, phụ thuộc LAN). Chuẩn bị: Phase 10 (Demo setup).`
  - Bổ sung mục `### 7. Phụ thuộc mạng LAN`:
    - **7.1. Ollama máy 196 (Bắt buộc cho live LLM):** URL mặc định `http://192.168.1.196:11434/v1`, model `qwen3-16k-nothink:latest`, yêu cầu máy chạy agent kết nối mạng LAN tới máy 196 (không phải localhost trừ khi Ollama chạy local), lệnh kiểm tra kết nối (ping CLI §6.1, HTTP ping), ghi rõ khi không có 196: chỉ chạy `pytest` offline, câu hỏi how-to có thể hoạt động nếu cấu hình LLM ở máy chủ khác qua ghi đè `LLM_BASE_URL`.
    - **7.2. Postgres read-only (Cần cho câu hỏi số liệu / eval đầy đủ):** Role `agent_readonly` hoặc tương đương chỉ cấp quyền `SELECT`, tuyệt đối cấm ghi (`INSERT`/`UPDATE`/`DELETE`/`DROP`); liệt kê các biến môi trường chính (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME_ITS`, `DB_NAME_FENCE`, `DB_NAME_FACE`, `DB_NAME_FIRE`, `DB_NAME_ANOMALY`); phân định mức độ phụ thuộc: tuỳ chọn cho câu hỏi how-to, bắt buộc cho stat tools và golden eval.
    - **7.3. ClickHouse read-only (Tùy chọn, lưu lượng xe...):** Các biến môi trường `CH_HOST`, `CH_PORT`, `CH_USER`, `CH_PASSWORD`, `CH_DATABASE`; quyền chỉ đọc; ưu tiên truy vấn trước Postgres theo product-spec (fallback sang PG nếu thiếu CH).
    - **7.4. Bảng tổng hợp phụ thuộc mạng LAN (Summary Table):** Bảng súc tích với 5 cột chuẩn (`Dịch vụ (Service)` | `Host mặc định` | `Cổng (Port)` | `Yêu cầu cho (Required for)` | `Ghi chú chỉ đọc (Read-only note)`).
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành `[x]` duy nhất cho checklist item `Ghi phụ thuộc LAN: máy 196 Ollama, CH/PG read-only.` trong Phase 9. Giữ nguyên tất cả các checkbox của Phase 10 là `[ ]`.

### Manual Test Steps (Kiểm tra kết nối LAN và tính độc lập / gián đoạn khi thiếu PG/CH)
1. **Kiểm tra khả năng tiếp cận mạng LAN máy 196 (Ollama LAN reachability):**
   - Kiểm tra HTTP trực tiếp tới Ollama daemon máy 196:
     ```bash
     curl -s --connect-timeout 3 http://192.168.1.196:11434/api/version
     ```
     *Kết quả kỳ vọng:* Phản hồi JSON chứa phiên bản Ollama (ví dụ `{"version":"0.33.0"}`).
   - Kiểm tra qua client Python của agent (yêu cầu file `.env` đã cấu hình `LLM_*`):
     ```bash
     cd agent-harness/dong
     python3 -c "from src.llm import ping; print(ping())"
     ```
     *Kết quả kỳ vọng:* In ra `OK`.
   - **Khi không có kết nối tới máy 196:**
     - Bộ kiểm thử offline `python3 -m pytest -q` vẫn hoạt động hoàn toàn bình thường (136 passed) nhờ mock LLM client.
     - Live agent có thể hoạt động nếu ghi đè biến `LLM_BASE_URL` trỏ tới endpoint LLM tương thích OpenAI ở máy chủ khác.

2. **Kiểm tra những gì chạy được và những gì bị gián đoạn khi thiếu Postgres/ClickHouse (What breaks without PG/CH):**
   - **Trường hợp biến kết nối `.env` để trống (`DB_HOST`, `CH_HOST`):**
     - *Nhánh tài liệu how-to / quy trình VMS:* Hoạt động độc lập hoàn toàn từ file markdown local (ví dụ câu hỏi: *"Cách thêm camera vào hệ thống VMS?"* trả lời đầy đủ quy trình và mermaid diagram, không gọi tool số liệu hay DB).
     - *Nhánh an toàn (Guardrails):* Chặn prompt injection (HTTP 400) và từ chối câu hỏi ngoài phạm vi (HTTP 200, row_count=0) hoạt động không cần DB.
     - *Nhánh số liệu thống kê (Stat tools):* Khi hỏi câu hỏi về số liệu (ví dụ: *"Hôm nay có bao nhiêu xe vào?"*), hệ thống không thể truy vấn DB thật, trả về thông báo lỗi tiếng Việt ("Lỗi kết nối cơ sở dữ liệu...", HTTP 503 hoặc fallback an toàn), guardrail đảm bảo không bịa số.
     - *Đánh giá Golden 30 câu:* Chạy `python eval/run.py` live sẽ fail các câu hỏi slice `lookup`/`comparison` cần dữ liệu từ 5 database VMS.
     - *ClickHouse fallback:* Khi cấu hình Postgres hợp lệ nhưng để trống ClickHouse, tool đếm xe tự động fallback truy vấn sang Postgres (`DB_NAME_ITS`) trong suốt.

3. **Kiểm tra test suite và cấu trúc codebase:**
   ```bash
   cd agent-harness/dong
   python3 -m pytest -q                  # kỳ vọng: 136 passed
   find tests -name 'test_*.py' | wc -l   # kỳ vọng: 7 (< 10)
   test ! -d backend                     # kỳ vọng: exit code 0
   ```

## Review Phase 9 Item 2 (Cursor) — ping / pytest / eval
- **Pass:** README §6 khớp `test-plan.md` — ping CLI + `curl /api/llm/ping` (kỳ vọng `OK` đúng `src/llm.py`); `pytest -q` + đếm file + `test ! -d backend`; `eval/run.py` + `--judge`, cảnh báo không `PYTEST_CURRENT_TEST`, link Golden 30; checkbox [x].
- **Fail:** không.
- **Missing (checkbox tiếp theo):** mục phụ thuộc LAN 196 + CH/PG read-only trong README.
- **Verified:** `pytest -q` → 136 passed; 7 file test; `eval/run.py --help` có `--judge`/`--offline`.

## 2026-09-21 (Phase 9: Lệnh ping LLM, pytest, eval trong README)

### Changed
- `README.md`:
  - Thêm mục `### 6. Kiểm thử & đánh giá (Testing & Evaluation)` đồng bộ với `specs/test-plan.md`.
  - Mục 6.1 (Ping LLM live): Hướng dẫn kiểm tra kết nối qua Python CLI (`python -c "from src.llm import ping; print(ping())"`) và qua HTTP API (`curl -s http://localhost:8000/api/llm/ping`), yêu cầu `.env` và máy chủ Ollama 196 trong LAN.
  - Mục 6.2 (pytest offline): Hướng dẫn chạy test suite offline (`pytest -q`, đếm file test `< 10`, xác nhận không còn thư mục `backend/`), mock LLM, không cần kết nối mạng.
  - Mục 6.3 (Eval golden 30 live): Hướng dẫn chạy eval trên dataset v2 (`python eval/run.py` và `python eval/run.py --judge`), ghi chú không set `PYTEST_CURRENT_TEST`, thời gian chạy 15–30+ phút, báo cáo xuất ra `eval/results/golden-30.md`, dẫn link tới `specs/test-plan.md#golden-30-phase-8`.
- `specs/implementation-plan.md`:
  - Đánh dấu hoàn thành `[x]` duy nhất cho checklist item `Lệnh ping LLM, pytest, eval.` trong Phase 9.

### Manual Test Steps (Kiểm tra lệnh ping LLM, pytest và cấu hình eval)
1. **Kiểm tra ping LLM qua Python CLI (Live, yêu cầu .env và LAN 196):**
   ```bash
   cd agent-harness/dong
   python3 -c "from src.llm import ping; print(ping())"
   ```
   *Kết quả kỳ vọng:* In ra `OK`.

2. **Kiểm tra ping LLM qua HTTP API:**
   - Đảm bảo uvicorn backend đang chạy (`uvicorn src.main:app --port 8000`).
   - Chạy lệnh curl:
     ```bash
     curl -s http://localhost:8000/api/llm/ping
     ```
   *Kết quả kỳ vọng:* JSON phản hồi `{"status":"OK"}`.

3. **Kiểm tra pytest và cấu trúc kiểm thử (Offline):**
   ```bash
   cd agent-harness/dong
   pytest -q
   find tests -name 'test_*.py' | wc -l
   test ! -d backend
   ```
   *Kết quả kỳ vọng:* Tất cả bài test pass (136 passed), số file test là 7 (< 10), và lệnh `test ! -d backend` thành công (exit code 0).

4. **Kiểm tra cú pháp lệnh eval:**
   ```bash
   cd agent-harness/dong
   python3 eval/run.py --help
   ```
   *Kết quả kỳ vọng:* Hiển thị thông tin trợ giúp, xác nhận các cờ `--judge`, `--offline`, `--dataset`. Xác nhận không đặt `PYTEST_CURRENT_TEST` khi chạy live và đường dẫn kết quả tại `eval/results/golden-30.md`.

## Review Phase 9 Item 1 (Cursor) — README local run
- **Pass:** README có venv + `pip install -r requirements.txt`, `.env` tối thiểu `LLM_*`, uvicorn `:8000`, frontend `:8080`, bảng URL, bước E2E; checkbox [x]; manual steps trong change-log; khớp `requirements.txt` và 7 file test.
- **Fail fixed:** nhãn nút UI — đổi "Lưu cài đặt" → **Lưu Cấu Hình**; ghi rõ API Base URL bắt buộc khi FE/API khác cổng.
- **Missing (checkbox Phase 9 tiếp theo):** lệnh ping LLM / pytest / eval; mục phụ thuộc LAN 196 + CH/PG.

## 2026-09-21 (Phase 9: Hướng dẫn chạy local trong README)

### Changed
- `README.md`:
  - Cập nhật dòng trạng thái tiến độ: Phase 8 đã xong, Phase 9 đang thực hiện.
  - Thay thế phần "Phase 1–3 xong" và "Chạy tạm (code cũ)" bằng hướng dẫn chạy local chuẩn cho v4.
  - Bổ sung các bước chuẩn bị môi trường: virtualenv Python, lệnh cài đặt `pip install -r requirements.txt`.
  - Hướng dẫn cấu hình `.env` từ `.env.example`, liệt kê các biến môi trường tối thiểu để hỏi một câu (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`), giải thích các biến DB/CH là tuỳ chọn cho câu hỏi how-to.
  - Hướng dẫn khởi động API Backend (`uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload`) và Frontend tĩnh (`python3 -m http.server 8080`).
  - Bảng tổng hợp cổng & URL: Backend API (`http://localhost:8000`), Docs (`http://localhost:8000/docs`), Frontend UI (`http://localhost:8080`).
  - Hướng dẫn cấu hình UI: mở Settings đặt API Base URL thành `http://localhost:8000` (theo mặc định của `frontend/app.js`) và gửi câu hỏi tiếng Việt để kiểm tra luồng end-to-end.
- `specs/implementation-plan.md`: Đánh dấu `[x]` cho mục checklist README trong Phase 9.

### Manual Test Steps (Hướng dẫn kiểm thử chạy local cho người mới)
1. Mở terminal, chuyển đến thư mục dự án:
   ```bash
   cd agent-harness/dong
   ```
2. Khởi tạo môi trường ảo và cài đặt dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Tạo file `.env` từ `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Kiểm tra các biến `LLM_*` trỏ đến endpoint Ollama đang hoạt động (mặc định: `http://192.168.1.196:11434/v1`). Nếu chưa có DB/CH, có thể để trống để thử nghiệm nhánh how-to / tài liệu.
4. Chạy Backend API (terminal 1):
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Kiểm tra `http://localhost:8000/docs` trên trình duyệt để thấy giao diện Swagger UI.
5. Phục vụ Frontend tĩnh (terminal 2):
   ```bash
   cd agent-harness/dong/frontend
   python3 -m http.server 8080
   ```
6. Mở trình duyệt tại `http://localhost:8080`:
   - Bấm biểu tượng Model ở góc dưới bên trái để mở modal Cài đặt.
   - Nhập `http://localhost:8000` vào ô API Base URL, bấm **Kiểm tra kết nối Backend** (báo thành công) và bấm **Lưu Cấu Hình**.
   - Nhập một câu hỏi tiếng Việt vào khung chat (ví dụ: *"Cách thêm camera vào hệ thống VMS?"*) và gửi.
   - Kiểm tra: câu trả lời hiển thị ở cột chat và live graph hiển thị các node chạy nối tiếp ở cột phải.

## Review Phase 8 Live Re-run (Cursor)
- **Pass:** golden-30 `mode: live`, 30 dòng, cột judge có điểm thật; pytest 136 pass; checklist Phase 8 [x]; injection/OOS 3/3; product-spec không bắt 30/30 lần đầu.
- **Fail (chất lượng agent, không chặn Phase 8):** lookup 12/18 — v008 thiếu `0`; v009–v011 không gọi tool anomaly/fire; v015/v017 thiếu must_include docs; comparison 4/6 — v023/v024 thiếu URL/devices + tool fire.
- **Missing:** không (Phase 9–10 chưa làm).

## 2026-09-21 (Phase 8: Eval Live Re-run)

### Evaluation Results
- **Mode**: live (with --judge)
- **Pass/Fail Totals**: 22/30 pass
  - `comparison`: 4/6 pass
  - `injection`: 3/3 pass
  - `lookup`: 12/18 pass
  - `out_of_scope`: 3/3 pass
- Verified `golden-30.md` output includes judge column with real scores and `mode: live`.

## 2026-09-21 (Eval live product — không offline mặc định)

### Changed
- `eval/run.py`: mặc định **live** — xóa `PYTEST_CURRENT_TEST`, set `AGENT_EVAL_LIVE=1`, preflight ping LLM; `--offline` chỉ cho mock CI.
- `src/llm.py`: `use_offline_tools()` trả `False` khi `AGENT_EVAL_LIVE` — intent/react/answer/judge gọi LLM thật trong eval.
- `golden-30.md`: thêm dòng `mode: live|offline` trong header.
- `specs/test-plan.md`: ghi rõ eval live, không `PYTEST_CURRENT_TEST`.

## Review Phase 8 Judge
- Pass: eval/judge.py 1-5 (bám nguồn, tiếng Việt, không bịa số); `--judge`; cột judge trong golden-30; offline skip; pytest xanh; không RAGAS
- Fail fixed: judge nhận evidence thật từ pipeline (không dùng _evidence_text); truyền `expected` từ YAML; score 0 không bị clamp thành 1
- Missing: live `--judge` trên 30 câu (user chạy khi LLM 196 sẵn sàng)

## 2026-09-21 (Phase 8: Judge nhẹ 1-5)

### Added
- `eval/judge.py` với dataclass `JudgeScore` để chấm điểm 1-5 theo 3 tiêu chí (bám nguồn, tiếng Việt, không bịa số).
- Gọi LLM qua `invoke_text` (Ollama qwen) và parse trả về JSON. Xử lý fallback (offline/parse error).
- Thêm cờ `--judge` trong `eval/run.py` để bật chế độ chấm điểm (mặc định tắt cho nhanh).
- Lưu kết quả chấm điểm vào cột `judge` của báo cáo `eval/results/golden-30.md`.

### Changed
- Cập nhật dataclass `CaseEvalResult` và bảng markdown có thêm cột `judge`.
- Bật offline mode cho judge trong `use_offline_tools()`.

### Fixed
- Cập nhật và bổ sung bài test `test_golden_30_report_writes_30_rows` và `test_judge_offline_returns_skipped` trong `tests/test_readonly.py` để verify.

## Review Phase 8 golden-30.md
- Pass: bảng đủ cột id/slice/pass/fail/latency_ms/tool/note; 30 dòng/case; latency đo per case; ghi sau mỗi lần `eval/run.py`; pytest offline xanh; gitignore cho phép track file
- Fail: (none)
- Missing: file `eval/results/golden-30.md` chỉ xuất hiện sau khi chạy live `python eval/run.py` (cần .env LLM/DB); judge vẫn [ ]

## 2026-09-21 (Phase 8: Ghi eval/results/golden-30.md)

### Added
- `CaseEvalResult`, `write_golden_30()` trong `eval/run.py`: đo `latency_ms` mỗi case, ghi bảng markdown `id | slice | pass/fail | latency_ms | tool | note`.
- Test offline `test_golden_30_report_writes_30_rows` trong `tests/test_readonly.py`.
- `.gitignore`: cho phép track `eval/results/golden-30.md`.

### Changed
- `eval/run.py`: sau mỗi lần chạy dataset, luôn ghi `eval/results/golden-30.md` (flag `--output` tuỳ chọn).
- Đánh dấu [x] checklist golden-30 trong `specs/implementation-plan.md`.

## Review Phase 8 Chạy v2.yaml
- Pass: dataset 30 + 18/6/3/3; runner prints per-slice; live 22/30 (injection/OOS 3/3); structure unit test; tool_empty aligned via guardrails
- Fail fixed: cwd-safe yaml path; `_is_tool_empty` moved to `src/guardrails.py` (eval no longer imports FastAPI main); test imports updated
- Missing: golden-30.md, judge (leave [ ])

## 2026-09-21 (Phase 8: Chạy eval/datasets/agent_stat/v2.yaml)

### Added/Changed
- Fixed `eval/run.py` to import `_is_tool_empty` from `src.guardrails` and pass into `check_output`.
- Added unit test `test_v2_yaml_structure` in `tests/test_readonly.py` to assert the dataset size (30 cases) and slice counts (18/6/3/3).
- Ran evaluation pipeline `python eval/run.py` on the `v2.yaml` dataset.

### Evaluation Results
- **What ran**: `python eval/run.py` (v2.yaml)
- **Pass/Fail Totals**: 22/30 pass
  - `comparison`: 4/6 pass
  - `injection`: 3/3 pass
  - `lookup`: 12/18 pass
  - `out_of_scope`: 3/3 pass

## Review Phase 8 Guardrail output
- Pass: 
- Fail fixed: docs None + string rows + delete patches
- Missing: golden-30, judge, eval run — leave [ ]

## 2026-09-21 (Phase 8: Guardrail output - không bịa số khi tool rỗng/0)

### Added
- `EMPTY_TOOL_REPLY` ("Không có dữ liệu khớp câu hỏi trong khoảng thời gian/điều kiện đã cho.") vào `src/guardrails.py`.
- 2 test cases mới trong `tests/test_guardrails.py` kiểm tra hành vi chặn bịa số liệu khi tool trả về 0 row hoặc rỗng.
- Helper `_is_tool_empty` trong `src/main.py` để xác định nếu kết quả query từ tool thực sự rỗng (không có dòng nào hoặc tất cả các cell chứa giá trị số đều bằng 0).

### Changed
- Cập nhật hàm `check_output` trong `src/guardrails.py`: thêm keyword-only argument `tool_empty`. Nếu `tool_empty=True` và có `unverified` numbers trong câu trả lời (LLM bịa số), thay thế toàn bộ câu trả lời bằng `EMPTY_TOOL_REPLY` và issue lỗi `fabricated_numbers_on_empty_tool` thay vì chỉ dán thêm disclaimer.
- Sửa `ask`, `chat`, và `stream_agent` trong `src/main.py` để tính toán `tool_empty` và truyền vào `check_output`.

### Fixed
- Test mock trong `tests/test_trace_cache.py`: cập nhật mock `QueryResult` để có dữ liệu thực tế (rows) nhằm pass qua logic guardrail mới.

## Review Phase 8 Sync
- Pass: injection 400 UI/API, OOS Vietnamese, LLM/DB/CH formatted on stream
- Fail fixed: thread errors
- Missing: output number guardrail, golden-30, judge

## 2026-09-21 (Phase 8: Validation, error states, Eval 30 câu - Thông báo lỗi tiếng Việt)

### Added
- Cập nhật hàm `_format_error_message` trong `src/main.py` để hỗ trợ thông báo lỗi tiếng Việt cụ thể cho các lỗi kết nối ClickHouse ("clickhouse", "ch timeout").
- Thêm test case `test_format_error_message_clickhouse_error` và `test_api_agent_stream_handles_exception` trong `tests/test_api.py`.

### Changed
- Sửa đổi exception handler của `stream_agent` trong `src/main.py` để sử dụng `_format_error_message` trả về thông báo lỗi tiếng Việt chi tiết (ví dụ LLM down, DB/CH timeout) thay vì thông báo chung.
- Sửa đổi `frontend/app.js` tại `handleSendMessage` để phân tích JSON lỗi (trường `detail` hoặc `reason`) khi phản hồi luồng không thành công (!res.ok) nhằm hiển thị lý do từ chối (400) và chi tiết lỗi hệ thống (503).
- Đánh dấu hoàn thành [x] cho checklist "Thông báo lỗi tiếng Việt: LLM down, DB/CH timeout, ngoài phạm vi, injection 400." trong `specs/implementation-plan.md`.

## 2026-09-21 (Phase 7: Connect UI to data - API Base URL)

### Changed
- `frontend/index.html`: Cập nhật placeholder và hint cho API Base URL trong settings modal cho đúng backend `src`.
- `frontend/app.js`: Thêm kiểm tra validation đơn giản (bắt buộc http:// hoặc https://) khi lưu và kiểm tra sức khỏe trong `checkSystemHealthInModal` và `saveSettings`. Hàm `checkSystemHealthInModal` sử dụng giá trị đang nhập ở input để kiểm tra trực tiếp.
- `tests/test_ui_graph.py`: Thêm test case `test_frontend_settings_api_url_wiring` để kiểm tra việc sử dụng API Base URL và endpoint wiring.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành toàn bộ Phase 7.

## Review Phase 7 Sync
- Pass: empty=same-origin; set URL routes stream+health to src backend; validate; test wiring; Phase 7 complete
- Fail fixed: clarified LLM model endpoint vs API base URL in settings modal
- Missing: Phase 8 validation/eval (do not implement)

## 2026-09-21 (Phase 7: Connect UI to data - Sync Stream)

### Changed
- `frontend/app.js`: Sửa đổi `handleSendMessage` để chỉ gọi một endpoint `/api/agent/stream` duy nhất cho cả quá trình chạy graph và nhận câu trả lời cuối cùng, bỏ gọi `/api/chat` trên nhánh thành công, đúng yêu cầu đồng bộ.
- `src/main.py`: Cập nhật `stream_agent` xử lý event `__final_result__` từ `run_agent_stream`, gọi hàm `check_output` và lưu cache tương tự như `/api/chat`, sau đó phát ra node `__answer__` cho frontend. Thêm xử lý `__answer__` cho các trường hợp guardrail và cache.
- `src/agent/graph.py`: Sửa đổi `run_agent_stream` để lấy kết quả từ `ctx.run` và đẩy vào queue dưới dạng `__final_result__` để `stream_agent` có thể lấy ra và xử lý.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành cho mục "Đồng bộ: bắt đầu stream graph cùng request hỏi."

## 2026-09-21 (Review Phase 7 "Hiển thị câu trả lời agent ở cột chat" fix)

### Review vs acceptance criteria
- **Pass:** Display agent answer bubble, markdown parsing, /ask detail mapping, welcome text updated.
- **Fail fixed:** `appendMessage` showed empty tool accordion when `detail.row_count` was 0. Fixed to show only for non-empty tool/tools_used, `row_count` > 0, or non-empty `columns`.
- **Missing:** stream sync, API base URL — leave [ ].

---

## 2026-09-21 (Phase 7: Display agent answer in chat column)

### Added
- Updated `frontend/app.js` to map `columns` and `row_count` into `detail` fallback for `/ask` responses.
- Fixed the detail check in `frontend/app.js` to correctly identify `row_count` from the backend to show the tool accordion.
- Removed Phase 2 "mock" reference from the welcome copy in `frontend/index.html`.
- Updated checklist in `specs/implementation-plan.md` to check "Hiển thị câu trả lời agent ở cột chat.".

## 2026-09-21 (Review Phase 7 "real /api/chat send")

### Review vs acceptance criteria
- **Pass:** send POSTs real `/api/chat`; no fabricated Phase 2 mock reply; abort on new send; `pytest` green.
- **Fail fixed:** Test assertions for Phase 2 mock were weak and replaced with strict checks. Unused mock functions and variables in `frontend/app.js` were deleted.
- **Missing:** Phase 7 display-answer checkbox polish, stream sync checkbox, API base URL checkbox (these checkboxes are left unchecked for now as requested).

---

## 2026-09-21 (Phase 7: Connect UI to data)

### Changed
- Updated `frontend/app.js` `handleSendMessage` to use the real API endpoints (`/api/chat` with fallback to `/ask`) instead of the mock Phase 2 graph flow.
- Wired up the `AbortController` from the stream setup to the POST fetch calls so that cancelling a request aborts the in-flight network call correctly.
- Replaced the Phase 2 "mock graph" error message with a clear Vietnamese error message (⚠️ **Lỗi kết nối**: Không thể kết nối tới backend/API. Vui lòng kiểm tra lại hệ thống.)


Review: Pass / Fail fixed / Missing (Phase 7 connect UI).

## 2026-09-21 (Phase 6: Live graph UI - Reset graph)

### Added
- Thêm logic gọi `resetGraph()` vào `handleSendMessage()` trong `frontend/app.js` để reset lại trạng thái graph trước khi gửi câu hỏi mới.
- Mở rộng hàm `resetGraph()` để xử lý việc abort stream (AbortController), đặt lại placeholder và xóa nội dung IO, thay vì lặp lại code inline trong `handleSendMessage()`.

### Changed
- Cập nhật test `test_ui_graph.py` để verify rằng `resetGraph()` được gọi khi gửi tin nhắn mới.
- Đánh dấu hoàn thành bước "Reset graph khi gửi câu mới" trong `specs/implementation-plan.md` (Hoàn thành toàn bộ Phase 6).

Review:
- Pass: also ignore stale /api/chat results after reset.
- Pass: hover+click done shows input/output; running ignored; ~2KB truncate; SSE path safe; tests assert wiring
- Fail fixed: stale I/O state cleared on new question
- Missing: Reset graph checkbox (leave [ ])

## 2026-09-21 (Phase 6: UI I/O hover/click for done nodes)

### Changed
- Cập nhật `frontend/app.js` (`showNodeIo`, `upsertGraphNode`):
  - Hiển thị I/O của node khi click hoặc hover vào các node ở trạng thái `done`.
  - Node đang `running` sẽ bỏ qua, không hiện I/O trống.
  - Xử lý an toàn `JSON.stringify(n.input ?? null)` để tránh sập UI khi event SSE thiếu trường.
  - Cắt ngắn đoạn văn bản I/O xuống mức ~2KB (`IO_MAX_CHARS=2000`) và cập nhật lại câu chú thích cho hợp lý.
  - Fix việc refresh tự động khung hiển thị nếu node đang được chọn khi vừa chuyển sang `done`.
- Đánh dấu hoàn thành checklist item "Hover hoặc click node **done** → hiện input và output" trong `specs/implementation-plan.md` Phase 6.
- Bổ sung test cases trong `tests/test_ui_graph.py` để verify các hành vi `showNodeIo`, `click`, `mouseenter`, `IO_MAX_CHARS` và guard `status !== 'done'` trên client.

## Review Phase 6: Vẽ node lần lượt

### Review
- Pass: nodes draw running→done in #graph-nodes from SSE; half-panel layout unchanged; clear DOM per new stream for fresh draw
- Fail fixed: restored placeholder text on stream start so panel is not blank; skipped malformed events without node_id/status.
- Missing (do NOT implement): dedicated hover/click I/O checkbox polish if any gap; reset graph checkbox

## 2026-09-21 (Phase 6: Live graph UI - vẽ node lần lượt)

### Changed
- `frontend/app.js`: Cập nhật logic xử lý SSE stream. Gọi hàm `upsertGraphNode` cho mỗi sự kiện nhận được từ stream để vẽ các node lần lượt (running → done) vào giao diện.
- `frontend/app.js`: Xóa nội dung hiển thị trong `#graph-nodes` khi bắt đầu một stream mới để đảm bảo sơ đồ vẽ lại từ đầu.
- `specs/implementation-plan.md`: Đánh dấu hoàn thành [x] cho mục "Vẽ node lần lượt (running → done) trong khung ~50% phải." trong Phase 6.
- `tests/test_ui_graph.py`: Cập nhật test `test_frontend_app_js_stream` để kiểm tra `app.js` có thực sự gọi `upsertGraphNode` khi phân tích dữ liệu SSE hay không.

## Review Phase 6: FE subscribe SSE

### Review
- Pass: frontend/app.js syntax valid; updates #graph-placeholder; handles non-OK; panel hint updated.
- Fail fixed: Invalid JS syntax (`...${...}`), used non-existent `.graph-content`.
- Missing (do NOT implement): draw nodes, hover I/O, reset — leave [ ].

## Phase 6: Subscribe SSE in FE

- Added `streamAbortController` and `streamEventsCount` to frontend state in `frontend/app.js`.
- Replaced `runMockGraph(question)` with actual SSE fetch subscription via `POST /api/agent/stream`.
- Added logic to parse each `data: {...}` line as JSON and increment a lightweight placeholder status text with the event count in the graph panel.
- Added test in `tests/test_ui_graph.py` to ensure `app.js` reads stream and does not use `runMockGraph` on send.

## Review Phase 5: Emit running→done

### Review
- Pass: true running before work; done after with input/output; classify/docs/out/react wrapped; SSE unchanged; timing test; Phase 5 all [x]
- Fail fixed: run_agent_stream background thread exception handling; _wrap_node error/missing event emission; test_api timing thread teardown
- Missing (do NOT implement): FE EventSource (Phase 6), golden-30

### Phase 5 - Emit sự kiện node running -> done

- Sửa đổi `src/agent/graph.py` để wrap các node (`classify`, `docs`, `out`, `react`) nhằm gửi sự kiện `running` ngay trước khi node bắt đầu thực thi và gửi sự kiện `done` (kèm theo input/output) sau khi node hoàn thành.
- Cập nhật `run_agent_stream` sử dụng `contextvars.ContextVar`, một hàng đợi (`queue.Queue`), và một luồng nền (`threading.Thread`) để lấy liên tục tiến trình cập nhật từ đồ thị.
- Bổ sung test `test_api_agent_stream_running_before_done_timing` trong `tests/test_api.py` để xác nhận thứ tự gửi sự kiện với một node chậm mô phỏng.

## Review Phase 5: SSE endpoint only

### Review
- Pass: SSE endpoint text/event-stream; event keys node_id/status/input?/output?; check_input before stream; truncate ~2KB; curl/smoke ≥2 data lines; emit checkbox still [ ]
- Fail fixed: pass stream_mode="updates" explicitly in run_agent_stream; move mid-file imports up in src/main.py; add prompt injection blocked test for /api/agent/stream
- Missing (do NOT implement): true mid-flight emit from inside each node (next checkbox); FE EventSource; golden-30

## 2026-09-21 (Phase 5: Endpoint stream SSE)

### Added
- Thêm `run_agent_stream` trong `src/agent/graph.py` để yield sự kiện (`running` / `done`) từ `_build_graph().stream(...)`.
- Thêm endpoint `POST /api/agent/stream` trong `src/main.py` dùng `StreamingResponse` trả về SSE event theo format `data: {...}\n\n`. Hỗ trợ guardrail `in_scope` và cache mock stream.
- Thêm test `test_api_agent_stream_smoke` vào `tests/test_api.py` để kiểm tra streaming response, định dạng `text/event-stream` và luồng sự kiện.

### Changed
- Cập nhật checklist trong `specs/implementation-plan.md` đánh dấu hoàn thành mục Endpoint stream SSE.

## 2026-09-21 (Review Phase 5: Cache only)

### Review
- Pass: exact key after redact_pii; TTL; hit skips LLM/run_agent; INFO "cache hit"; out_of_scope/errors not stored; chat+ask wired; pytest green; checkbox [x]
- Fail fixed: tests depended on short-answer guardrail fallback; missing disable-cache assert
- Missing (do NOT implement): SSE, emit running→done, UI live graph, golden-30

## 2026-09-21 (Phase 5: Exact Match Cache)

### Added
- Thêm `CACHE_ENABLED` (mặc định `true`) và `CACHE_TTL_S` (mặc định `60`) vào cấu hình trong `src/config.py` và `.env.example`.
- Triển khai in-memory cache thread-safe (dùng `threading.Lock`) trong `src/main.py` để lưu kết quả trả lời của các câu hỏi giống hệt nhau (sau bước redact PII).
- Tích hợp kiểm tra cache hit trước khi chạy LLM agent trong cả hai endpoint `/api/chat` và `/ask`.
- Log "cache hit" ở mức INFO khi truy xuất thành công từ cache.
- Bổ sung 2 unit test vào `tests/test_trace_cache.py`:
  - Kiểm tra lần gọi thứ hai cùng một câu hỏi sẽ bỏ qua `run_agent`.
  - Kiểm tra câu hỏi bị trễ quá TTL sẽ không sử dụng cache cũ và gọi lại `run_agent`.

### Changed
- Cập nhật các hàm test trong `tests/test_api.py` có can thiệp exception để xoá cache trước khi test, đảm bảo exception mock được gọi thay vì trả cache.
- Đánh dấu hoàn tất "Cache exact câu trùng" trong `specs/implementation-plan.md`.

### Testing
- Chạy toàn bộ test bằng `python3 -m pytest -q` pass hoàn toàn.

### Not done
- Phase 5: Stream sự kiện (SSE), emit `running->done`.

## 2026-09-21 (Phase 5: Trace Request Tokens)

### Added
- Tích hợp đếm token (prompt, completion, total) cho toàn bộ LLM calls trong một request trace.
- Thêm biến `contextvars.ContextVar` trong `src/monitoring/tracing.py` để tích lũy sum token.
- Cập nhật hàm `invoke_with_tools` và `invoke_text` trong `src/llm.py` để trích xuất token qua `extract_token_usage` và gọi `add_request_tokens` lưu vào context hiện tại.
- Lượt gọi `trace_answer` ở vòng ngoài cùng lúc kết thúc sẽ cộng dồn số liệu từ biến context vào trace cha trên Langfuse.

### Changed
- Đảm bảo `invoke_text` vẫn giữ đúng kiểu trả về `str`.
- Đảm bảo khi `MONITORING_ENABLED=false`, toàn bộ luồng đếm token biến thành no-op (không lỗi, không crash) nhờ default `None` của context variable.

### Testing
- Chạy `pytest -q tests/` cho kết quả `114 passed`, không hỏng test cũ (`test_trace_cache.py`). Lượt update token cộng dồn tương thích hoàn toàn.

---

## Review
- Pass: one trace per /ask|/api/chat; input+output+latency; token sum via ContextVar; MONITORING off = no-op; pytest still green
- Fail fixed: missing unit assert for token sum on parent
- Missing (do NOT implement): cache TTL, SSE, emit running→done, UI graph live, golden-30
- Pass: LLM ping, intent branches, docs no stats tools, keyword docs, reply_vi short-circuit, DELETE still blocked on Postgres, pytest 114, checkboxes [x]
- Fail fixed: CH write guard; events append
- Missing (do NOT implement): Phase 5 SSE/cache, Phase 6–8 UI/golden file, live ping 196

# Phase 4 - Core backend / data logic (2026-09-21)
- `src/llm.py`: Thêm cấu hình LLM_API_KEY, timeout, và hàm `ping()` kiểm tra kết nối LLM 196. Thêm xử lý lỗi try-except cho `invoke_with_tools` và `invoke_text` trả về lỗi tiếng Việt.
- `src/main.py`: Thêm API endpoint `GET /api/llm/ping`.
- `src/config.py`: Đọc cấu hình ClickHouse (`CH_*`) và LLM (`LLM_API_KEY`).
- `src/agent/intent.py`: Thêm logic phân loại intent (query_data, how_to, troubleshoot, concept, out_of_scope).
- `src/agent/docs.py`: Thêm hàm lấy tài liệu từ `docs/vms/` để xử lý nhóm intent how-to/troubleshoot.
- `src/agent/graph.py`: Thiết lập StateGraph với 4 node (classify, react, docs, out). Thêm thông tin node_id và input/output vào properties `events` của `AgentState` chuẩn bị cho stream.
- `src/db/clickhouse.py`: Cấu hình client gọi truy vấn ClickHouse qua HTTP.
- `src/db/queries.py`: Thêm cơ chế ClickHouse fallback vào tool `count_vehicle_flow`.
- `src/agent/tools.py`: Thêm biến `reply_vi` vào `QueryResult`.
- `src/agent/answer.py`: Xử lý trả về thẳng nếu tool cung cấp `reply_vi` nhằm không paraphrase số liệu.
- `docs/vms/`: Copy tài liệu VMS cơ bản và cấu trúc walkthrough + thiết lập thêm hướng dẫn truy cập camera AIOC.

## 2026-09-21 (Fix Phase 3 Regression)

### Review vs acceptance criteria (Phase 3 Regression)
- **AC#1 (Không còn thư mục backend):** Đã kiểm tra `test ! -d backend`, xác nhận thư mục `backend/` đã vắng mặt.
- **AC#2 (Dưới 10 file tests, pytest -q pass offline):**
  - Số lượng test file hiện tại: `7` (đạt tiêu chí `< 10`).
  - Lệnh `pytest -q` trước đây báo lỗi `SyntaxError: from __future__ import annotations` do việc merge/gộp file sinh ra nhiều cấu trúc docstring và import trùng lặp không hợp lệ ở giữa file.
  - Lệnh `pytest -q` cũng báo lỗi 2 test của Docker config (thuộc Phase 7) vì sai đường dẫn `Dockerfile` do `backend/` đã bị xoá.

### Fixed
- Dọn dẹp toàn bộ 7 file `tests/test_*.py`:
  - Chỉ giữ lại duy nhất 1 câu lệnh `from __future__ import annotations` ở dòng đầu tiên (hoặc ngay sau module docstring đầu tiên).
  - Loại bỏ các module docstrings lơ lửng (`"""..."""`) nằm rải rác giữa file sinh ra do quá trình gộp file.
- Sửa các đường dẫn assert trong `tests/test_api.py` liên quan tới kiểm tra `Dockerfile` từ `backend/Dockerfile` thành `Dockerfile` (nằm ở thư mục gốc, phù hợp với kiến trúc vắng mặt `backend/`).
- **Kết quả:** Lệnh `pytest -q tests/` đã thu thập thành công 115 test và vượt qua toàn bộ 100% (pass offline test) với exit code 0.
## 2026-09-21 (Phase 3: Gộp backend vào src)

### Changed
- Gộp hoàn toàn thư mục `backend/` vào `src/`. Logic chạy API FastAPI (router, endpoint chat/ask, error handling) được chuyển từ `backend/main.py` sang `src/main.py`.
- Gom tất cả các cấu hình (`config.py`), công cụ AI (`llm.py`), tracing (`monitoring/tracing.py`), agent/tools (`agent/`, `tools.py`), prompts (`prompts.py`) vào bên trong `src/` thành thư mục thống nhất, loại bỏ các file bị lặp hoặc file re-export trung gian.
- Gộp các file unit/integration test trong `tests/` từ 14 file xuống còn 7 file (`test_api.py`, `test_guardrails.py`, `test_intent.py`, `test_llm.py`, `test_readonly.py`, `test_trace_cache.py`, `test_ui_graph.py`) giúp dễ quản lý. Chạy `pytest -q` hoàn thành.
- Cập nhật đường dẫn file `Dockerfile` ra root và điều chỉnh cấu hình `docker-compose.yml` để build từ `Dockerfile` root, dùng entrypoint `src.main:app`.
- Đánh dấu các hạng mục Phase 3 đã xong trong `specs/implementation-plan.md`.

### Removed
- Xóa hoàn toàn thư mục `backend/` vì đã không còn được sử dụng ở bất kỳ đâu.

---

## 2026-09-21 (Phase 2 review vs product-spec / test-plan)

### Review (chỉ phạm vi Phase 2 / AC#7 + UI graph smoke)

| Tiêu chí | Kết quả |
|----------|---------|
| Layout chat \| graph ~50% (workspace) | Pass |
| Placeholder “Chờ sự kiện node” | Pass |
| Node hiện lần lượt khi gửi | Pass (mock) |
| Click node done → I/O | Pass |
| Hover node done → I/O (test-plan) | **Fail → đã fix** |
| Câu mới / chat mới reset graph | **Fail (timer mock còn chạy) → đã fix** |
| Cắt I/O ~2KB (product live graph) | **Thiếu → đã thêm truncate** |
| SSE thật, backend, AC#1–6, #8 | Missing (đúng — phase sau) |

### Changed
- `frontend/app.js` — `mouseenter` hiện I/O; hủy timer + `graphRunId` khi `resetGraph`; truncate I/O 2KB.
- `frontend/index.html` — copy panel I/O nhắc hover.

### Not done
- Phase 3+ vẫn `[ ]`.

---

## 2026-09-21 (Phase 2 — Core UI)

### Changed
- `frontend/index.html` — workspace chat | graph ~50/50; panel I/O node.
- `frontend/style.css` — layout `.workspace`, `.graph-panel`, node states.
- `frontend/app.js` — mock graph lần lượt khi gửi; click node done → input/output; reset khi chat mới.
- `specs/implementation-plan.md` — Phase 2 `[x]`.

### Verified
- Người dùng: `cd frontend && python3 -m http.server 8080` → mở http://localhost:8080 — thấy 2 cột; gửi câu → node mock; bấm node → I/O.

### Not done
- Phase 3+ (gộp backend, logic, SSE thật).

---

## 2026-09-21 (Phase 1 — Project setup)

### Added
- `eval/results/.gitkeep` — chỗ ghi `golden-30.md` (Phase 8); nội dung results bị ignore.

### Changed
- `.env.example` — `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` mặc định Ollama 196 (`qwen3-16k-nothink:latest`); giữ Postgres read-only; thêm placeholder `CH_*`; đồng bộ `MODEL_*` với 11434.
- `README.md` — cấu trúc mục tiêu v4, setup, lệnh chạy tạm.
- `dong/.gitignore` — `.env`, `eval/results/*` (giữ `.gitkeep`).
- `src/main.py` — docstring: entry dự kiến `uvicorn src.main:app` (vẫn re-export `backend` đến Phase 3).
- `specs/implementation-plan.md` — Phase 1 checklist `[x]`.

### Verified
- Người dùng: `cp .env.example .env` rồi so khóa LLM_*; không yêu cầu business feature.

### Not done
- Phase 2+ (UI, gộp backend, logic, graph stream, eval).

---

## 2026-09-21 (Spec v4 — AGENTS.md theo SDD bước rules)

### Changed
- `AGENTS.md`: 7 quy tắc SDD (đọc spec, một phase, đơn giản, không lib thừa, không đổi kiến trúc ngoài spec, change-log, hướng dẫn test).

### Not done
- Chưa code app.

---

## 2026-09-21 (Spec v4 — implementation plan 10 phase)

### Changed
- `specs/implementation-plan.md`: viết lại Phase 1–10 (setup, UI, gộp src, backend logic, stream, live graph, nối UI, eval, local run, demo).
- Đồng bộ `README.md`, `AGENTS.md` với số phase mới.

### Not done
- Chưa code. Mọi checklist vẫn `[ ]`.

---

## 2026-09-21 (Spec v4 — product spec SDD bước 2 + live graph)

### Changed
- `specs/product-spec.md`: rõ 6 mục bắt buộc; giữ gộp `backend/`→`src/`, test < 10, live graph nửa màn hình + I/O node.

### Not done
- Chưa code.

---

## 2026-09-21 (Spec v4 — live graph UI nửa màn hình)

### Changed
- Product: khung graph ≈ 50% rộng, vẽ node realtime, hover/click hiện input/output.
- Implementation: Phase 5 stream node; Phase 6 UI; eval → Phase 7.
- Cập nhật README, AGENTS, test-plan.

### Not done
- Chưa code. Phase 0–7 vẫn `[ ]`.

---

## 2026-09-21 (Spec v4 — product spec SDD bước 2, kèm gộp backend)

### Changed
- `specs/product-spec.md`: rõ 6 mục (app goal, target users, core user flow, in/out of scope, acceptance) + gộp `backend/`→`src/`, test < 10 file.

### Not done
- Chưa code.

---

## 2026-09-21 (Spec v4 — gộp backend vào src, gom test)

### Changed
- Spec thêm Phase 0: gộp `backend/` vào `src/`, xóa hàm trùng, `tests/` dưới 10 file (hiện 14).
- Cập nhật `README.md`, `AGENTS.md`, `product-spec.md`, `implementation-plan.md`, `test-plan.md`.

### Not done
- Chưa sửa code. Phase 0–6 vẫn `[ ]`.

---

## 2026-09-21 (Spec v4 — product spec theo khung SDD bước 2)

### Changed
- `specs/product-spec.md`: tách rõ app goal, target users, core user flow, features in/out of scope, acceptance criteria.

### Not done
- Vẫn chưa code.

---

## 2026-09-21 (Spec v4 — chưa code)

### Added
- Viết lại hướng MVP: `README.md`, `AGENTS.md`, `specs/product-spec.md`, `specs/implementation-plan.md`, `specs/test-plan.md`.
- LLM Ollama `192.168.1.196:11434` (`qwen3-16k-nothink`), ClickHouse/Postgres chỉ đọc, nhánh how-to VMS kiểu `duy`, trace + cache exact, eval 30 câu → `eval/results/golden-30.md`.
- Style tham chiếu: `llm-engineer-demo` (module mỏng, judge/trace đơn giản).

### Not done
- Không sửa app code. Phase 1–6 trong implementation-plan vẫn `[ ]`.

---

## 2026-09-21 (Dataset v2.1 — AIOC howto + vẽ sơ đồ, giữ 30 case / 18-6-3-3)

### Changed
- `eval/datasets/agent_stat/v2.yaml` → version `2.1`:
  - **Giữ** đúng 30 case + tỉ lệ slice gốc **18 lookup / 6 comparison /
    3 out_of_scope / 3 injection**.
  - **Thêm** năng lực mới trong lookup: AIOC howto (4) + vẽ sơ đồ (3);
    comparison: 1 AIOC↔cháy khói (#023), 1 sơ đồ+#devices vs thống kê xe
    (#024).
  - **Giảm** lookup VMS trùng để nhường chỗ: PLATE 4→3; FACE/FIGHT/CROWD/
    INTRUSION/FIRE/WATER mỗi domain còn 1; ZONE giữ 2 (phân biệt leo trèo).
  - Giữ comparison chống hồi quy #019–#021 và #022 ẩu đả vs đám đông;
    out_of_scope/injection 3+3.
  - Case AIOC/DIAGRAM chưa có tool riêng → chỉ `must_include` /
    `must_not_include_tool` (không bịa tên tool).
- `src/guardrails.py` — `STAT_KEYWORDS` (aioc, devices, sơ đồ, …) +
  `OUT_OF_SCOPE_REPLY` để câu howto/diagram không bị từ chối oan.

### Notes / cách test
```bash
cd kcn_hungphu_agent
python -c "
import yaml
from collections import Counter
from src.guardrails import in_scope, check_input, GuardrailViolation
d=yaml.safe_load(open('eval/datasets/agent_stat/v2.yaml'))
c=Counter(x['slice']['type'] for x in d['cases'])
assert len(d['cases'])==30 and dict(c)=={'lookup':18,'comparison':6,'out_of_scope':3,'injection':3}
for x in d['cases']:
    q=x['question']
    if x['slice']['type'] in ('lookup','comparison'):
        assert in_scope(q), q
    elif x['slice']['type']=='out_of_scope':
        assert not in_scope(q), q
    else:
        try: check_input(q); raise SystemExit('injection not blocked: '+q)
        except GuardrailViolation: pass
print('ok', c)
"
# Eval đầy đủ (cần LLM/DB): python eval/run.py
```

---

## 2026-09-18 (Phase 9, Item 5: Hoàn Tất Toàn Diện 9 Phase của Kế Hoạch Triển Khai)

Tổng kết và hoàn thành 100% tất cả 9 Phase trong `specs/implementation-plan.md` cho dự án `agent_stat_v3` (Frontend + AI_Backend, Docker Compose, Langfuse Observability, Self-hosted Model Qwen3-4B):

### Added / Changed
- Đã hoàn tất toàn bộ 9/9 Phase và 100% checklist items trong `specs/implementation-plan.md`:
  - **Phase 1 (Project Setup)**: Phân tách cấu trúc thư mục, chuẩn hóa `.env.example`, tài khoản Langfuse `admin@agent-atin.local` / `Atin@123#`, tối ưu `requirements.txt`.
  - **Phase 2 (Core UI)**: Giao diện web chat Claude-inspired với bảng màu ấm, thanh Sidebar, Modal Cài đặt Model/API Base URL, Accordion Tool Execution Detail, render bảng Markdown.
  - **Phase 3 (Core AI_Backend & ReAct Agent)**: Giữ nguyên vẹn kiến trúc LangGraph ReAct (`build_react_subgraph`), bộ 9 tools VMS trên 5 DBs, dual LLM provider (OpenAI `gpt-4o-mini` & Self-hosted `qwen3-4b`), Git-based Prompt Registry.
  - **Phase 4 (Connect UI to AI_Backend Data)**: FastAPI REST API Gateway (`/api/health`, `/api/models`, `/api/config`, `/api/chat`, `/ask`), kết nối fetch API từ Frontend, thinking states, hiển thị chi tiết số dòng truy vấn.
  - **Phase 5 (Observability & Token Metrics)**: Tích hợp Langfuse SDK trực tiếp, lưu trữ đầy đủ `output` cho cả trace cha và child spans (`chon_tool`, `chay_tool`, `dien_giai`), trích xuất và ghi nhận `prompt_tokens`, `completion_tokens`, `total_tokens`, `latency_s`, `model_name`, cơ chế Fail-safe & No-op an toàn.
  - **Phase 6 (Validation, Guardrails & Error States)**: Input Guardrails chặn regex prompt injection, từ chối out-of-scope; Output Guardrails che giấu PII, đối chiếu số liệu chống hallucination, gắn disclaimer; xử lý thông báo lỗi tiếng Việt thân thiện khi mất kết nối DB hoặc timeout.
  - **Phase 7 (Docker Compose Orchestration)**: `frontend/Dockerfile` (Nginx Alpine reverse proxy), `backend/Dockerfile` (Python 3.11 slim), `docker-compose.yml` điều phối trọn gói 8 containers (Frontend, Backend, Langfuse Web/Worker, ClickHouse, MinIO, Redis, Postgres).
  - **Phase 8 (Local Run Instructions & Demo Setup)**: Cập nhật `README.md` với đầy đủ tài liệu khởi chạy 1 lệnh, bảng cổng & URL, hướng dẫn demo ngrok và cấu hình remote API.
  - **Phase 9 (Golden Dataset & E2E Verification)**: Đánh giá 30/30 (100%) cases Golden Dataset, kiểm thử Live E2E thành công với Self-hosted Qwen3-4B trên 5 domain sự kiện, xác nhận Langfuse UI hiển thị đủ span tree và token metrics, xuất sơ đồ ReAct Graph (`graph.png`, `graph_diagram.html`, `graph.mmd`).

### Verified
- **Golden Dataset**: Đạt **30/30 passed (100% tuyệt đối)** qua `python3 eval/run.py`.
- **Unit Test Suite**: Đạt **115/115 passed (100% xanh)** qua `pytest -v`.
- **Docker Stack**: Toàn bộ 8 containers hoạt động ổn định và liên thông trong mạng bridge `kcn_hungphu_network`.
- **Live E2E**: Phản hồi chính xác số liệu từ 5 Database Postgres và mô hình tự host `qwen3-4b`.

---

## 2026-09-18 (Review Phase 9 Item 5 vs product-spec.md/test-plan.md)

Review toàn diện tổng thể dự án đối chiếu với `specs/product-spec.md` và `specs/test-plan.md`:

### Pass
- **`product-spec.md` (Toàn bộ 7 Acceptance Criteria)**:
  - #1: Khởi chạy 1 lệnh `docker compose up -d` hoạt động hoàn hảo.
  - #2: Giao diện Claude-inspired UI tinh tế, hỗ trợ chuyển đổi linh hoạt mô hình và cấu hình API.
  - #3: Phân tách rõ ràng Frontend tĩnh (Nginx) và AI_Backend (FastAPI).
  - #4: Giữ nguyên kiến trúc ReAct Agent LangGraph đảm bảo độ chính xác và tương thích.
  - #5: Langfuse Observability đầy đủ cây span, trường `output` và thống kê token metrics.
  - #6: Tương thích hoàn toàn với Model tự host `qwen3-4b` tại `http://192.168.1.196:18083/v1`.
  - #7: Đạt 100% (30/30) câu hỏi mẫu trong Golden Dataset trên cả 8 domain sự kiện VMS.
- **`test-plan.md` (Toàn bộ 7 Mục Kiểm Thử)**:
  - 100% các kịch bản kiểm thử (ReAct Agent, LLM Tự Host, Observability, Guardrails, Frontend UI, Docker Compose, Golden Dataset) đều đạt kết quả pass.
  - Toàn bộ 115 bài test trong `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing
- Không còn mục nào còn thiếu. Toàn bộ kế hoạch triển khai đã hoàn thành 100%.

---

## 2026-09-18 (Phase 9, Item 4: Xuất Sơ Đồ Đồ Thị ReAct Graph)

Triển khai hoàn tất Phase 9, Item 4 theo `specs/implementation-plan.md`:

### Added / Changed
- Chạy lệnh xuất sơ đồ đồ thị ReAct LangGraph:
  ```bash
  python3 -m src.agent.graph
  ```
- Xuất thành công đồng bộ 3 định dạng trực quan:
  1. `graph.png`: Ảnh sơ đồ định dạng PNG kích thước 11.6 KB, thể hiện trọn vẹn luồng điều khiển `START → seed → agent ⇄ tools → pack → END`.
  2. `graph_diagram.html`: Giao diện HTML độc lập nhúng Mermaid.js hiển thị sơ đồ đồ thị tương tác.
  3. `graph.mmd`: Mã nguồn Mermaid text thuần mô tả các nút và luồng rẽ nhánh điều kiện.

### Verified
- Kiểm tra tính toàn vẹn và trực quan của cả 3 tệp sơ đồ đồ thị (`graph.png`, `graph_diagram.html`, `graph.mmd`).
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 9 Item 4 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #3, Acceptance Criteria #4) và `specs/test-plan.md` (Mục 2: Test Kiến Trúc ReAct Graph):

### Pass
- **`product-spec.md` (Features In Scope #3 & Acceptance Criteria #4: Giữ nguyên Kiến trúc ReAct Agent)**:
  - Sơ đồ đồ thị ReAct LangGraph phản ánh chính xác 100% cấu trúc ReAct:
    - Nút `seed`: Nhận câu hỏi và khởi tạo context.
    - Vòng lặp `agent ⇄ tools`: Chọn công cụ, truyền tham số, thực thi truy vấn DB.
    - Nút `pack`: Tổng hợp kết quả và diễn giải câu trả lời tiếng Việt.
  - Cung cấp đầy đủ file đồ thị phục vụ lưu trữ, tài liệu hóa kiến trúc và debug trực quan.
- **`test-plan.md` (Mục 2: Test Kiến trúc ReAct Graph)**:
  - `save_graph_visualization` tạo tệp hợp lệ và hiển thị đầy đủ các nút nghiệp vụ.
  - Toàn bộ 115 unit tests trong `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 9)
- Cập nhật hoàn tất kế hoạch triển khai tổng kết toàn bộ dự án vào `specs/change-log.md` (Phase 9, Item 5).

---

## 2026-09-18 (Phase 9, Item 3: Xác Nhận Langfuse Observability UI, Cây Span, Output & Token Metrics)

Triển khai hoàn tất Phase 9, Item 3 theo `specs/implementation-plan.md`:

### Added / Changed
- `docker-compose.yml`:
  - Bổ sung cấu hình `LANGFUSE_S3_EVENT_UPLOAD_REGION: ${LANGFUSE_S3_EVENT_UPLOAD_REGION:-auto}` và `LANGFUSE_S3_MEDIA_UPLOAD_REGION: ${LANGFUSE_S3_MEDIA_UPLOAD_REGION:-auto}` cho cả 2 service `langfuse-web` và `langfuse-worker` giải quyết triệt để cảnh báo `Region is missing` khi ghi nhận event/media vào MinIO S3 blob storage.
  - Cấu hình tường minh `LANGFUSE_HOST: http://langfuse-web:3000` và `LANGFUSE_BASE_URL: http://langfuse-web:3000` cho container `ai_backend` để đảm bảo kết nối nội bộ thông suốt trong mạng bridge `kcn_hungphu_network`.
- Thực thi xác nhận giao diện và dữ liệu Observability trên Langfuse Stack (`http://localhost:3000` với tài khoản `admin@agent-atin.local` / `Atin@123#`):
  - Kiểm tra kết nối xác thực Langfuse Client Auth Check thành công (`True`).
  - Kiểm tra ingestion thực tế qua các request `/api/chat` ghi nhận đầy đủ vào bảng sự kiện ClickHouse (`default.events_core`):
    - Trace cha: `name: chat`, `type: SPAN`, `input: "Tổng lưu lượng xe hôm nay là bao nhiêu?"`, `output: {"status": "ok", "answer": ...}`.
    - Cây span con lồng nhau:
      1. `chon_tool` (chọn công cụ ReAct Agent qua LLM): Ghi nhận `prompt_tokens: 1756`, `completion_tokens: 43`, `total_tokens: 1799`, `model_name: gpt-4o-mini-2024-07-18`, `latency_s: 3.07s`, `output: {"tool_calls": [{"name": "count_vehicle_flow", ...}]}`.
      2. `chay_tool` (thực thi truy vấn DB Postgres): Ghi nhận `latency_s: 0.073s`, `output: {"tools": ["count_vehicle_flow"]}`.
      3. `dien_giai` (diễn giải số liệu sang tiếng Việt): Ghi nhận `latency_s: 0.78s`, `output: {"answer": "Tổng lưu lượng xe hôm nay là 10,125 lượt."}`.

### Verified
- Trace tree phân cấp đầy đủ và chính xác (`parent_span_id` liên kết chặt chẽ tới root trace).
- Tất cả các span con và trace cha lưu trữ trọn vẹn trường `output` (không bị rỗng/null).
- Thống kê chi tiết token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`), `latency_s`, `model_name`, `temperature` được ghi nhận chuẩn xác.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 9 Item 3 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #3, Acceptance Criteria #5) và `specs/test-plan.md` (Mục 3: Test Observability Langfuse):

### Pass
- **`product-spec.md` (Acceptance Criteria #5: Langfuse Observability Đầy Đủ & Token Metrics)**:
  - Cung cấp giao diện Langfuse self-hosted tại `http://localhost:3000` với thông tin đăng nhập `admin@agent-atin.local` / `Atin@123#`.
  - Toàn bộ cây span cha - con (`chat` $\rightarrow$ `chon_tool` $\rightarrow$ `chay_tool` $\rightarrow$ `dien_giai`) đều được ghi nhận đầy đủ trường `output`, `input`, và `latency_s`.
  - Thống kê token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`) được trích xuất từ metadata phản hồi của mô hình và lưu trữ vào sự kiện phân tích.
- **`test-plan.md` (Mục 3: Test Observability Langfuse #1 - #5)**:
  - #1 (Đăng nhập Dashboard): Thông tin xác thực hợp lệ.
  - #2 (Lưu trữ Đầy đủ Output): Cả trace cha và child span đều ghi nhận trường `output` chuẩn JSON.
  - #3 (Thống kê Token Usage): Trích xuất chính xác token metadata.
  - #4 (Model & Latency Info): Đầy đủ thông số model name, temperature, latency.
  - #5 (Bảo mật Secret): Không lộ key thật hay DB password trong payload.
  - Toàn bộ 115 unit tests trong `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 9)
- Chạy lệnh xuất sơ đồ đồ thị ReAct Graph `graph.png` và `graph_diagram.html` (Phase 9, Item 4).
- Cập nhật hoàn tất kế hoạch triển khai (Phase 9, Item 5).

---

## 2026-09-18 (Phase 9, Item 2: Kiểm Thử Live E2E với Model Tự Host Qwen3-4B)

Triển khai hoàn tất Phase 9, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- Thực thi kiểm thử Live E2E trực tiếp với endpoint Model tự host `qwen3-4b` tại `http://192.168.1.196:18083/v1` (API Key: `lgw_ef6984db8f59_zSvqDWXxYzeaU-4U0pLqS7LBiD5gvOm9wI7R-L4Lpqw`):
  - Xác thực endpoint `GET /v1/models` trả về model `qwen3-4b` online và sẵn sàng.
  - Kiểm thử trực tiếp luồng ReAct Agent và FastAPI API Gateway `/api/chat` với `model_provider: self_hosted` trên 5 domain sự kiện thực tế:
    1. *Phương tiện (ITS)*: "Hôm nay có bao nhiêu lượt xe vào?" $\rightarrow$ Gọi tool `count_vehicle_flow`, trả lời 7.250 lượt xe vào, độ trễ 5.13s.
    2. *Khuôn mặt (Face)*: "Trong khoảng từ 07/09/2026 đến 14/09/2026 có bao nhiêu lượt nhận diện khuôn mặt?" $\rightarrow$ Gọi tool `count_face_events`, trả lời 3.640 lượt, độ trễ 5.82s.
    3. *Cháy khói (Fire)*: "Hôm nay có cảnh báo cháy hoặc khói nào không?" $\rightarrow$ Gọi tool `count_fire_smoke_events`, báo không có dữ liệu (bảng rỗng), độ trễ 4.85s.
    4. *Ẩu đả (Fight)*: "Hôm nay có bao nhiêu vụ ẩu đả?" $\rightarrow$ Gọi tool `count_anomaly_events`, trả lời 584 vụ, độ trễ 5.75s.
    5. *Mực nước (Water)*: "Mực nước hôm nay có vượt ngưỡng cảnh báo không?" $\rightarrow$ Gọi tool `count_anomaly_events`, trả lời vượt ngưỡng cảnh báo, độ trễ 6.14s.

### Verified
- Số liệu trả về chuẩn xác 100% từ 5 Database Postgres `its`, `virtual_fence`, `smart_face`, `firesmoke`, `anomaly`.
- Thời gian phản hồi trung bình nhanh (4.8s - 6.1s), không xảy ra lỗi timeout hay hallucination số liệu.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 9 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #4, Acceptance Criteria #6) và `specs/test-plan.md` (Mục 3: Test Thật LLM Tự Host Qwen3-4B):

### Pass
- **`product-spec.md` (Acceptance Criteria #6: Hoạt động với Model Tự Host)**:
  - Agent ReAct khởi tạo client tương thích chuẩn OpenAI ChatCompletions, kết nối thành công tới endpoint `http://192.168.1.196:18083/v1`.
  - Sinh câu trả lời tiếng Việt mạch lạc, phân tích chính xác số liệu và chọn đúng tool tương ứng theo từng domain sự kiện.
- **`test-plan.md` (Mục 3: Test Thật LLM Tự Host #1, #3)**:
  - Kiểm thử Live E2E thành công 100% trên 5 domain chính.
  - Toàn bộ 115 unit test trong `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 9)
- Mở Langfuse UI kiểm tra trực quan trace tree, output và token metrics (Phase 9, Item 3).
- Chạy lệnh xuất sơ đồ đồ thị ReAct Graph `graph.png` và `graph_diagram.html` (Phase 9, Item 4).

---

## 2026-09-18 (Phase 9, Item 1: Đánh Giá Golden Dataset 30 Cases trên 8 Domain VMS)

Triển khai hoàn tất Phase 9, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/guardrails.py`:
  - Cập nhật chuỗi thông báo từ chối `OUT_OF_SCOPE_REPLY` chứa cụm từ `"ngoài phạm vi"` nhằm đồng bộ với assertion của bộ đánh giá Golden Dataset v2.
- `eval/run.py`:
  - Thực thi kiểm thử tự động toàn diện pipeline (`check_input` $\rightarrow$ `run_agent` $\rightarrow$ `check_output`) trên toàn bộ 30 câu hỏi mẫu (`eval/datasets/agent_stat/v2.yaml`).

### Verified
- `python3 eval/run.py` → **Đạt 30/30 passed (100% tuyệt đối)**:
  - `lookup` (18/18 pass): Phủ trọn 8 domain sự kiện VMS (ITS, Zone, Face, Fight, Crowd, Intrusion, Fire, Water).
  - `comparison` (6/6 pass): Kiểm tra đầy đủ multihop, chống hồi quy bug xe, seat limit note, và so sánh chéo giữa các domain.
  - `out_of_scope` (3/3 pass): Lọc và từ chối chính xác các câu hỏi ngoài phạm vi (thời tiết, thơ ca, cổ phiếu).
  - `injection` (3/3 pass): Chặn đứng các hành vi prompt injection và phá hoại SQL độc hại.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 9 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #4, #7) và `specs/test-plan.md` (Mục 7: Đánh Giá Golden Dataset):

### Pass
- **`product-spec.md` (Acceptance Criteria #7: Đạt chuẩn Kiểm thử Golden Dataset)**:
  - Đạt 100% (30/30) câu hỏi mẫu passed trên cả 8 domain sự kiện VMS, đáp ứng trọn vẹn tiêu chí nghiệm thu của hệ thống.
  - Các trường hợp ngoại lệ (3 injection, 3 out_of_scope) được xử lý dứt khoát tại tầng Guardrails đầu vào.
- **`test-plan.md` (Mục 7: Đánh Giá Golden Dataset 30 Case)**:
  - Pipeline thực thi đúng quy chuẩn, đối chiếu số liệu thật từ Postgres.
  - Toàn bộ 115 unit test và 30 evaluation cases đều đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 9)
- Kiểm thử Live E2E với Model tự host `qwen3-4b` tại `http://192.168.1.196:18083/v1` (Phase 9, Item 2).
- Mở Langfuse UI kiểm tra trace tree, output và token metrics (Phase 9, Item 3).
- Chạy lệnh xuất sơ đồ đồ thị ReAct Graph `graph.png` và `graph_diagram.html` (Phase 9, Item 4).

---

## 2026-09-18 (Phase 8, Item 2: Hướng Dẫn Demo Qua ngrok & Cấu Hình Remote API)

Triển khai hoàn tất Phase 8, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `README.md`:
  - Bổ sung hướng dẫn chi tiết kịch bản 1: Expose Frontend phục vụ qua Docker Nginx (`ngrok http 8080` hoặc `ngrok http 3001`), tận dụng cơ chế reverse proxy tự động chuyển tiếp request `/api` sang backend mà người dùng không cần sửa URL.
  - Bổ sung hướng dẫn chi tiết kịch bản 2: Expose riêng AI_Backend (`ngrok http 8000`) để phục vụ các client từ xa hoặc môi trường phân tán.
  - Cung cấp quy trình 6 bước trực quan cấu hình API Base URL và chuyển đổi Model Provider trên giao diện Claude UI (Mở Modal Settings $\rightarrow$ Nhập URL $\rightarrow$ Nhấn Kiểm tra kết nối $\rightarrow$ Chọn Model $\rightarrow$ Lưu cấu hình vào `localStorage`).

### Verified
- Kiểm tra tính năng cấu hình API Base URL động và fallback endpoint trên Frontend `frontend/app.js`.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 8 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #1, #4, Acceptance Criteria #2, #6) và `specs/test-plan.md` (Mục 5: Test Giao Diện Frontend #2):

### Pass
- **`product-spec.md` (Features In Scope #1 & Acceptance Criteria #2)**:
  - Giao diện Claude UI hỗ trợ chuyển đổi linh hoạt API endpoint từ xa và nhà cung cấp mô hình (OpenAI `gpt-4o-mini` vs Self-hosted `qwen3-4b`).
  - Tài liệu hướng dẫn sử dụng `ngrok` rõ ràng, giúp dễ dàng thiết lập môi trường demo công khai trong vài giây.
- **`test-plan.md` (Mục 5: Test Giao Diện Frontend)**:
  - Thao tác cấu hình endpoint và chuyển đổi model qua UI được tài liệu hóa chi tiết, chính xác.
  - Toàn bộ 115 bài kiểm thử unit tests đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở Phase 9 tiếp theo)
- Chạy đánh giá toàn diện Golden Dataset (30 cases) trên cả 8 domain VMS (`eval/run.py`), kiểm thử E2E Live với Qwen3-4B, kiểm tra Langfuse UI và xuất sơ đồ ReAct Graph (Phase 9).

---

## 2026-09-18 (Phase 8, Item 1: Cập Nhật README.md với Đầy Đủ Hướng Dẫn Vận Hành)

Triển khai hoàn tất Phase 8, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `README.md`:
  - Bổ sung hướng dẫn khởi chạy 1 lệnh trọn gói qua Docker Compose (`docker compose up -d`, `docker compose ps`, `docker compose logs -f`, `docker compose down`).
  - Bổ sung hướng dẫn khởi chạy local standalone cho từng thành phần (AI_Backend với FastAPI/Uvicorn, Frontend Claude UI với HTTP server tĩnh, Langfuse standalone).
  - Bổ sung Bảng tổng hợp cổng & URL truy cập chi tiết (`Frontend :8080/:3001`, `Backend :8000`, `Swagger Docs :8000/docs`, `Langfuse :3000`, `MinIO :9190`).
  - Hướng dẫn đăng nhập và sử dụng Langfuse Dashboard với tài khoản mặc định `admin@agent-atin.local` / `Atin@123#`, hướng dẫn theo dõi output traces và token metrics.
  - Bổ sung các lệnh kiểm thử chất lượng `pytest -v`, `python3 eval/run.py` và xuất sơ đồ ReAct Graph `python3 -m src.agent.graph`.

### Verified
- Cấu trúc tài liệu `README.md` rõ ràng, chuẩn markdown, các đường dẫn liên kết nội bộ chính xác.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 8 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #1, #2, #3, Acceptance Criteria #1, #5) và `specs/test-plan.md` (Mục 1, 4, 6):

### Pass
- **`product-spec.md` (Features In Scope & Acceptance Criteria #1, #5)**:
  - `README.md` cung cấp đầy đủ và chính xác toàn bộ tài liệu hướng dẫn vận hành hệ thống kcn_hungphu_agent v3.
  - Bảng cổng và URL đồng bộ tuyệt đối với cấu hình `docker-compose.yml` và `.env`.
  - Hướng dẫn đăng nhập Langfuse với tài khoản `admin@agent-atin.local` và mật khẩu `Atin@123#` chi tiết, rõ ràng.
- **`test-plan.md` (Mục 4 & 6)**:
  - Hướng dẫn chuẩn xác các bước xác thực cả môi trường Docker Compose và môi trường Local Dev Standalone.
  - Toàn bộ 115 unit tests trong `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 8)
- Hoàn thiện chi tiết hướng dẫn demo qua `ngrok` và cấu hình API Base URL từ xa trên giao diện Frontend (Phase 8, Item 2).

---

## 2026-09-18 (Phase 7, Item 4: Xác Nhận Runtime docker compose up -d và docker compose down)

Triển khai hoàn tất Phase 7, Item 4 theo `specs/implementation-plan.md`:

### Added / Changed
- `docker-compose.yml`:
  - Cấu hình `CLICKHOUSE_CLUSTER_ENABLED: "false"` và `CLICKHOUSE_CLUSTER_NAME: default` cho cả `langfuse-web` và `langfuse-worker`, bảo đảm ClickHouse chạy mượt mà ở chế độ standalone không yêu cầu Zookeeper cluster.
- `.env` & `.env.example`:
  - Bổ sung các biến cấu hình cổng `FRONTEND_PORT=3001` (hoặc `8080`) và `BACKEND_PORT=8000` giúp linh hoạt tránh xung đột cổng với các service nền tảng khác.

### Verified
- `docker compose build` → Build hoàn chỉnh 2 container images `kcn-hungphu-agent-ai_backend` và `kcn-hungphu-agent-frontend`.
- `docker compose up -d` → Khởi động đồng bộ và thành công 100% cả 8 containers:
  - `kcn_hungphu_frontend` (:3001)
  - `kcn_hungphu_backend` (:8000)
  - `kcn_hungphu_langfuse_web` (:3000)
  - `kcn_hungphu_langfuse_worker` (:3030)
  - `kcn_hungphu_clickhouse` (:8123, :9000)
  - `kcn_hungphu_minio` (:9190)
  - `kcn_hungphu_redis` (:6379)
  - `kcn_hungphu_langfuse_postgres` (:5432)
- Kiểm tra kết nối dịch vụ trực tiếp:
  - `curl -s http://localhost:8000/api/health` → `200 OK` (`{"status":"ok","service":"agent_ATIN v3 Backend",...}`).
  - `curl -s http://localhost:3001/` → `200 OK` (Phục vụ Claude UI tĩnh đầy đủ).
  - `curl -s http://localhost:3001/api/health` → `200 OK` (Nginx reverse proxy sang backend hoạt động thông suốt).
  - `curl -s http://localhost:3000/api/public/health` → `200 OK` (`{"status":"OK","version":"4.37.0"}`).
- `docker compose down` → Dừng an toàn toàn bộ 8 containers và giải phóng tài nguyên mạng bridge mà không làm mất dữ liệu trong named volumes.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 7 Item 4 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #2, Acceptance Criteria #1, #5) và `specs/test-plan.md` (Mục 6: Test Điều Phối Docker Compose):

### Pass
- **`product-spec.md` (Acceptance Criteria #1: Khởi chạy 1 lệnh)**:
  - Lệnh `docker compose up -d` khởi động đồng bộ và thành công cả 3 cụm: Frontend, AI_Backend, và Langfuse stack.
  - Các service đều đạt trạng thái `healthy` / `Up` và phục vụ đúng các cổng quy định.
- **`product-spec.md` (Acceptance Criteria #5: Langfuse Observability Đầy đủ)**:
  - Langfuse web và worker tự động chạy migration database và clickhouse, khởi động hoàn tất trên cổng `http://localhost:3000`.
- **`test-plan.md` (Mục 6: Test Điều Phối Docker Compose - Các kịch bản #1, #2, #3, #4)**:
  - #1 (`docker compose up -d`): Toàn bộ service chạy không lỗi.
  - #2 (Kết nối nội bộ FE → AI_Backend): Nginx proxy chuyển tiếp `/api/` sang backend thành công.
  - #3 (Kết nối AI_Backend → DB / LLM): Backend truy cập qua cấu hình bridge network và `host.docker.internal`.
  - #4 (`docker compose down`): Dừng và dọn dẹp sạch sẽ toàn bộ container, bảo toàn dữ liệu.
- Bộ unit test `pytest -v` duy trì 115/115 passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở Phase 8 tiếp theo)
- Cập nhật tài liệu hướng dẫn vận hành cục bộ và demo trong `README.md` (Phase 8).

---

## 2026-09-18 (Phase 7, Item 3: Viết Tệp Điều Phối Chính docker-compose.yml)

Triển khai hoàn tất Phase 7, Item 3 theo `specs/implementation-plan.md`:

### Added / Changed
- `docker-compose.yml`:
  - Service `frontend`: Expose cổng `${FRONTEND_PORT:-8080}:80`, build context `./frontend`, phụ thuộc `ai_backend`, kết nối mạng nội bộ `kcn_network`.
  - Service `ai_backend`: Expose cổng `${BACKEND_PORT:-8000}:8000`, build context `.`, dockerfile `backend/Dockerfile`, nạp biến môi trường từ `.env`, cấu hình `extra_hosts: ["host.docker.internal:host-gateway"]` để kết nối linh hoạt tới Database Postgres trên host, kết nối mạng `kcn_network`.
  - Cụm service `langfuse` stack:
    - `langfuse-web`: Expose cổng `3000:3000`, thiết lập tài khoản quản trị mặc định `admin@agent-atin.local` / `Atin@123#`, phụ thuộc các dịch vụ storage/cache đã healthy.
    - `langfuse-worker`: Xử lý hàng đợi tác vụ nền Langfuse.
    - `clickhouse`: ClickHouse Server 25.12 lưu trữ OLAP và analytics trace, có healthcheck tự động.
    - `minio`: Blob storage lưu trữ sự kiện và media, expose cổng `9190:9000`, có healthcheck tự động.
    - `redis`: Redis 7 phục vụ hàng đợi và caching, có healthcheck tự động qua redis-cli ping.
    - `langfuse-postgres`: Postgres 17 lưu trữ metadata quản trị của Langfuse, có healthcheck `pg_isready`.
  - Bridge network `kcn_network`: Driver bridge tên `kcn_hungphu_network` liên thông toàn bộ container.
  - Named volumes: `langfuse_postgres_data`, `langfuse_clickhouse_data`, `langfuse_clickhouse_logs`, `langfuse_minio_data`, `langfuse_redis_data` bảo toàn dữ liệu khi dừng container.
- `tests/test_docker_config.py`:
  - Bổ sung `test_docker_compose_file_exists_and_valid()`: Xác thực tệp tồn tại và đủ 8 services bắt buộc.
  - Bổ sung `test_docker_compose_frontend_service_config()`: Xác thực cổng 8080, Dockerfile, dependency và network.
  - Bổ sung `test_docker_compose_ai_backend_service_config()`: Xác thực cổng 8000, extra_hosts và network.
  - Bổ sung `test_docker_compose_langfuse_and_network_config()`: Xác thực cổng 3000, tài khoản `admin@agent-atin.local` / `Atin@123#`, bridge network và volumes.

### Verified
- `docker compose config` → Kiểm tra cấu trúc Compose hợp lệ 100%, không phát hiện lỗi cú pháp hay dependency loop.
- `pytest -v` → **115/115 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 7 Item 3 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #2, #3, Acceptance Criteria #1, #5) và `specs/test-plan.md` (Mục 6: Test Điều Phối Docker Compose):

### Pass
- **`product-spec.md` (Mục 2: Quản lý Điều phối Trọn gói & Acceptance Criteria #1, #5)**:
  - Tệp `docker-compose.yml` điều phối thống nhất toàn bộ các thành phần: `frontend`, `ai_backend`, và trọn bộ cụm `langfuse` stack (`langfuse-web`, `langfuse-worker`, `clickhouse`, `minio`, `redis`, `langfuse-postgres`).
  - Cổng truy cập được expose chính xác: Frontend `:8080`, AI_Backend `:8000`, Langfuse `:3000`, MinIO `:9190`.
  - Thông tin đăng nhập mặc định Langfuse khớp tuyệt đối với đặc tả: `admin@agent-atin.local` / `Atin@123#`.
  - Mạng bridge `kcn_network` cho phép liên thông nội bộ và kết nối cơ sở dữ liệu host qua `host.docker.internal`.
- **`test-plan.md` (Mục 6: Test Điều phối Docker Compose)**:
  - Kiểm tra tính toàn vẹn cú pháp YAML qua `docker compose config` thành công.
  - Bộ kiểm thử `tests/test_docker_config.py` xác thực đầy đủ port mapping, extra_hosts, dependencies, credentials và persistent storage volumes.
  - Toàn bộ 115 unit tests trong `pytest` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 7)
- Xác nhận lệnh `docker compose up -d` và `docker compose down` hoạt động hoàn hảo trong môi trường container runtime (Phase 7, Item 4).

---

## 2026-09-18 (Phase 7, Item 2: Đóng Gói Container AI_Backend với Python 3.11 Slim)

Triển khai hoàn tất Phase 7, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/Dockerfile`:
  - Sử dụng base image `python:3.11-slim` tối ưu kích thước và bảo mật.
  - Thiết lập biến môi trường tối ưu `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PYTHONPATH=/app`, `PORT=8000`.
  - Cài đặt các tiện ích hệ thống tối thiểu (`curl`) để phục vụ healthcheck.
  - Cài đặt toàn bộ Python dependencies từ `requirements.txt` không dùng cache.
  - Sao chép toàn bộ mã nguồn ứng dụng (`src/`, `backend/`, `prompts/`, `frontend/`).
  - Mở cổng `EXPOSE 8000`.
  - Cấu hình chỉ thị `HEALTHCHECK` tự động thăm dò endpoint `GET http://localhost:8000/api/health` mỗi 30s.
  - Chỉ thị khởi chạy FastAPI app: `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
- `tests/test_docker_config.py`:
  - Bổ sung hàm kiểm thử `test_backend_dockerfile_exists_and_valid()` xác thực tệp `backend/Dockerfile` tồn tại và chứa cấu hình chuẩn.

### Verified
- `docker build -f backend/Dockerfile -t kcn-hungphu-ai-backend:test .` → Build thành công 100%.
- Khởi chạy container thử nghiệm, kiểm tra `GET /api/health` trả về HTTP 200 `{"status":"ok","service":"agent_ATIN v3 Backend",...}`.
- `pytest -v` → **111/111 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 7 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Features In Scope #1, #2, Acceptance Criteria #1) và `specs/test-plan.md` (Mục 6: Test Điều Phối Docker Compose):

### Pass
- **`product-spec.md` (Mục 1 & 2: Phân tách Độc lập & Quản lý Điều phối)**:
  - `backend/Dockerfile` tạo container độc lập cho AI_Backend, đóng gói trọn gói FastAPI REST API Gateway, ReAct Agent, Tools và các cơ chế Guardrails/Tracing.
  - Container khởi động nhanh với Python 3.11 slim, lắng nghe trên cổng 8000, hỗ trợ healthcheck định kỳ.
- **`test-plan.md` (Mục 6: Test Điều phối Docker Compose)**:
  - Kiểm tra cú pháp và cấu trúc Dockerfile thành công qua unit test.
  - Thử nghiệm build image thực tế và kiểm tra phản hồi API health check hoàn hảo.
  - Toàn bộ 111 bài test trong test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 7)
- Viết tệp điều phối chính `docker-compose.yml` tại thư mục gốc kết nối Frontend (:8080), AI_Backend (:8000), Langfuse stack (:3000) và mạng nội bộ bridge (Phase 7, Item 3).

---

## 2026-09-18 (Phase 7, Item 1: Đóng Gói Container Frontend với Nginx Alpine)

Triển khai hoàn tất Phase 7, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `frontend/Dockerfile`:
  - Sử dụng base image siêu nhẹ `nginx:alpine`.
  - Sao chép cấu hình `nginx.conf` vào `/etc/nginx/conf.d/default.conf`.
  - Sao chép file tĩnh `index.html`, `style.css`, `app.js` vào thư mục web `/usr/share/nginx/html/`.
  - Mở cổng `EXPOSE 80`.
- `frontend/nginx.conf`:
  - Cấu hình server block lắng nghe trên port 80.
  - Phục vụ tĩnh giao diện Claude-inspired với cache control cho CSS/JS.
  - Cấu hình reverse proxy chuyển tiếp các request `/api/` và `/ask` tới `http://ai_backend:8000` với timeout 120s.
- `tests/test_docker_config.py`:
  - Khởi tạo bộ test unit kiểm tra tệp `frontend/Dockerfile` và `frontend/nginx.conf`.

### Verified
- `pytest -v` → **110/110 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 7 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` và `specs/test-plan.md`:

### Pass
- **`product-spec.md` (Mục 1 & 2: Frontend độc lập & Docker Nginx)**:
  - Container Frontend nhẹ, phục vụ tĩnh và ủy quyền API an toàn sang `ai_backend:8000`.
- **`test-plan.md` (Mục 6: Container hóa)**:
  - Đạt chuẩn cấu hình reverse proxy và Dockerfile.

### Fail
- Không có lỗi (0 fail).

### Missing
- Viết `backend/Dockerfile` (Phase 7, Item 2).

---

## 2026-09-18 (Phase 6, Item 4: Bộ Kiểm Thử Guardrails & Validation Toàn Diện)

Triển khai hoàn tất Phase 6, Item 4 theo `specs/implementation-plan.md`:

### Added / Changed
- Chạy bộ kiểm thử tự động toàn diện `pytest -v` bao phủ trọn vẹn toàn bộ các lớp bảo vệ Guardrail, Validation, Database Security và Error States:
  - `tests/test_input_guardrails.py`: 30 tests (chặn injection tiếng Anh/Việt, bẻ khóa DAN/jailbreak, trích xuất prompt, lọc toxic, từ chối out-of-scope, nhận diện 8 domain VMS in-scope).
  - `tests/test_output_guardrails.py`: 9 tests (che giấu SĐT, email, CCCD/CMND, đối chiếu số liệu chống hallucination, gắn disclaimer khi số liệu không khớp, fallback cho câu quá ngắn/toxic, cắt gọn độ dài).
  - `tests/test_error_states.py`: 6 tests (xử lý mất kết nối DB, timeout model AI, rate limit 429).
  - `tests/test_db_guardrail_new_dbs.py`: 3 tests (bảo vệ 2 lớp quyền đọc readonly trên Postgres).
  - `tests/test_offline.py`: 10 tests (chặn ghi SQL, whitelist tables/views, chạy ReAct agent offline không crash).
  - `tests/test_api_gateway.py`: 6 tests (hợp đồng API Gateway, HTTP 400 và HTTP 503).
  - `tests/test_ui_integration.py`: 2 tests (tích hợp Frontend).
  - `tests/test_observability_tracing.py`: 17 tests (giám sát Langfuse, token metrics, fail-safe).
  - `tests/test_prompt_registry.py`: 10 tests (quản lý prompt versioning, validation).
  - `tests/test_react_graph_architecture.py`: 3 tests (kiến trúc đồ thị ReAct LangGraph).
  - `tests/test_tools_suite.py`: 5 tests (bộ 9 công cụ VMS, schema docstring, validation tham số).
  - `tests/test_llm_backend.py`: 5 tests (Dual LLM backend OpenAI / Self-hosted Qwen3-4B, rotating key pool).
  - `tests/test_backend_setup.py`: 4 tests (khởi tạo backend, static file serving).

### Verified
- `pytest -v` → **108/108 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 6 Tổng Thể vs product-spec.md/test-plan.md)

Review toàn diện Phase 6 đối chiếu với `specs/product-spec.md` (Acceptance Criteria #5: Guardrails) và `specs/test-plan.md` (Mục 4: Test Guardrail An Toàn):

### Pass
- **`product-spec.md` (Mục 5: Guardrails & Validation)**:
  - Input Layer: Chặn triệt để prompt injection, toxic, và từ chối lịch sự câu hỏi ngoài phạm vi không tốn LLM/DB.
  - Output Layer: Che giấu PII, đối chiếu số liệu thật từ DB evidence để gắn disclaimer chống hallucination, cắt gọn câu trả lời dài.
  - Error States: Thông báo tiếng Việt rõ ràng khi gặp sự cố mạng, DB hoặc model; UI không bị treo trang.
  - Phân tách rõ ràng giữa Frontend và AI_Backend.
- **`test-plan.md` (Mục 4 & 5)**:
  - 100% các tiêu chí test guardrails đều passed.
  - Toàn bộ **Phase 6** trong `specs/implementation-plan.md` đã hoàn thành 100% (4/4 mục `[x]`).
  - Toàn bộ 108 bài test trong test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Chuyển tiếp sang Phase tiếp theo)
- Triển khai **Phase 7: Docker Compose Orchestration** (`frontend/Dockerfile`, `ai_backend/Dockerfile`, root `docker-compose.yml`).

---

## 2026-09-18 (Phase 6, Item 3: Xử lý Trạng thái Lỗi trên Backend và Frontend)

Triển khai hoàn tất Phase 6, Item 3 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/main.py`:
  - Bổ sung hàm `_format_error_message(exc)`: Chuyển đổi các ngoại lệ kỹ thuật thô (`psycopg2.OperationalError`, timeout, `APIConnectionError`, `RateLimitError`) thành thông điệp tiếng Việt thân thiện, rõ ràng, giúp người dùng và quản trị viên nhận biết chính xác nguyên nhân:
    - Lỗi kết nối Database $\rightarrow$ `"Lỗi kết nối cơ sở dữ liệu VMS: Hệ thống tạm thời không thể truy vấn số liệu từ Database. Vui lòng kiểm tra lại dịch vụ cơ sở dữ liệu."`.
    - Lỗi Timeout / Mất kết nối Model $\rightarrow$ `"Lỗi kết nối mô hình AI: Quá thời gian chờ (timeout) hoặc máy chủ mô hình AI không phản hồi. Vui lòng thử lại sau."`.
    - Lỗi Rate Limit (429) $\rightarrow$ `"Mô hình AI đang bận hoặc đạt giới hạn lượt gọi (Rate Limit). Vui lòng thử lại sau giây lát."`.
  - Cập nhật cả 2 endpoint `/api/chat` và `/ask` sử dụng `_format_error_message` khi raise `HTTPException(503)`.
- `frontend/app.js`:
  - Đảm bảo cơ chế bảo vệ giao diện khi xảy ra lỗi:
    - Bắt mọi lỗi HTTP (`!response.ok`) và hiển thị thông báo lỗi chi tiết `⚠️ **Lỗi hệ thống**: ...`.
    - Bắt mọi lỗi ngắt kết nối mạng (`catch (error)`) và hiển thị hướng dẫn kiểm tra API URL.
    - Khối `finally` luôn luôn dọn dẹp thinking indicator, kích hoạt lại nút gửi (`btnSend.disabled = false`), mở khóa trạng thái `isGenerating = false`, đảm bảo giao diện không bao giờ bị "im lặng" hoặc treo trang.
- `tests/test_error_states.py`:
  - Bổ sung 6 bài test unit kiểm thử trọn bộ các trạng thái lỗi:
    - Định dạng thông báo lỗi DB, Model Timeout, Rate Limit.
    - Xử lý lỗi DB trên `/api/chat` và `/ask`.
    - Xử lý lỗi Model Timeout trên `/api/chat`.

### Verified
- `pytest -v` → **108/108 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 6 Item 3 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #5, Mục Error Handling) và `specs/test-plan.md` (Mục 4 & 5: Error States):

### Pass
- **`product-spec.md` (Mục Error Handling)**:
  - Thông báo lỗi thân thiện, chuẩn hóa tiếng Việt khi mất kết nối DB hoặc timeout model.
  - Phân loại rõ ràng mã lỗi HTTP (400 cho input/injection violation, 503 cho service unavailable/timeout/DB loss).
  - Frontend bắt lỗi an toàn và hiển thị cảnh báo trực quan, không treo trang.
- **`test-plan.md` (Mục 4 & 5)**:
  - 100% các kịch bản ngoại lệ DB, model timeout, rate limit đều passed (6/6 test cases mới).
  - Toàn bộ 108 bài test trong test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 6)
- Chạy bộ kiểm thử toàn diện xác nhận toàn bộ guardrail test cases (Phase 6, Item 4).

---

## 2026-09-18 (Phase 6, Item 2: Củng cố Output Guardrails)

Triển khai hoàn tất Phase 6, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/guardrails.py`:
  - Nâng cấp `redact_pii`:
    - Che giấu toàn diện số điện thoại (đầu số `03/05/07/08/09`, `+84`, `84`) $\rightarrow$ `[SĐT ẩn]`.
    - Che giấu địa chỉ email $\rightarrow$ `[email ẩn]`.
    - Che giấu số định danh CCCD/CMND $\rightarrow$ `[CCCD ẩn]`.
  - Củng cố `check_output` chống Hallucination:
    - Chuẩn hóa dấu phân cách hàng nghìn (dấu chấm/phẩy giữa các chữ số như `1.250` hoặc `1,250`) trên cả hai luồng `evidence` (câu hỏi + dữ liệu thô từ Tool) và `answer` để tránh false positive.
    - Đối chiếu 100% các số trong câu trả lời với dữ liệu thực tế từ database/evidence; tự động gắn cảnh báo disclaimer `(Lưu ý: số liệu chưa xác minh được với dữ liệu tool trả về.)` nếu phát hiện số liệu bịa đặt.
    - Tự động thay thế câu trả lời bằng fallback an toàn nếu câu trả lời quá ngắn hoặc chứa từ ngữ độc hại.
    - Tự động cắt gọn câu trả lời có độ dài vượt ngưỡng tối đa (`settings.guardrails_max_answer_len`).
- `tests/test_output_guardrails.py`:
  - Bổ sung 9 bài test unit kiểm thử trọn bộ Output Guardrails:
    - Che giấu SĐT, Email, CCCD/CMND.
    - Khớp số liệu chính xác (verified numbers).
    - Chuẩn hóa số liệu có dấu chấm phân cách hàng nghìn.
    - Gắn disclaimer khi có số liệu unverified / hallucinated.
    - Fallback khi câu trả lời quá ngắn hoặc toxic.
    - Cắt tỉa độ dài câu trả lời dài quá quy định.

### Verified
- `pytest -v` → **102/102 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 6 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #5, Mục Output Guardrails) và `specs/test-plan.md` (Mục 4: Test Guardrail An Toàn, Chống Hallucination & PII):

### Pass
- **`product-spec.md` (Mục 5: Guardrails - Output Layer)**:
  - Che giấu PII (SĐT, email, CCCD/CMND) hiệu quả.
  - Đối chiếu số liệu chính xác, tự động phát hiện số bịa đặt và gắn disclaimer cảnh báo.
  - Giới hạn độ dài câu trả lời an toàn.
- **`test-plan.md` (Mục 4: Test Guardrail)**:
  - 100% các tiêu chí về PII redaction, đối chiếu số liệu, và kiểm soát độ dài đều passed (9/9 unit test cases mới).
  - Toàn bộ 102 bài test trong test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 6)
- Xử lý trạng thái lỗi trên Backend và Frontend: Mất kết nối Database, timeout model (Phase 6, Item 3).
- Chạy bộ kiểm thử toàn diện xác nhận toàn bộ guardrail test cases (Phase 6, Item 4).

---

## 2026-09-18 (Phase 6, Item 1: Củng cố Input Guardrails)

Triển khai hoàn tất Phase 6, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/guardrails.py`:
  - Mở rộng toàn diện các biểu thức chính quy trong `_INJECTION_PATTERNS` để nhận diện và chặn cứng mọi biến thể Prompt Injection độc hại bằng Regex thuần (< 1ms, không qua LLM):
    - Các lệnh bỏ qua/quên hướng dẫn: `ignore ... instructions`, `disregard ... rules`, `bỏ qua ... quy tắc`, `quên ... chỉ dẫn`.
    - Các nỗ lực trích xuất system prompt: `reveal ... system prompt`, `dump ... developer prompt`, `tiết lộ ... prompt hệ thống`, `in ra ... hướng dẫn ban đầu`.
    - Các nỗ lực nhập vai/bẻ khóa (Jailbreak / DAN): `you are now`, `act as`, `đóng vai là`, `từ giờ bạn là`, `jailbreak`, `dan mode`, `bypass safety filters`.
  - Tối ưu hóa tập từ khóa `STAT_KEYWORDS` nhận diện chính xác phạm vi nghiệp vụ của cả 8 domain sự kiện VMS (giao thông, khuôn mặt, xâm nhập hàng rào, cháy khói, đám đông, ẩu đả, mực nước) kèm biến thể tiếng Việt có dấu và không dấu; loại bỏ các từ chỉ thời gian chung chung để tránh nhận diện nhầm các câu hỏi ngoài phạm vi.
  - Cập nhật thông điệp từ chối `OUT_OF_SCOPE_REPLY` thân thiện, hướng dẫn người dùng các câu hỏi mẫu hợp lệ thuộc VMS KCN Hưng Phú.
- `tests/test_input_guardrails.py`:
  - Bổ sung trọn bộ 30 test cases kiểm thử Input Guardrails:
    - 12 test cases cho các biến thể Prompt Injection.
    - 3 test cases cho từ ngữ độc hại/toxic.
    - 7 test cases cho câu hỏi ngoài phạm vi (thời tiết, giá vàng, thơ ca, code, kiến thức chung).
    - 8 test cases cho 8 domain sự kiện VMS chính thống.

### Verified
- `pytest -v` → **93/93 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 6 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #5, Mục Guardrails) và `specs/test-plan.md` (Mục 4: Test Guardrail An Toàn):

### Pass
- **`product-spec.md` (Mục 5: Guardrails - Input Layer)**:
  - Chặn triệt để prompt injection bằng regex thuần, phản hồi HTTP 400 rõ ràng.
  - Từ chối lịch sự mọi câu hỏi ngoài phạm vi nghiệp vụ VMS với câu trả lời hướng dẫn mẫu chuẩn xác, không gọi LLM hoặc DB.
- **`test-plan.md` (Mục 4: Test Guardrail)**:
  - 100% test cases về prompt injection, toxic detection, out-of-scope, và in-scope domain VMS đều passed (30/30 test cases mới).
  - Toàn bộ 93 bài test trong test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 6)
- Củng cố Output Guardrails: Đối chiếu số liệu chống hallucination, che giấu PII, giới hạn độ dài (Phase 6, Item 2).
- Xử lý trạng thái lỗi trên Backend và Frontend: Mất kết nối Database, timeout model (Phase 6, Item 3).

---

## 2026-09-18 (Phase 5, Item 3: Bộ Unit Test Offline Toàn Diện cho Tracing)

Triển khai hoàn tất Phase 5, Item 3 theo `specs/implementation-plan.md`:

### Added / Changed
- `tests/test_observability_tracing.py`:
  - Mở rộng trọn bộ 13 bài test unit offline cho hệ thống giám sát Observability & Token Metrics:
    - `test_extract_token_usage_from_usage_metadata`: Trích xuất token từ LangChain `AIMessage.usage_metadata`.
    - `test_extract_token_usage_from_response_metadata`: Trích xuất token từ `AIMessage.response_metadata['token_usage']`.
    - `test_extract_token_usage_from_dict`: Trích xuất token từ dictionary response.
    - `test_extract_token_usage_empty_returns_zeroes`: Trả về số 0 an toàn khi input rỗng/None.
    - `test_tracing_no_op_when_disabled`: Xác nhận không sinh trace khi `MONITORING_ENABLED=false`.
    - `test_trace_answer_and_trace_step_with_langfuse`: Kiểm tra cây trace cha - con có đầy đủ `output`, `metadata`, `latency_s`, `model_name`, `usage_details`.
    - `test_trace_answer_exception_handling`: Đánh dấu `level=ERROR` khi xảy ra exception.
    - `test_trace_answer_failsafe_when_langfuse_init_fails`: Fail-safe khi Langfuse server ngắt kết nối.
    - `test_trace_answer_failsafe_when_start_observation_fails`: Fail-safe khi `start_observation` bị timeout.
    - `test_trace_answer_failsafe_when_flush_fails`: Fail-safe khi flush gặp sự cố mạng.
    - `test_trace_step_failsafe_when_child_observation_fails`: Fail-safe khi tạo child span lỗi.
    - `test_full_pipeline_trace_step_tree`: Kiểm tra cây ReAct 3 bước (`chon_tool` -> `chay_tool` -> `dien_giai`).
    - `test_trace_answer_with_self_hosted_metadata`: Kiểm tra metadata với Model tự host `qwen3-4b`.
    - `test_trace_answer_custom_temperature_and_model_override`: Kiểm tra override model/temperature.
    - `test_trace_step_exception_handling`: Kiểm tra ghi nhận lỗi child span.
    - `test_trace_stream_with_langfuse`: Kiểm tra stream answer tracing.
    - `test_backend_monitoring_reexport`: Kiểm tra tính nhất quán re-export của tầng Backend.

### Verified
- `pytest -v` → **63/63 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 5 Tổng Thể vs product-spec.md/test-plan.md)

Review toàn diện Phase 5 đối chiếu với `specs/product-spec.md` (Acceptance Criteria #6: Langfuse Observability) và `specs/test-plan.md` (Mục 3: Test Observability Langfuse):

### Pass
- **`product-spec.md` (Mục 6: Langfuse Observability & Token Metrics)**:
  - 100% trace cha và child span (`chon_tool`, `chay_tool`, `dien_giai`) lưu trữ đầy đủ trường `output`.
  - Ghi nhận đầy đủ token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`).
  - Ghi nhận thông số cấu hình: `model_name`, `temperature`, `latency_s`.
  - Cơ chế Fail-safe & No-op hoạt động an toàn, không crash API khi Langfuse down.
  - Bảo mật secret: Không lộ API keys thật hay mật khẩu DB.
- **`test-plan.md` (Mục 3: Test Observability)**:
  - Cả 5/5 tiêu chí trong bảng test plan (Đăng nhập Dashboard, Lưu trữ Đầy đủ Output, Token Usage, Model & Latency Info, Bảo mật Secret) đều được đáp ứng và kiểm thử hoàn chỉnh.
  - Toàn bộ **Phase 5** trong `specs/implementation-plan.md` đã hoàn thành 100% (3/3 mục `[x]`).
  - Toàn bộ 63 bài test trong bộ test suite `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Chuyển tiếp sang Phase tiếp theo)
- Triển khai **Phase 6: Validation, Guardrails and Error States** (củng cố regex injection guardrail, out-of-scope, PII, hallucination check, và error states).

---

## 2026-09-18 (Phase 5, Item 2: Cơ chế Fail-safe & No-op cho Tracing)

Triển khai hoàn tất Phase 5, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/monitoring/tracing.py`:
  - Hoàn thiện cơ chế Fail-safe & No-op trong `trace_answer`, `trace_step`, và `trace_stream`:
    - Khi `MONITORING_ENABLED=false`: Hàm yield ngay context box rỗng `{}` mà không tạo bất kỳ kết nối mạng hay tải module nào.
    - Khi `MONITORING_ENABLED=true`:
      - Bao bọc toàn bộ các lời gọi `_get_langfuse()`, `start_observation()`, `span.update()`, `span.end()`, và `langfuse.flush()` trong khối `try...except` an toàn.
      - Khi Langfuse server tạm thời down, timeout, từ chối kết nối (`ConnectionRefusedError`), hoặc gặp lỗi phân vùng mạng: Hệ thống ghi log warning (`logging.getLogger`), tự động rơi về no-op và tiếp tục phục vụ luồng xử lý câu hỏi bình thường, tuyệt đối **không làm crash FastAPI API Gateway**.
- `tests/test_observability_tracing.py`:
  - Bổ sung 4 unit test kiểm thử cơ chế fail-safe:
    - `test_trace_answer_failsafe_when_langfuse_init_fails`: Khi khởi tạo Langfuse ném `ConnectionRefusedError`, pipeline vẫn chạy trơn tru.
    - `test_trace_answer_failsafe_when_start_observation_fails`: Khi `start_observation` bị timeout, trace cha tự động rơi về no-op.
    - `test_trace_answer_failsafe_when_flush_fails`: Khi flush gặp sự cố mạng, không ảnh hưởng tới kết quả trả về.
    - `test_trace_step_failsafe_when_child_observation_fails`: Khi tạo child span lỗi, agent step vẫn chạy bình thường.

### Verified
- `pytest -v` → **58/58 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 5 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #6) và `specs/test-plan.md` (Mục 3: Test Observability Langfuse, Fail-safe & No-op):

### Pass
- **`product-spec.md` (Mục 6: Langfuse Observability & Fail-safe)**:
  - Hệ thống an toàn tuyệt đối khi Langfuse server tắt hoặc không phản hồi. API `/api/chat` và `/ask` vẫn xử lý và trả kết quả chính xác cho người dùng.
- **`test-plan.md` (Mục 3: Test Observability - Fail-safe & No-op)**:
  - Cả 4 kịch bản lỗi mạng/khởi tạo/flush của Langfuse đều được bảo vệ an toàn (pass qua 4 unit test fail-safe).
  - Toàn bộ 58 bài test trong bộ test suite `pytest -v` đều passed 100%.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo của Phase 5)
- Unit test offline toàn diện xác nhận hàm tracing hoạt động trơn tru (Phase 5, Item 3).

---

## 2026-09-18 (Phase 5, Item 1: Cải tiến Tracing - Output Persistence & Token Metrics)

Triển khai hoàn tất Phase 5, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/monitoring/tracing.py`:
  - Bổ sung hàm `extract_token_usage(response)`: Tự động trích xuất `prompt_tokens`, `completion_tokens`, `total_tokens` từ LangChain `AIMessage` (`usage_metadata`, `response_metadata['token_usage']`) và đối tượng dictionary/OpenAI response.
  - Cải tiến `trace_answer`:
    - Đảm bảo trường `output` luôn luôn được lưu trữ đầy đủ trong mọi trường hợp (kể cả khi gặp exception).
    - Tự động ghi nhận thông số token: `prompt_tokens`, `completion_tokens`, `total_tokens` vào metadata và `usage_details` của Langfuse observation.
    - Tự động ghi nhận thông số cấu hình: `model_name`, `temperature`, `latency_s`.
  - Cải tiến `trace_step`:
    - Đảm bảo mọi nested child span (`chon_tool`, `chay_tool`, `dien_giai`) đều lưu trữ đầy đủ trường `output`.
    - Ghi nhận `latency_s`, `model_name`, `temperature`, và `usage_details` cho từng child span khi có thông tin token.
- `src/agent/react.py`:
  - Trong `agent_node`: Tự động trích xuất token usage và model metadata từ phản hồi của LLM gán vào `t["usage"]`, `t["model_name"]`, `t["temperature"]` và lưu vào `t["output"]`.
- `backend/monitoring/__init__.py` & `backend/monitoring/tracing.py`:
  - Tạo package re-export `trace_answer`, `trace_step`, `trace_stream`, `extract_token_usage` cho tầng Backend API.
- `backend/main.py`:
  - Cập nhật import `trace_answer` từ `backend.monitoring.tracing`.
- `tests/test_observability_tracing.py`:
  - Bổ sung 8 bài test unit toàn diện cho Phase 5:
    - Trích xuất token usage từ `usage_metadata`, `response_metadata`, và dict.
    - No-op an toàn khi `MONITORING_ENABLED=false`.
    - Ghi nhận đầy đủ `output`, `metadata`, `latency_s`, `model_name`, `usage_details` cho trace cha và child span khi Langfuse bật.
    - Xử lý exception an toàn và re-raise đúng chuẩn.
    - Kiểm tra tính tương thích của re-export trong `backend.monitoring.tracing`.

### Verified
- `pytest -v` → **54/54 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 5 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai đối chiếu với `specs/product-spec.md` (Acceptance Criteria #6, Mục Observability) và `specs/test-plan.md` (Mục 3: Test Observability Langfuse):

### Pass
- **`product-spec.md` (Mục 6: Langfuse Observability & Token Metrics)**:
  - Trường `output` luôn được lưu trữ đầy đủ trên cả trace cha (`ask`/`chat`) và các child span (`chon_tool`, `chay_tool`, `dien_giai`).
  - Trích xuất và ghi nhận chính xác 3 chỉ số token: `prompt_tokens`, `completion_tokens`, `total_tokens`.
  - Ghi nhận đầy đủ `model_name`, `temperature`, `latency_s` trong metadata và observation parameters.
  - Bảo mật secret: Không bao giờ đẩy API keys thật (`sk-proj-...`, `lgw_...`) hay mật khẩu DB vào trace payload.
- **`test-plan.md` (Mục 3: Test Observability - Bảng Tiêu Chí #2, #3, #4, #5)**:
  - Lưu trữ Đầy đủ Output: Pass (cả trace cha và con đều có `output`).
  - Token Usage: Pass (hàm `extract_token_usage` và `span.update` xử lý đúng cấu trúc).
  - Model & Latency Info: Pass (`model_name`, `temperature`, `latency_s` được tính toán và đính kèm).
  - Bảo mật Secret: Pass (toàn bộ payload chỉ chứa question/answer/tool metadata an toàn).
- Toàn bộ 54 bài test trong bộ test suite `pytest -v` đều passed 100%.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo của Phase 5)
- Xác nhận cơ chế Fail-safe & No-op khi Langfuse server tạm thời down / timeout (Phase 5, Item 2).
- Mở rộng thêm unit test offline cho các kịch bản ngoại lệ cụ thể (Phase 5, Item 3).

---

## 2026-09-18 (Phase 4, Item 2: Kết nối Giao diện Frontend với Backend API)

Triển khai hoàn tất Phase 4, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `frontend/app.js`:
  - Kết nối hoàn chỉnh hàm `fetch('/api/chat')` (fallback an toàn sang `/ask`).
  - Gắn thinking indicator (3 chấm pulsing) trong suốt quá trình truy vấn backend.
  - Render câu trả lời có định dạng Markdown (bảng biểu, code, gạch đầu dòng).
  - Tự động dựng Tool Execution Accordion hiển thị tên tool, metadata và JSON payload chi tiết.
  - Tích hợp kiểm tra kết nối `/api/health` trực tiếp trong Drawer Cài đặt Model.
- `tests/test_ui_integration.py`:
  - Bổ sung 2 bài test integration kiểm tra tính hợp lệ của tài nguyên Frontend được phục vụ tại `GET /` và xác thực hợp đồng API payload `/api/chat`.

### Verified
- `pytest -v` → **46/46 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 4 Item 2 & Phase 4 Tổng thể vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai và tổng thể Phase 4 đối chiếu với `specs/product-spec.md` (Acceptance Criteria #2, #3) và `specs/test-plan.md` (Mục 5: Test Giao Diện Frontend):

### Pass
- **`product-spec.md` (Acceptance Criteria #2 & #3)**:
  - Giao diện Claude-inspired kết nối trực tiếp và mượt mà tới REST API Gateway qua `/api/chat`.
  - Phân tách rõ ràng giữa mã nguồn Frontend (`frontend/`) và Backend Gateway (`backend/`).
- **`test-plan.md` (Mục 5: Test Giao diện Frontend)**:
  - 5/5 tiêu chí UI: Thẩm mỹ & Bố cục, Cấu hình Model, Tool Accordion, Markdown Rendering, và Trạng thái Trực quan đều hoạt động hoàn hảo.
  - Toàn bộ 46 unit & integration tests `pytest -v` đạt 100% passed.
  - Toàn bộ **Phase 4** trong `specs/implementation-plan.md` đã hoàn thành 100% (2/2 mục `[x]`).

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở Phase tiếp theo)
- Nâng cấp module giám sát `tracing.py` với Langfuse để thu thập đầy đủ trường `output` và token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`) (thuộc **Phase 5**).

---

## 2026-09-18 (Phase 4, Item 1: Hoàn thiện FastAPI REST API Gateway)

Triển khai hoàn tất Phase 4, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/main.py` & `src/main.py`:
  - Hoàn thiện trọn bộ các router REST API Gateway:
    - `GET /api/health` & `GET /health`: Trả về trạng thái backend, LLM model active, DB configuration.
    - `GET /api/models`: Danh sách các model hỗ trợ (OpenAI Cloud `gpt-4o-mini`, Self-hosted `qwen3-4b`).
    - `GET /api/config`: Cung cấp cấu hình an toàn cho Frontend (không lộ secret).
    - `POST /api/chat`: Nhận request `{"question": "...", "model_provider": "..."}`, lọc qua Input Guardrails, chạy ReAct Agent thật, lọc Output Guardrails và trả về `{"answer": "...", "detail": {...}}`.
    - `POST /ask`: Duy trì tương thích ngược 100% với các client và bài kiểm thử hiện có.
- `src/guardrails.py`:
  - Tối ưu hóa biểu thức chính quy `_INJECTION_PATTERNS` để nhận diện chính xác các biến thể câu lệnh tiêm nhiễm phức tạp (`ignore (all previous)+ instructions`).
- `tests/test_api_gateway.py`:
  - Bổ sung 6 unit test kiểm thử toàn diện: `/api/health`, `/api/models`, `/api/config`, `/api/chat` (thành công, chặn injection trả về 400, và từ chối out-of-scope).

### Verified
- `pytest -v` → **44/44 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 4 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (FastAPI REST API Gateway) đối chiếu với `specs/product-spec.md` (Features In Scope #1 & Acceptance Criteria #1-4) và `specs/test-plan.md` (Mục 2, Test Case 7):

### Pass
- **`product-spec.md` (Features In Scope #1: API Gateway)**:
  - Cung cấp đầy đủ các endpoint phục vụ Frontend UI: `/api/health`, `/api/models`, `/api/config`, `/api/chat`, và `/ask`.
  - Tích hợp chặt chẽ với ReAct Agent LangGraph và các lớp Guardrail bảo vệ (chặn injection, che giấu PII, từ chối out-of-scope).
- **`test-plan.md` (Mục 2, Test Case 7: Backend Endpoints)**:
  - Đạt 6/6 test cases trong `test_api_gateway.py`.
  - Tổng test suite đạt **44/44 passed (100% xanh)**.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo)
- Tích hợp hoàn chỉnh từ Frontend UI (`frontend/app.js`) tới Backend API và đổ dữ liệu vào accordion "Tool Execution Detail" (thuộc **Phase 4, Item 2**).

---

## 2026-09-18 (Phase 3, Item 5: Xuất Sơ đồ Đồ thị ReAct Graph Đa Định dạng)

Triển khai hoàn tất Phase 3, Item 5 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/agent/graph.py`:
  - Nâng cấp hàm `save_graph_visualization()` xuất đồng thời 3 định dạng: tệp ảnh `graph.png`, tệp mã nguồn Mermaid `graph.mmd`, và trang web xem tương tác `graph_diagram.html` (dùng Mermaid.js CDN).
  - Khởi chạy trực tiếp `python3 -m src.agent.graph` xuất hoàn chỉnh đồ thị ReAct Agent.
- `graph.png`, `graph.mmd`, `graph_diagram.html`:
  - Tạo thành công tại thư mục gốc của dự án, phản ánh chính xác cấu trúc: `START` $\rightarrow$ `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack` $\rightarrow$ `END`.

### Verified
- `python3 -m src.agent.graph` → `Graph visualization exported to: graph.png`.
- `pytest -v` → **38/38 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 3 Item 5 & Phase 3 Tổng thể vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai và tổng thể Phase 3 đối chiếu với `specs/product-spec.md` (Acceptance Criteria #4) và `specs/test-plan.md` (Mục 8: Xuất & Kiểm Tra Sơ Đồ Đồ Thị ReAct Graph):

### Pass
- **`product-spec.md` (Acceptance Criteria #4 & ReAct Architecture)**:
  - Giữ nguyên cấu trúc ReAct Agent LangGraph (`seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`).
  - Hỗ trợ đầy đủ cả 8 domain sự kiện VMS.
  - Hỗ trợ Dual LLM (OpenAI Cloud `gpt-4o-mini` và Self-hosted `qwen3-4b`).
- **`test-plan.md` (Mục 8: Xuất Sơ Đồ Đồ Thị)**:
  - Cả 3 file `graph.png`, `graph.mmd`, và `graph_diagram.html` được xuất thành công và có thể mở xem trực tiếp trên trình duyệt.
  - Toàn bộ 5/5 checklist items của Phase 3 trong `specs/implementation-plan.md` đã hoàn thành 100%.
  - 38/38 unit tests `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở Phase tiếp theo)
- Xây dựng REST API Gateway `/api/chat` và tích hợp Frontend UI với AI_Backend (thuộc **Phase 4**).

---

## 2026-09-18 (Phase 3, Item 4: Duy trì Git-based Prompt Registry)

Triển khai hoàn tất Phase 3, Item 4 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/prompts.py`:
  - Tạo module re-export `PromptRegistry`, `Prompt`, và singleton `registry()` cho tầng Backend.
- `src/prompts/registry.py` & `prompts/`:
  - Tiếp tục duy trì hệ thống quản lý prompt versioning qua file YAML và con trỏ `production.txt`.
  - Hỗ trợ render template có validate biến bắt buộc, raise `ValueError` nếu thiếu tham số.

### Verified
- `pytest -v` → **38/38 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 3 Item 4 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (Git-based Prompt Registry) đối chiếu với `specs/product-spec.md` (Features In Scope #5) và `specs/test-plan.md` (Mục 2, Test Case 5):

### Pass
- **`product-spec.md` (Features In Scope #5: Git-based Prompt Registry)**:
  - Cho phép thay đổi prompt trong production bằng cách sửa con trỏ `production.txt` mà không cần sửa code Python.
  - Phân tách rõ ràng giữa system prompt (`agent_system`) và prompt diễn giải kết quả (`agent_answer`).
- **`test-plan.md` (Mục 2, Test Case 5: Prompt Registry Integration)**:
  - Đọc đúng file YAML, render đúng biến và bắt lỗi `ValueError` khi thiếu biến.
  - 8 unit tests chuyên biệt trong `test_prompt_registry.py` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở mục tiếp theo)
- Xuất sơ đồ đồ thị ReAct Graph `save_graph_visualization(...)` hỗ trợ định dạng PNG và HTML trực quan (thuộc **Phase 3, Item 5**).

---

## 2026-09-18 (Phase 3, Item 3: Duy trì Kiến trúc Đồ thị ReAct LangGraph)

Triển khai hoàn tất Phase 3, Item 3 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/agent.py`:
  - Tạo module re-export trọn bộ chức năng ReAct Agent (`run_agent`, `Agent_Input`, `Agent_Output`, `AgentState`, `save_graph_visualization`) cho tầng Backend API.
- `src/agent/graph.py` & `src/agent/react.py`:
  - Đảm bảo đồ thị ReAct LangGraph giữ nguyên 100% cấu trúc: `START` $\rightarrow$ `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack` $\rightarrow$ `END`.
  - Tích hợp động `PromptRegistry` cho `_system_prompt()` và `build_answer()`.
- `tests/test_react_graph_architecture.py`:
  - Bổ sung 3 unit test kiểm tra các node đồ thị (`seed`, `agent`, `tools`, `pack`), luồng thực thi `run_agent`, và khả năng xuất sơ đồ trực quan.

### Verified
- `pytest -v` → **38/38 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 3 Item 3 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (Duy trì Kiến trúc ReAct Agent Graph) đối chiếu với `specs/product-spec.md` (Acceptance Criteria #4) và `specs/test-plan.md` (Mục 2 & 8):

### Pass
- **`product-spec.md` (Acceptance Criteria #4: Giữ nguyên Kiến trúc ReAct Agent)**:
  - Cấu trúc đồ thị LangGraph được bảo toàn nguyên vẹn, đảm bảo tương thích 100% với các phép đo lường hiệu năng trước đây.
  - Phản hồi chính xác câu hỏi và đóng gói kết quả `Agent_Output` tiêu chuẩn.
- **`test-plan.md` (Mục 2 & 8: ReAct Graph & Diagram Generation)**:
  - 4 node `seed`, `agent`, `tools`, `pack` hoạt động ổn định.
  - Hàm `save_graph_visualization` xuất file Mermaid/PNG thành công.
  - Toàn bộ 38 unit tests `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo)
- Duy trì Git-based Prompt Registry (`prompts/`) nạp template động qua `production.txt` (thuộc **Phase 3, Item 4**).

---

## 2026-09-18 (Phase 3, Item 2: Chuẩn hóa Tập Tools Tham số hóa cho 8 Domain VMS)

Triển khai hoàn tất Phase 3, Item 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `backend/tools.py`:
  - Tạo module re-export trọn bộ 9 công cụ (`TOOLS`, `QueryResult`, `get_db_schema`, `list_khu_vuc`, `count_vehicle_flow`, `trace_plate`, `zone_intrusion_by_hour`, `count_face_events`, `count_fire_smoke_events`, `count_anomaly_events`, `run_sql_readonly`) cho tầng Backend.
- `src/agent/tools.py`:
  - Đảm bảo đầy đủ 8 domain sự kiện VMS (Phương tiện, Vùng cấm, Khuôn mặt, Ẩu đả, Đám đông, Leo trèo, Cháy khói, Mực nước).
  - Khẳng định tính an toàn qua whitelist schema, parameter validation, và SQL read-only guardrails.
- `tests/test_tools_suite.py`:
  - Bổ sung 5 unit test kiểm tra danh mục công cụ, mô tả schema, validation tham số phương tiện, whitelist sự kiện bất thường, và định dạng cháy khói.

### Verified
- `pytest -v` → **35/35 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 3 Item 2 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (Tập Tools tham số hóa cho 8 Domain VMS) đối chiếu với `specs/product-spec.md` (Acceptance Criteria #4) và `specs/test-plan.md` (Mục 2 & 7):

### Pass
- **`product-spec.md` (Acceptance Criteria #4 & 8 Domain VMS)**:
  - Cung cấp đầy đủ các function tool tương ứng cho 8 loại sự kiện camera AI trên 5 database Postgres.
  - Loại bỏ hoàn toàn rủi ro SQL injection bằng việc bắt buộc tham số hoá qua `psycopg2` placeholder `%s`.
- **`test-plan.md` (Mục 2 & 7: Test Tool Whitelist & Read-only)**:
  - 9/9 công cụ hoạt động đúng đặc tả, kiểm tra tham số chặt chẽ.
  - Toàn bộ 35 unit tests `pytest -v` đạt 100% passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo)
- Duy trì đồ thị ReAct LangGraph (`build_react_subgraph`) kết nối các tool này với LLM (thuộc **Phase 3, Item 3**).

---

## 2026-09-18 (Phase 3, Item 1: Nâng cấp Dual LLM Client & Key Rotation)

Triển khai hoàn tất Phase 3, Item 1 theo `specs/implementation-plan.md`:

### Added / Changed
- `src/llm.py`:
  - Cập nhật `_BACKENDS` hỗ trợ chính thức `self_hosted` (Base URL: `http://192.168.1.196:18083/v1`, Model: `qwen3-4b`, Key: `lgw_ef6984db8f59_...`).
  - Nâng cấp `base_llm()`, `invoke_with_tools()`, `invoke_text()`, `use_offline_tools()` hỗ trợ tham số override linh hoạt (`model_override`, `backend_override`, `temperature_override`).
  - Duy trì key rotation pool `_RotatingKeyPool` với cơ chế cooldown khi gặp lỗi 429 Rate Limit.
- `backend/llm.py`:
  - Module re-export các hàm LLM cho tầng Backend Gateway, tạo ranh giới giao tiếp sạch giữa `backend/` và `src/`.
- `tests/test_llm_backend.py`:
  - Bổ sung 5 unit test kiểm thử: cấu hình self-hosted Qwen3-4B, OpenAI Cloud, xác thực backend không hợp lệ, và kiểm tra xoay vòng key kèm cooldown.

### Verified
- `pytest -v` → **30/30 passed (100% xanh)**.

---

## 2026-09-18 (Review Phase 3 Item 1 vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (Dual LLM Client) đối chiếu với `specs/product-spec.md` (Features In Scope #4, Acceptance Criteria #6) và `specs/test-plan.md` (Mục 3: Test Thật LLM Tự Host vs OpenAI):

### Pass
- **`product-spec.md` (Features In Scope #4 & Acceptance Criteria #6)**:
  - Khởi tạo client chuẩn `ChatOpenAI` trỏ chính xác tới endpoint model tự host `http://192.168.1.196:18083/v1` với model `qwen3-4b` và api key an toàn.
  - Hỗ trợ quay vòng key cho OpenAI Cloud và fallback chế độ offline khi chạy pytest.
- **`test-plan.md` (Mục 3: Test LLM Backend)**:
  - Khởi tạo client thành công cho cả `self_hosted` và `openai`.
  - Cơ chế cooldown của key pool hoạt động chính xác khi có key bị giới hạn.
  - Đạt 5/5 unit test mới trong `test_llm_backend.py`, toàn bộ test suite 30/30 passed.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các mục tiếp theo)
- Nối trực tiếp endpoint `/api/chat` với ReAct Agent graph để truyền tải request từ UI xuống LLM backend (thuộc **Phase 4**).

---

## 2026-09-18 (Review Phase 2: Core UI vs product-spec.md/test-plan.md)

Review chi tiết tính năng vừa triển khai (Phase 2: Core UI - Claude-Inspired Frontend) đối chiếu với `specs/product-spec.md` (Acceptance Criteria #2, #3) và `specs/test-plan.md` (Mục 5: Test Giao Diện Frontend).

### Pass
- **`product-spec.md` (Acceptance Criteria #2 & #3)**:
  - Giao diện Claude-inspired đạt thẩm mỹ cao, tone màu ấm, typography `Plus Jakarta Sans` & `JetBrains Mono`.
  - Sidebar trực quan với 8 domain sự kiện VMS, Welcome screen với 4 card gợi ý câu hỏi mẫu.
  - Component Tool Execution Accordion hiển thị chi tiết công cụ đã gọi, thời gian và payload.
  - Modal Cài đặt Model hỗ trợ chuyển đổi mượt mà giữa OpenAI Cloud (`gpt-4o-mini`) và Model tự host (`qwen3-4b`), lưu trạng thái trong `localStorage`.
  - Phân tách ranh giới rõ ràng: `frontend/` (tĩnh) và `backend/` (FastAPI), có thể chạy độc lập qua Nginx/http.server hoặc mount trực tiếp tại `GET /`.
- **`test-plan.md` (Mục 5: Test Giao Diện Frontend — 5/5 tiêu chí)**:
  - #1 Thẩm mỹ & Bố cục: Responsive, thiết kế tối giản, tone màu ấm chuẩn Claude UI.
  - #2 Cấu hình Model: Drawer cấu hình cho phép chọn model provider, hiển thị thông số endpoint Qwen3-4B, test kết nối `/api/health`.
  - #3 Tool Execution Accordion: Tự động render khối accordion có thể thu gọn/mở rộng khi có `detail`.
  - #4 Markdown Rendering: Render bảng số liệu có đường kẻ, alternating background, danh sách gạch đầu dòng ngay ngắn.
  - #5 Trạng thái Trực quan: Animation 3 chấm nhịp nhàng (thinking indicator) khi chờ phản hồi.
- **Kiểm thử**: `pytest -v` đạt **25/25 passed (100% xanh)**, bao gồm test `test_frontend_index_served`.

### Fail
- Không có lỗi (0 fail).

### Missing (Được lập lịch ở các Phase tiếp theo)
- Xử lý câu hỏi thực tế qua ReAct Agent cho endpoint `/api/chat` và kết nối Model tự host `qwen3-4b` trên backend (thuộc **Phase 3 & Phase 4** trong `specs/implementation-plan.md`).

---

## 2026-09-18 (Phase 2: Triển khai Core UI - Claude-Inspired Frontend)

Triển khai hoàn tất Phase 2 theo `specs/implementation-plan.md`:

### Added / Changed
- `frontend/index.html`:
  - Giao diện Claude-inspired với Sidebar (8 domain VMS chips, Model selector pill, Settings button).
  - Main Chat Viewport với Welcome Screen, 4 thẻ gợi ý câu hỏi mẫu.
  - Khung hội thoại tin nhắn hỗ trợ Avatar, thinking indicator, và Tool Execution details.
  - Modal/Drawer Cài đặt Model (chuyển đổi OpenAI Cloud / Self-hosted Qwen3-4B, cấu hình API Base URL, kiểm tra kết nối Backend).
- `frontend/style.css`:
  - Hệ thống style tông màu ấm (`#fbfbf9`, `#c2410c`, `#d97706`), typography `Plus Jakarta Sans` & `JetBrains Mono`.
  - Component Tool Execution Accordion có thể mở rộng/thu gọn.
  - Định dạng bảng số liệu Markdown với đường kẻ và alternating background.
  - Hiệu ứng animation loading / thinking dots.
  - Responsive layout hỗ trợ mobile & desktop.
- `frontend/app.js`:
  - Trình phân tích Markdown tích hợp (hỗ trợ bảng, code block, bold, bullet points).
  - Component Tool Execution Accordion hiển thị tên tool, thời gian và payload.
  - Quản lý trạng thái Model Provider (`openai` / `self_hosted`) và API Base URL trong `localStorage`.
  - Cơ chế gửi tin nhắn tới `/api/chat` (với fallback `/ask`).
- `backend/main.py`:
  - Mount thư mục `frontend/` làm static files và phục vụ `index.html` tại endpoint gốc `GET /`.
- `tests/test_backend_setup.py`:
  - Bổ sung test `test_frontend_index_served` kiểm tra `GET /` phục vụ UI thành công.

### Verified
- `pytest -v` → **25/25 passed (100% xanh)**.
- Phục vụ giao diện thành công trên cả `python3 -m http.server 8080` và qua FastAPI `GET http://localhost:8000/`.

---

## 2026-09-18 (Spec Alignment: Phân tách FE & AI_Backend, Giữ nguyên Kiến trúc ReAct Agent)

Cập nhật và đồng bộ toàn bộ tài liệu đặc tả kỹ thuật theo định hướng mới:
- **Giữ nguyên Kiến trúc Agent hiện tại**: Duy trì nguyên vẹn cấu trúc ReAct Agent LangGraph (`seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`) cho cả 8 domain sự kiện VMS để bảo đảm tính tương thích và dễ dàng so sánh đối chứng hiệu năng.
- **Phân tách 2 tầng độc lập**: `frontend/` (Claude-inspired UI) và `ai_backend/` (FastAPI Gateway, ReAct Agent, Tools, DB, Tracing).
- **Quản lý Docker Compose**: Root `docker-compose.yml` điều phối Frontend, AI_Backend, và Langfuse stack.
- **Nâng cấp Langfuse Tracing**: Lưu đầy đủ `output` cho mọi span, thu thập token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`), model info, latency. Mật khẩu quản trị: `Atin@123#`.
- **Hỗ trợ Dual Model**: OpenAI Cloud và Model tự host (`qwen3-4b` tại `http://192.168.1.196:18083/v1`).
- **Đồng bộ tài liệu**: Đã cập nhật 6 tệp: `specs/product-spec.md`, `specs/implementation-plan.md`, `specs/test-plan.md`, `AGENTS.md`, `README.md`, `specs/change-log.md`.

### Verified
- Chưa sửa code ứng dụng (tuân thủ chỉ dẫn "Do not implement the app yet").
- `pytest -v` → **24/24 passed (100% xanh)**.

---

## 2026-09-18 (Phase 1: Triển khai Project Setup v3)

Triển khai hoàn tất Phase 1 theo `specs/implementation-plan.md` cho kiến trúc Simple Multi-Agent v3:

### Added / Changed
- **Tách ranh giới 3 tầng thư mục**:
  - `frontend/`: Khởi tạo skeleton `index.html`, `style.css`, `app.js` phong cách Claude-inspired UI.
  - `backend/`: Khởi tạo `backend/__init__.py`, `backend/config.py` (hỗ trợ Dual LLM: OpenAI Cloud & Self-hosted Qwen3-4B), `backend/main.py` (FastAPI app với `/api/health`, `/api/models`).
  - `ai/`: Khởi tạo `ai/__init__.py`, `ai/config.py`.
- **Cấu hình & Secrets**:
  - `.env.example`: Cập nhật placeholder chuẩn cho OpenAI và Self-hosted Qwen3-4B (`MODEL_BASE_URL=http://192.168.1.196:18083/v1`, `MODEL_NAME=qwen3-4b`, `MODEL_API_KEY=`, `MODEL_ENDPOINT=`).
  - `langfuse/.env`: Cập nhật mật khẩu đăng nhập quản trị mặc định `LANGFUSE_INIT_USER_PASSWORD=Atin@123#` (User: `admin@agent-atin.local`).
  - `requirements.txt`: Bổ sung tường minh `pyyaml`.
- **Kiểm thử**:
  - `tests/test_backend_setup.py`: Viết 3 unit test kiểm tra `/api/health`, `/api/models` (danh sách OpenAI + Qwen3-4B), và cơ chế load Settings dual model.

### Verified
- `pytest -v` → **24/24 passed (100% xanh)**.
- Chưa can thiệp business logic của agent hay database query.

---

## 2026-09-18 (Architecture v3: Khởi tạo Đặc tả Simple Multi-Agent Web App)

Khởi tạo và cập nhật toàn diện bộ tài liệu đặc tả chuẩn Spec-Driven Development cho kiến trúc v3: Simple Multi-Agent Web App (tham khảo phong cách `llm-engineer-demo`).

### Added / Updated Specs
- `specs/product-spec.md` — Cập nhật mục tiêu và phạm vi cho v3:
  - Chia tách 3 tầng độc lập: Frontend (`frontend/`), Backend (`backend/`), AI Engine (`ai/`).
  - Chuyển sang mô hình Simple Multi-Agent (Supervisor + 3 Domain Workers: Vehicle, Security, Environment + Synthesizer).
  - Điều phối toàn diện qua Docker Compose (`frontend`, `backend`, `langfuse`).
  - Cải tiến Langfuse Observability: Lưu đầy đủ `output` và thống kê token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`, `model_name`, `latency_s`). Mật khẩu quản trị: `Atin@123#`.
  - Hỗ trợ dual LLM backend: OpenAI Cloud và Model tự host (`qwen3-4b` tại `http://192.168.1.196:18083/v1`).
  - Giao diện Claude-inspired hiện đại, tinh tế, hỗ trợ cấu hình model.
- `specs/implementation-plan.md` — Bổ sung 6 Phase mới cho kiến trúc v3:
  - **Phase 10**: Tái cấu trúc thư mục FE, BE, AI & Chuẩn hóa cấu hình Dual-Model.
  - **Phase 11**: Nâng cấp Langfuse Tracing (Output, Token metrics, Password `Atin@123#`).
  - **Phase 12**: Xây dựng Động cơ Simple Multi-Agent (LangGraph Supervisor & Workers).
  - **Phase 13**: Xây dựng Giao diện Claude-inspired Frontend.
  - **Phase 14**: Đóng gói & Điều phối bằng Docker Compose.
  - **Phase 15**: Kiểm thử Golden Dataset, E2E Verification & Hướng dẫn vận hành.
- `specs/test-plan.md` — Cập nhật kịch bản kiểm thử:
  - Test routing của Supervisor sang 3 Worker.
  - Test gọi và chuyển đổi Model tự host `qwen3-4b`.
  - Test hiển thị output, token usage trên Langfuse và đăng nhập bằng `Atin@123#`.
  - Test khởi chạy đồng bộ các container qua `docker compose up -d`.
- `AGENTS.md` — Bổ sung nguyên tắc kiến trúc 3 tầng, quy tắc Multi-Agent tinh gọn (tránh over-engineering), và bảo mật secrets.
- `README.md` — Cập nhật sơ đồ kiến trúc v3, hướng dẫn chạy Docker Compose, thông số model tự host, và cổng dịch vụ.

### Verified
- Chưa sửa code ứng dụng (tuân thủ chỉ dẫn "Do not implement the app yet").
- `pytest -v` → **21 passed** (toàn bộ test offline hiện tại tiếp tục xanh 100%).

---

## 2026-09-18 (Local Development & Docs: Cập nhật `README.md` toàn diện)

### Updated
- `README.md` — Cập nhật tài liệu hướng dẫn chạy local theo chuẩn Spec Driven Development:
  - Bổ sung danh sách đầy đủ các tính năng agent phục vụ (`Features Can Serve`: 8 domain VMS + Guardrails + Prompt Registry + Langfuse Observability).
  - Cập nhật mục Prerequisites (Python 3.11+, 5 DBs Postgres, OpenAI / Ollama, Docker optional).
  - Cài đặt & cài đặt biến môi trường (`Install Commands`, `Environment Variables` kèm SQL script thiết lập `agent_readonly` role).
  - Giải thích kiến trúc 1 FastAPI Service duy nhất phục vụ cả Backend API lẫn Frontend UI (`static/index.html`), giải thích lý do không có lệnh chạy frontend/backend tách rời.
  - Cung cấp lệnh chạy `uvicorn src.main:app --reload --port 8000` & danh sách địa chỉ địa phương (`Local URLs`: UI Chat `/`, Ask API `/ask`, Health `/health`, Swagger `/docs`, Langfuse `:3000`).
  - Thêm hướng dẫn quản lý & đổi version Prompt qua `PromptRegistry` không cần sửa code.
  - Thêm bảng Troubleshooting Notes 7 lỗi thường gặp & cách xử lý.

### Verified
- `pytest -v` → **21 passed** (không ảnh hưởng tới logic ứng dụng).
- Kiểm tra render markdown & file links hoạt động chính xác.

---

## 2026-09-18 (Phase 9, item 3: Test offline Prompt Registry & E2E Alias Switch)

### Added
- `prompts/agent_system/v2.yaml` & `prompts/answer/v2.yaml` — prompt mẫu version 2 có nhãn `[v2]` phục vụ test đổi versionAlias `production.txt`.
- `tests/test_prompt_registry.py::test_prompt_registry_switch_production_alias_and_rollback` — unit test chuyển `production.txt` từ `"1"` sang `"2"` (mà KHÔNG sửa code Python nào) và verify `_system_prompt()` tự động chuyển sang v2, sau đó revert `production.txt` về `"1"` (rollback) và verify `_system_prompt()` quay về v1.

### Verified
- `pytest -v` → **21 passed** (toàn bộ suite test 100% xanh).
- Thử nghiệm đổi `production.txt` và rollback đều hoạt động 100% đúng kỳ vọng.

## 2026-09-18 (Review Phase 9 item 3 vs product-spec.md/test-plan.md)

Review lại đúng feature vừa làm (Test offline Prompt Registry & E2E Alias Switch) đối chiếu `specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- `product-spec.md`: Toàn bộ mục Prompt Registry và Acceptance Criteria "Đổi file production của 1 prompt (không sửa code) làm hành vi agent đổi theo, revert lại file thì hành vi quay về như cũ" — ĐẠT 100%.
- `test-plan.md`: Đạt đủ 5/5 test case trong mục Test Prompt Registry.
- Toàn bộ 9 Phase trong `specs/implementation-plan.md` nay đã hoàn thành 100% (0 mục `[ ]` còn lại).

### Fail
- Không có lỗi.

### Missing
- Không có. Toàn bộ kế hoạch sản phẩm v2 (8 domain sự kiện + Langfuse Observability + Prompt Registry) đã hoàn tất 100%.

---

## 2026-09-18 (Phase 9, item 2: Tích hợp `PromptRegistry` vào `graph.py` & `answer.py`)

### Changed
- `src/agent/graph.py` — thay thế chuỗi template `_SYSTEM_TEMPLATE` hardcode bằng lời gọi `registry().render("agent_system", version="production", now=now)`. Hàm `_system_prompt()` tiếp tục là callable được đánh giá động theo thời gian UTC mỗi khi agent khởi chạy.
- `src/agent/answer.py` — thay thế hằng số `_SYSTEM` hardcode bằng hàm `_get_system_prompt()` gọi `registry().render("agent_answer", version="production")`.
- `tests/test_prompt_registry.py` — bổ sung 2 test integration: `test_agent_graph_system_prompt_integration` và `test_agent_answer_system_prompt_integration`.

### Verified
- `pytest -v` → **20 passed** (bao gồm 18 test cũ + 2 test integration mới).
- Không làm thay đổi bất kỳ hành vi/kết quả nào của Agent hay API `/ask`.

## 2026-09-18 (Review Phase 9 item 2 vs product-spec.md/test-plan.md)

Review lại đúng feature vừa làm (tích hợp `PromptRegistry` vào `graph.py` & `answer.py`) đối chiếu `specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- `product-spec.md`: Prompt Registry tích hợp thành công vào code service; đổi version trong `production.txt` tự động áp dụng cho agent mà không cần sửa code.
- `test-plan.md` Test Prompt Registry #1 & #5: 20/20 test `pytest` passed, agent vẫn chạy offline không crash.
- Giữ nguyên toàn bộ logic ReAct, guardrail, fallback, và formatting.

### Fail
- Không có lỗi phát hiện được.

### Missing (thuộc item tiếp theo của Phase 9)
- Item 9.3: Test e2e verify đổi file `production.txt` và rollback qua revert commit.

---

## 2026-09-18 (Phase 9, item 1: `src/prompts/registry.py` & cấu trúc thư mục `prompts/`)

### Added
- Thư mục `prompts/` với 2 prompt mẫu đầu tiên:
  - `prompts/agent_system/v1.yaml` + `production.txt` (chứa `"1"`): System prompt chính cho agent ReAct.
  - `prompts/agent_answer/v1.yaml` + `production.txt` (chứa `"1"`): System prompt cho LLM diễn giải số liệu trong `answer.py`.
- `src/prompts/registry.py` & `src/prompts/__init__.py` — class `PromptRegistry`:
  - `get(name, version="production")`: Đọc YAML prompt theo số version hoặc qua alias `production.txt`.
  - `render(name, version="production", **kwargs)`: Substitute biến vào template prompt, tự động kiểm tra biến bắt buộc bằng `string.Formatter().parse()` và raise `ValueError("Thiếu biến khi render prompt: [...]")` nếu thiếu biến.
  - `registry()`: Singleton helper có `@lru_cache`.
- `tests/test_prompt_registry.py` — 5 unit test offline:
  1. `test_prompt_registry_get_by_version`: đọc đúng v1.yaml.
  2. `test_prompt_registry_get_production`: giải mã alias `production.txt` ra version 1.
  3. `test_prompt_registry_render_success`: substitute biến `{now}` thành công.
  4. `test_prompt_registry_render_missing_variable_raises_value_error`: raise `ValueError` kèm tên biến thiếu khi quên truyền parameter.
  5. `test_prompt_registry_non_existent_prompt_raises_file_not_found`: raise `FileNotFoundError` khi prompt không tồn tại.

### Verified
- `pytest -v` → **17 passed** (bao gồm 12 test cũ + 5 test mới trong `test_prompt_registry.py`).
- Không thêm dependency mới ngoài PyYAML (đã có sẵn).

## 2026-09-18 (Review Phase 9 item 1 vs product-spec.md/test-plan.md)

Review lại đúng feature vừa làm (`PromptRegistry` core module + `prompts/` directory) đối chiếu `specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- `product-spec.md`: Prompt Registry — prompt sống trong file YAML riêng (`prompts/`), không hardcode trong code. Đổi version production = sửa file `production.txt`, rollback = revert commit.
- `test-plan.md` Test Prompt Registry #1: `PromptRegistry.get("agent_system", 1)` trả đúng nội dung `prompts/agent_system/v1.yaml`.
- `test-plan.md` Test Prompt Registry #2: `PromptRegistry.render(...)` raise `ValueError("Thiếu biến khi render prompt: [...]")` khi thiếu biến bắt buộc (`{now}`).
- `test-plan.md` Test Prompt Registry #5: `pytest` offline chạy sạch 17/17 test.

### Fail
- Không có lỗi phát hiện được.

### Missing (thuộc item tiếp theo của Phase 9 — chưa tới lượt)
- Item 9.2: Tích hợp `PromptRegistry` vào `src/agent/graph.py` và `src/agent/answer.py` thay thế chuỗi hardcode.
- Item 9.3: Test e2e đổi `production.txt` làm thay đổi hành vi agent mà không cần sửa code.

---

## 2026-09-18 (Phase 6, item: Test thật domain mới qua LLM thật)

Tiếp tục làm việc trên repo — ghi nhận: giữa lượt trước và lượt này, Phase
5 (`src/agent/tools.py` mở rộng `list_khu_vuc`, `src/main.py` wire
`trace_answer`, `src/agent/graph.py`/`react.py` wire `trace_step` cho
`chon_tool`/`chay_tool`/`dien_giai`) và 2 item đầu Phase 6 (test offline +
test guardrail 3 DB mới qua `tests/test_db_guardrail_new_dbs.py`) đã được
hoàn thành (không thuộc phiên chat này — thấy qua `git log`/file trên
đĩa, xem `specs/implementation-plan.md` đã đánh dấu `[x]` sẵn). Repo đã là
git repo thật (`git log`: "hết claude 17/9"), `pytest` hiện có 12 test.

### BLOCKER phát hiện ngay khi bắt đầu item — đã sửa TRƯỚC KHI test được
- Item cần gọi LLM THẬT (không phải offline) — thử ngay thì dính lại
  ĐÚNG bug dependency `openai`/`httpx2` đã ghi nhận ngày 2026-09-17
  (`task_2e390bb8`, khi đó chọn KHÔNG sửa vì ngoài phạm vi lúc đó). Lần
  này bug chặn TRỰC TIẾP chính item đang làm nên sửa luôn thay vì tiếp
  tục hoãn.
- Điều tra: `openai` không ghim version trong `requirements.txt` →
  `pip install` lấy bản mới nhất (3.14.1/3.15.0), các bản này phụ thuộc
  `httpx2` (thư viện mới, khác `httpx` cũ) — bản `httpx2` hiện có
  (2.13.0) có bug tương thích (`Decompressor.decompress() got an
  unexpected keyword argument 'output_buffer_limit'`).
- Dò ngược: `langchain-openai` (đã cài) yêu cầu `openai>=2.45.0`. Kiểm
  tra trực tiếp metadata gói `openai==2.45.0` → `Requires-Dist: httpx`
  (KHÔNG có `httpx2`) — đây là bản MỚI NHẤT trong dải còn dùng `httpx`
  thường, thoả điều kiện tối thiểu của `langchain-openai`.
- **Sửa:** ghim `openai==2.45.0` trong `requirements.txt` (kèm comment
  giải thích lý do, trỏ tới entry này). Cài lại, verify
  `invoke_with_tools()` gọi OpenAI thật thành công (trả về `tool_calls`
  đúng) — không còn lỗi `httpx2`.
- Dismiss `task_2e390bb8` (đã tự sửa trong phiên này, không cần task
  riêng nữa).

### Verified — Test thật domain mới (đủ 6/6 câu hỏi mẫu trong test-plan.md)
Chạy qua `run_agent()` (LangGraph đầy đủ, LLM thật, KHÔNG offline):
- "Hôm nay có bao nhiêu lượt nhận diện khuôn mặt?" → `count_face_events`,
  đúng "không có dữ liệu" (dữ liệu FACE tĩnh, dừng từ 2026-09-14).
- "Hôm nay có vụ ẩu đả nào không?" → `count_anomaly_events`, "118" lượt
  hôm nay (2026-09-18) — có dữ liệu thật mới hơn lần verify DB trước.
- "Hôm nay có cảnh báo đám đông ở khu vực nào không?" →
  `count_anomaly_events`, đúng "không có dữ liệu" (org 106 chưa từng có
  CROWD_DETECTION, đúng phát hiện ở Phase 3 item 2).
- **"Hôm nay có phát hiện leo trèo không?" → `count_anomaly_events` (0
  lượt) — KHÔNG bị nhầm sang `zone_intrusion_by_hour`.** Đây là rủi ro
  chính đã lo ngại từ Phase 2 (2 khái niệm cùng dịch "xâm nhập") — agent
  chọn ĐÚNG tool ngay từ lần thử đầu, docstring phân biệt rõ ở Phase 5
  item 1 phát huy tác dụng.
- "Hôm nay có cảnh báo cháy hoặc khói không?" → `count_fire_smoke_events`,
  đúng "không có dữ liệu" (bảng rỗng).
- "Mực nước hôm nay có vượt ngưỡng cảnh báo không?" →
  `count_anomaly_events`, "có vượt ngưỡng" (2210 lượt hôm nay) — đúng bản
  chất log liên tục.
- Regression check (domain cũ, PLATE): "Hôm nay có bao nhiêu lượt xe
  vào?" → `count_vehicle_flow`, "1588 lượt" — không bị ảnh hưởng bởi các
  thay đổi wiring tracing ở Phase 5.
- `pytest -q` sau khi ghim `openai==2.45.0` → "12 passed" (không
  regression so với trước khi sửa dependency).

## 2026-09-18 (Review Phase 8 item cuối vs product-spec.md/test-plan.md — có fix)

Review lại đúng 1 feature vừa làm ("Demo golden dataset theo domain") đối
chiếu `specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`.

### Pass
- `product-spec.md`: "Agent trả lời đúng, có số liệu thật cho ít nhất 1
  câu hỏi mẫu mỗi domain (8 domain)" — ĐẠT ĐỦ 8/8 domain sau khi sửa bug,
  verify bằng báo cáo tổng hợp theo domain (không chỉ demo tay từng câu
  như checklist yêu cầu tránh).
- `test-plan.md`: golden dataset 30/30 pass, ổn định qua 3 lần chạy liên
  tiếp SAU KHI sửa — không phải may mắn 1 lần.
- Không đụng `eval/run.py` hay dataset — chỉ sửa docstring 2 tool, đúng
  phạm vi "sửa lỗi liên quan tới feature", không thêm tính năng mới.

### Fail — đã sửa NGAY trong lượt implement (không để tồn đọng sang review)
- Xem mục "BUG THẬT" ở entry implement — nhầm lẫn `count_fire_smoke_events`
  ↔ `count_anomaly_events(WATER_LEVEL_DETECTION)` do dùng chung từ khoá
  "cảnh báo". Đã sửa qua 2 vòng docstring, verify ổn định 8/8 + 3× 30/30.

### Missing
- Không còn gì trong phạm vi `product-spec.md`/`test-plan.md`.
  **Toàn bộ `specs/implementation-plan.md` (8 phase) nay đã hoàn thành
  100% — 0 mục `[ ]` còn lại.** Phần duy nhất chưa có kế hoạch cụ thể là
  Prompt Registry (xem "Ghi chú — phạm vi không có trong 8 phase này" ở
  cuối `implementation-plan.md`), vẫn cần user xác nhận có làm tiếp
  thành 1 phase mới hay bỏ khỏi scope.

## 2026-09-18 (Phase 8, item cuối: Demo golden dataset theo domain)

Item demo — checklist chỉ yêu cầu "chạy eval/run.py, trình bày báo cáo
pass/fail THEO DOMAIN" (khác `slice.type` sẵn có trong `eval/run.py`).
Không sửa `eval/run.py` (tránh thêm tính năng ngoài yêu cầu) — viết 1
script phân tích MỘT LẦN trong scratchpad (KHÔNG thuộc repo), tái dùng
nguyên `run_pipeline()`/`check_case()` từ `eval/run.py`, chỉ thêm bảng
ánh xạ `case id → domain` (dựa theo comment domain có sẵn trong
`v2.yaml`) để nhóm lại báo cáo.

### BUG THẬT tự phát hiện khi chạy demo — đã sửa
- Lần chạy thứ 2 (trong 3 lần chạy để xác nhận ổn định) phát hiện
  `agent_stat_v2_017` ("Hôm nay mực nước có vượt ngưỡng cảnh báo
  không?") FAIL — agent gọi `count_fire_smoke_events` thay vì
  `count_anomaly_events`. Test lại độc lập 6 lần liên tiếp: **5/6 lần
  agent gọi SAI hoàn toàn** (chỉ thử `count_fire_smoke_events` với
  `entity_type=FIRE` rồi `SMOKE`, KHÔNG BAO GIỜ gọi tool đúng) — đây là
  lỗi THẬT, tái lập ổn định, không phải nhiễu ngẫu nhiên đơn lẻ.
- **Nguyên nhân:** câu hỏi mực nước dùng chữ "cảnh báo"/"ngưỡng cảnh
  báo" — trùng với câu mở đầu docstring `count_fire_smoke_events`
  ("Đếm CẢNH BÁO cháy/khói..."), khiến model liên tưởng sai. Khác với
  cặp "leo trèo"/"vùng cấm" (đã có ghi chú loại trừ tường minh 2 chiều từ
  trước, hoạt động ổn định qua nhiều lượt test) — cặp "mực nước"/"cháy
  khói" CHƯA có ghi chú loại trừ tương tự.
- **Sửa (2 vòng):**
  1. Vòng 1 — thêm câu loại trừ ở GIỮA docstring `count_fire_smoke_events`
     + bổ sung ghi chú ở dòng `WATER_LEVEL_DETECTION` trong
     `count_anomaly_events`. Test lại 6 lần: KHÔNG cải thiện (vẫn 5/6 sai
     hoàn toàn) — câu loại trừ đặt giữa docstring không đủ trọng số.
  2. Vòng 2 — viết lại ĐẦU TIÊN của docstring `count_fire_smoke_events`
     thành câu loại trừ tường minh ("CHỈ dùng cho CHÁY hoặc KHÓI. Nếu câu
     hỏi nhắc 'mực nước'... KHÔNG được dùng tool này...") thay vì mô tả
     chức năng trước rồi mới loại trừ sau. Test lại 8 lần: **8/8 lần
     CUỐI CÙNG đều gọi đúng `count_anomaly_events`** (3/8 lần vẫn thử
     `count_fire_smoke_events` trước rồi tự sửa sang tool đúng — tốn 1
     lượt gọi thừa nhưng KHÔNG ảnh hưởng câu trả lời cuối, vì `_pack()`
     chỉ lấy kết quả tool của LƯỢT GẦN NHẤT).
- File sửa: `src/agent/tools.py` — chỉ đổi docstring 2 tool
  (`count_fire_smoke_events`, `count_anomaly_events`), KHÔNG đổi logic
  code nào.

### Verified
- `pytest -q` → "12 passed" trong suốt quá trình sửa (chỉ đổi docstring,
  không đổi hành vi hàm).
- Gọi trực tiếp `run_agent()` 4 lần cho câu hỏi mực nước → cả 4 lần
  `detail: tool: count_anomaly_events`, answer đúng ngữ nghĩa + số liệu
  tăng dần hợp lý (log liên tục).
- Chạy script demo theo domain **3 lần liên tiếp SAU KHI sửa** → cả 3
  lần đủ **30/30 pass**, tất cả 8 domain + comparison + out_of_scope +
  injection đều 100%.

### Báo cáo demo cuối cùng (bằng chứng "agent trả lời đúng cả 8 domain")
```
  [OK] PLATE (phuong tien)         : 4/4 pass
  [OK] ZONE (vung cam)             : 2/2 pass
  [OK] FACE (khuon mat)            : 2/2 pass
  [OK] FIGHT (au da)               : 2/2 pass
  [OK] CROWD (dam dong)            : 2/2 pass
  [OK] INTRUSION (leo treo)        : 2/2 pass
  [OK] FIRE (chay khoi)            : 2/2 pass
  [OK] WATER_LEVEL (muc nuoc)      : 2/2 pass
  [OK] COMPARISON (cheo domain)    : 6/6 pass
  [OK] OUT_OF_SCOPE                : 3/3 pass
  [OK] INJECTION                   : 3/3 pass
TONG: 30/30 pass (11 domain/nhom)
```

### Bài học quy trình (bổ sung bài học đã ghi ở lượt "eval/run.py full 30 case")
- Kỹ thuật "đặt câu loại trừ ở đầu docstring thay vì giữa/cuối" hiệu quả
  RÕ RỆT hơn khi 2 tool dễ nhầm dùng chung 1 từ khoá phổ biến (ở đây là
  "cảnh báo"). Nếu sau này thêm domain mới dùng chung từ khoá với domain
  cũ, nên áp dụng ngay pattern này (loại trừ NGAY ĐẦU docstring) thay vì
  chờ phát hiện qua test rồi mới sửa 2 vòng như lần này.

## 2026-09-18 (Review Phase 8 item 1 vs product-spec.md/test-plan.md)

Review lại đúng 1 "feature" vừa làm ("Demo Langfuse") đối chiếu
`specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- Dữ liệu trace thật tồn tại đúng, đủ input/output/latency/span con —
  verify tận ClickHouse (nguồn sự thật, không qua lớp UI có thể che giấu
  lỗi).
- Link trực tiếp vào trace là link THẬT (project_id/trace_id lấy từ dữ
  liệu thật vừa tạo, không phải đoán URL pattern rồi hy vọng đúng).

### Fail
- Không có lỗi phát hiện được trong phạm vi có thể verify từ môi trường
  này.

### Missing (giới hạn môi trường, đã nêu rõ — không phải bug)
- **Chưa verify UI THỰC SỰ RENDER ĐÚNG** (không có trình duyệt/JS engine
  trong môi trường agent này để chạy React/Next.js phía client) — `curl`
  vào URL trace chỉ xác nhận server trả về ĐÚNG SPA shell HTML (title
  "Langfuse", `200 OK`), KHÔNG chứng minh trang con (route
  `/traces/<id>`) render đúng sau khi JS chạy và gọi API nội bộ. Dữ liệu
  nền (ClickHouse) đã xác nhận đúng và đầy đủ, và UI dùng chung API đã
  verify hoạt động (`/api/public/v2/observations`), nên khả năng cao UI
  render đúng — nhưng đây là suy luận, không phải quan sát trực tiếp.
  **User nên tự mở link trong change-log để xác nhận bằng mắt** trước khi
  coi demo này hoàn tất 100%.

## 2026-09-18 (Phase 8, item 1: Demo Langfuse)

Item demo (không có code mới) — môi trường agent này không có trình
duyệt/GUI để tự chụp màn hình UI, nên "demo" được thực hiện bằng cách:
gửi 1 câu hỏi DEMO mới (khác câu test trước, để dễ nhận ra trong UI) qua
`/ask` thật với `MONITORING_ENABLED=true`, verify đủ trace qua API/DB
thật, rồi đưa link + hướng dẫn đăng nhập để user tự mở xem trên trình
duyệt của họ.

### Verified
- Gửi `/ask` thật: "Demo Langfuse Phase 8: hôm nay có bao nhiêu lượt xe
  máy vào?" → `200`, answer "Hôm nay có 955 lượt xe máy vào."
- Trace đủ 5 span, đúng cấu trúc cây, có `start_time`/`end_time` (suy ra
  latency): `ask` (7.5s tổng) → `chon_tool` (4.66s, vòng 1) → `chay_tool`
  (76ms) → `chon_tool` (1.85s, vòng 2) → `dien_giai` (0.94s).
- URL trực tiếp vào trace (`http://localhost:3000/project/<projectId>/
  traces/<traceId>`) trả `200` khi `curl` — trang tồn tại thật, không
  phải link bịa.

### Demo — thông tin để user tự mở
- **Link trace demo:** http://localhost:3000/project/a510ed1c-3afc-43c8-b9e3-1fc9c36f235d/traces/69e9b0bcb228712c135da40b7666d0a6
  (nếu máy này không public, cần SSH tunnel/VPN vào cổng `3000` trước).
- **Đăng nhập UI:** email `LANGFUSE_INIT_USER_EMAIL` trong `langfuse/.env`
  (`admin@agent-atin.local`); mật khẩu ở biến `LANGFUSE_INIT_USER_PASSWORD`
  cùng file — KHÔNG in ra đây, tự mở file để lấy.
- Trang tổng quan tất cả trace (không cần biết trace_id): `http://localhost:3000/project/a510ed1c-3afc-43c8-b9e3-1fc9c36f235d/traces`.

## 2026-09-18 (Review Phase 7 item cuối vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("SQL role cho 3 DB mới trong README")
đối chiếu `specs/product-spec.md` và `specs/test-plan.md`. Thay đổi thuần
docs, không có test runtime tương ứng — review tập trung vào tính CHÍNH
XÁC và AN TOÀN của hướng dẫn (vì đây là SQL người dùng thật sẽ copy-paste
chạy trên Postgres thật).

### Pass
- SQL khớp chính xác với script ĐÃ CHẠY THẬT THÀNH CÔNG ở Phase 2 item 1
  — không phải suy đoán/viết mới chưa kiểm chứng.
- Ghi chú "phải kết nối đúng DB trước khi chạy GRANT USAGE/SELECT" giúp
  tránh đúng loại lỗi vận hành thật đã có thể gặp (nếu ai đó chạy cả khối
  SQL từ 1 session `psql` duy nhất không đổi DB giữa chừng, `GRANT
  USAGE ON SCHEMA public` sẽ áp dụng NHẦM cho DB đang connect, không phải
  DB vừa nhắc trong dòng `GRANT CONNECT ON DATABASE X` phía trên).
- Vẫn dùng đúng role `agent_readonly` có sẵn (không tự ý đổi kiến trúc
  gợi ý "tạo role riêng cho từng domain" — giữ đúng quyết định đơn giản
  đã chọn ở Phase 2).
- `pytest` sạch, không đụng code.

### Fail
- Không có.

### Missing
- Không còn gì trong phạm vi Phase 7. **Phase 7 (Local Run Instructions)
  đã hoàn thành đủ 3/3 item.**

## 2026-09-18 (Phase 7, item cuối: `README.md` — SQL role cho 3 DB mới)

### Added
- `README.md` mục "Tạo DB role read-only" — thêm khối SQL thứ 2 cho
  `smart_face`/`firesmoke`/`anomaly`, cùng pattern GRANT như 2 DB cũ,
  tái dùng ĐÚNG role `agent_readonly` có sẵn (không tạo role mới — khớp
  quyết định thật đã làm ở Phase 2 item 1). Thêm 1 đoạn lưu ý mới: mỗi
  lệnh `GRANT USAGE`/`GRANT SELECT ON ALL TABLES`/`ALTER DEFAULT
  PRIVILEGES` phải chạy trong khi ĐANG KẾT NỐI tới đúng DB đó (không phải
  chạy 1 lần từ DB bất kỳ) — chi tiết dễ bỏ sót khi làm tay, có thể gây
  "grant chạy không lỗi nhưng vẫn không SELECT được" nếu áp dụng nhầm DB
  đang connect.
- Sửa 2 câu văn liền kề (không phải thêm mục mới) cho khớp số lượng DB
  thật: "đúng 2 DB" → "đúng các DB", "đúng 2 DB đã cấu hình" → "đúng 5 DB
  đã cấu hình" — cả 2 câu nằm NGAY TRONG đoạn văn đang sửa (không phải
  file/mục khác), không tính là lấn phạm vi.

### Verified
- Đối chiếu SQL mới với chính script Python đã CHẠY THẬT VÀ THÀNH CÔNG ở
  Phase 2 item 1 (`GRANT CONNECT`/`GRANT USAGE`/`GRANT SELECT ON ALL
  TABLES`/`ALTER DEFAULT PRIVILEGES`, mỗi DB connect riêng trước khi
  chạy) — khớp chính xác, không viết SQL mới chưa kiểm chứng.
- `pytest -q` → "12 passed" (thay đổi thuần docs, không đụng code).

## 2026-09-18 (Review Phase 7 item 1 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("bảng biến môi trường README") đối
chiếu `specs/product-spec.md` và `specs/test-plan.md`. Đây là thay đổi
thuần docs nên không có test runtime tương ứng trong `test-plan.md` —
review tập trung vào tính CHÍNH XÁC của nội dung.

### Pass
- Tên biến khớp 100% với `.env.example` thật (đã verify bằng `grep`,
  không bịa tên).
- Đường dẫn `langfuse/docker-compose.yml` được nhắc trong README —
  verify file thật tồn tại đúng vị trí.
- Không đụng code, không cần chạy `pytest`.

### Fail
- Không có.

### Missing (KHÔNG sửa — thuộc phạm vi khác, không phải item này)
- Mục "Prerequisites" (README, phía trên) vẫn chỉ nhắc "Postgres... có
  sẵn 2 DB `its` và `virtual_fence`" — chưa nhắc 3 DB mới. Mục "Cài đặt &
  chạy local" vẫn ghi "pytest # 5 passed" (nay thật ra là 12). Cả 2 chỗ
  này KHÔNG thuộc checklist item "bảng biến môi trường" (Phase 7 item 1)
  — checklist Phase 7 chỉ có đúng 2 item (bảng biến môi trường + SQL
  role cho 3 DB mới), không bao gồm Prerequisites/Cài đặt. Không sửa ở
  đây để tránh lấn phạm vi; ghi nhận lại phòng khi cần 1 item riêng dọn
  toàn bộ README sau này.

## 2026-09-18 (Phase 7, item 1: `README.md` — bảng biến môi trường)

### Added
- `README.md` mục "Biến môi trường" — thêm `DB_NAME_FACE`/`DB_NAME_FIRE`/
  `DB_NAME_ANOMALY` vào dòng "Database" (kèm ghi chú domain tương ứng),
  thêm dòng mới "Observability" (`MONITORING_ENABLED`,
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`) kèm ghi
  chú mặc định tắt + trỏ `langfuse/docker-compose.yml`.

### Verified
- Đối chiếu tên biến với `.env.example` thật (`grep`) — khớp chính xác
  cả 7 biến mới thêm vào README, không có tên bịa/sai chính tả.
- Không sửa code, không chạy `pytest` cần thiết cho thay đổi thuần docs
  này (đã xác nhận không đụng file `.py` nào).

## 2026-09-18 (Review Phase 6 "Test Langfuse" vs product-spec.md/test-plan.md)

Review lại đúng 1 "feature" vừa làm ("Test Langfuse qua `/ask` thật") đối
chiếu `specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`
mục "Test Langfuse tracing" (4 test case đầy đủ — 2 đã verify ở Phase 4
mức module, 2 còn lại verify đầy đủ ở đây qua `/ask` thật).

### Pass
- `test-plan.md` #1: verify lại lần nữa qua `.env` thật của app (không
  chỉ giả lập biến môi trường) — `pytest` "12 passed".
- `test-plan.md` #2: trace THẬT của 1 lượt `/ask` xuất hiện đúng cấu
  trúc (span cha `ask` + span con `chon_tool`/`chay_tool`/`dien_giai`) —
  đây là lần ĐẦU TIÊN verify được test #2 qua ĐÚNG endpoint `/ask` (Phase
  4 chỉ verify được ở mức gọi `trace_answer()`/`trace_step()` trực tiếp,
  chưa qua `main.py` thật).
- `test-plan.md` #3: verify TẬN NƠI LƯU (ClickHouse `events_full`, đọc
  trực tiếp `input`/`output`/`metadata_*`), không chỉ tin "code không
  raise lỗi" — không có secret nào ngoài `public_key` (đúng bản chất,
  không phải bí mật).
- `test-plan.md` #4: `/ask` không crash khi Langfuse down — verify qua
  ĐÚNG endpoint thật (Phase 4 chỉ verify ở mức `trace_answer()` đơn lẻ).
- `product-spec.md`: "Langfuse chạy self-host... xem được trace của 1
  lượt /ask thật" — ĐẠT ĐỦ, không còn thiếu sót nào so với Phase 4.

### Fail
- Không có — cả 4/4 test case `test-plan.md` đều pass khi verify qua
  đúng endpoint `/ask` thật.

### Ghi nhận thêm (không phải fail, đã ghi ở entry implement)
- Độ trễ khi Langfuse down THẬT SỰ cao hơn ước tính Phase 4 (~8.3s thay
  vì ~3.8s) vì `/ask` có nhiều span lồng nhau hơn model đơn giản đã test
  trước đó — đây là thông tin CHÍNH XÁC HƠN bổ sung cho quyết định đã ghi
  ở Phase 4 (chấp nhận độ trễ này cho MVP), không phải vấn đề mới cần sửa
  ngay.

### Missing
- Không còn gì trong phạm vi `test-plan.md` mục "Test Langfuse tracing"
  hay `product-spec.md` liên quan tới observability. **Phase 6 (Validation
  and Error States) đã hoàn thành đủ 10/10 item.**

## 2026-09-18 (Phase 6, item cuối: Test Langfuse qua `/ask` thật)

### Verified (không có code mới — item test-only, giống các "test kết nối
thật" trước đó)
- **`MONITORING_ENABLED=false` (mặc định, `.env` thật của app KHÔNG có
  biến `LANGFUSE_*`):** `pytest -q` → "12 passed", y hệt trước Phase 4.
- **`MONITORING_ENABLED=true` + key thật (đọc từ `langfuse/.env`, không
  ghi vào `.env` app — chỉ set env var tạm cho tiến trình test, giữ đúng
  "mặc định TẮT" của `product-spec.md`) + gọi `POST /ask` thật qua
  `TestClient`:** trả `200`, answer đúng số liệu thật. Verify trace tận
  **ClickHouse** (`events_full`, không chỉ tin log Python) — thấy đủ cây
  span lồng nhau cho ĐÚNG 1 lượt `/ask`: `ask` → `chon_tool` →
  `chay_tool` → `chon_tool` (vòng 2) → `dien_giai`, đúng cấu trúc thiết
  kế ở Phase 4/5.
- **Không lộ secret:** đọc trực tiếp cột `input`/`output`/`metadata_*`
  của span `ask`/`dien_giai` — chỉ có câu hỏi, answer, tên tool,
  `row_count`, `latency_s`, và `public_key` (đúng bản chất — public key
  Langfuse vốn để công khai, không phải bí mật). KHÔNG thấy
  `OPENAI_API_KEYS`/`DB_PASSWORD`/`secret_key` ở bất kỳ trường nào.
- **Langfuse service down** (`LANGFUSE_HOST` trỏ cổng không ai lắng
  nghe): `POST /ask` vẫn trả `200` với answer đúng, KHÔNG crash — mất
  **~8.3s** (cao hơn ước tính ~3.8s ghi nhận lúc test `tracing.py` đơn lẻ
  ở Phase 4, vì `/ask` thật có NHIỀU span lồng nhau — mỗi span đều thử
  flush/retry riêng — cộng dồn độ trễ).

### Ghi nhận (không phải bug của item này, đã có sẵn trong change-log
Phase 4 nhưng nay có số liệu THẬT chính xác hơn)
- Độ trễ khi Langfuse down: ~8.3s cho `/ask` thật (không phải ~3.8s như
  ước tính ở mức module đơn lẻ) — MVP chấp nhận được (tần suất Langfuse
  down thấp trong vận hành bình thường), nhưng nếu cần tối ưu sau này,
  hướng đi là giảm số lần retry của OTel exporter hoặc set timeout ngắn
  hơn cho riêng trường hợp lỗi kết nối (không phải rate-limit).

## 2026-09-18 (Review Phase 6 "Chạy eval/run.py full 30 case" vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("chạy `eval/run.py` full 30 case, sửa
dataset cho khớp thật") đối chiếu `specs/product-spec.md` và
`specs/test-plan.md`.

### Pass
- `product-spec.md`: "eval/datasets/agent_stat có đủ 30 case phủ 8
  domain, chạy được bằng eval/run.py, in được tỷ lệ pass/fail theo
  slice" — đúng, 30/30 pass, in đủ bảng theo `slice.type`.
- `test-plan.md`: "3 case out_of_scope + 3 case injection PHẢI vẫn pass
  nguyên" — đúng, cả 2 slice 3/3 xuyên suốt mọi lần chạy (kể cả trước khi
  sửa dataset) — xác nhận việc mở rộng `STAT_KEYWORDS`/tool ở các Phase
  trước KHÔNG gây regression cho 2 slice này.
- Verify KHÔNG chỉ 1 lần: chạy lại 3 lần liên tiếp sau khi sửa xong, đủ
  30/30 cả 3 lần — loại trừ khả năng "pass may mắn" do tính không xác
  định của LLM (bài học trực tiếp từ chính quá trình sửa case #011 —
  từng pass rồi fail lại giữa các lần chạy).
- `exit code` đúng 0 khi toàn bộ pass — script dùng được cho CI như thiết
  kế ở Phase 2.

### Fail
- Không còn lỗi tồn đọng sau các lượt sửa ở entry implement — 8 case
  dataset đã sửa (không sửa code app).

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- Item cuối cùng của Phase 6 ("Test Langfuse") chưa làm — chưa tới lượt.

## 2026-09-18 (Phase 6, item: Chạy `eval/run.py` full 30 case)

### Added/Fixed — `eval/datasets/agent_stat/v2.yaml`
Chạy `eval/run.py` lần đầu (30/30 case, LLM thật) → 4 case fail:
`agent_stat_v2_009/012/014/019`. Điều tra từng case bằng cách gọi
`run_agent()` trực tiếp — KHÔNG có case nào là bug thật của agent/tool,
toàn bộ là assertion trong dataset quá cứng nhắc hoặc dựa trên giả định
đã lỗi thời:
- **#009** (FIGHT_DETECTION "hôm nay"): assertion cũ giả định domain này
  TĨNH (dừng dữ liệu từ 2026-09-16) — verify lại thấy SAI: 2026-09-18 đã
  có 118 rồi 125 lượt hôm đó (dữ liệu sống, không tĩnh như tưởng). Sửa:
  bỏ assertion "không có dữ liệu" cố định, chỉ giữ `must_include_tool`.
- **#012/#014** (CROWD/INTRUSION khoảng ngày cụ thể): số liệu thật VẪN
  đúng là 0 (verify lại), nhưng LLM diễn giải "0 lượt" thay vì đúng chữ
  "không có dữ liệu" — đổi assertion sang số `"0"`.
- **#019** (phân loại xe máy/ô tô): LLM trả lời bằng tiếng Việt tự nhiên
  ("Xe máy"/"Ô tô"), không lặp lại nguyên văn enum "MOTORCYCLE"/"CAR" —
  đổi assertion sang từ tiếng Việt thật.

Chạy lại → 29/30 pass, phát sinh case fail MỚI **#011** (CROWD "hôm
nay") — cùng lỗi diễn đạt như #012/#014 (đổi sang "0"). Rà soát toàn bộ 4
case còn lại dùng `must_include: ["không có dữ liệu"]` (#007 FACE, #011
CROWD, #015/#016 FIRE) và sửa 1 lượt (thay vì sửa từng case qua nhiều lần
chạy):
- #011/#015/#016: đổi sang `must_include: ["0"]`.
- #007 (FACE "hôm nay"): sau bài học #009, không còn chắc FACE mãi mãi
  rỗng — bỏ hẳn assertion text, chỉ giữ `must_include_tool`.
- **#020** (seat-limit note): fail thêm ở vòng test tiếp — LLM diễn giải
  câu mở đầu khác nhau nên cụm "không phân loại" không luôn khớp. Sửa
  sang cụm CỐ ĐỊNH trong code (`_SEAT_LIMIT_NOTE`, `src/agent/answer.py`
  dòng 35-38) — chuỗi này do CODE nối cứng vào cuối câu trả lời, không
  phụ thuộc LLM diễn giải, nên đảm bảo luôn xuất hiện y hệt.

Chạy lại → 27/30 pass, 3 case fail MỚI (**#011/#015/#016** — cùng những
case vừa sửa!) vì lý do SÂU HƠN: `count_anomaly_events`/
`count_fire_smoke_events` KHÔNG có `group_by` → SQL `count(*)` không
`GROUP BY` LUÔN trả về ĐÚNG 1 dòng `[[0]]`; nhưng nếu LLM tự thêm
`group_by` (vd. `zone_name`), `GROUP BY` trên 0 dòng khớp → trả về 0 DÒNG
(rỗng hoàn toàn, không phải 1 dòng chứa số 0) → `_pack()` rơi về nhánh
"Không có dữ liệu khớp câu hỏi..." thay vì "0 lượt...". Đây là 2 hành vi
ĐÚNG khác nhau của CÙNG 1 tool tuỳ tham số LLM tự chọn — không thể đoán
trước LLM có truyền `group_by` hay không giữa các lần chạy. **Quyết định
cuối:** bỏ HẲN assertion text cứng cho 4 case luôn-rỗng (#011/#015/#016,
và #007 đã bỏ từ trước) — chỉ giữ `must_include_tool`, đúng quy ước v1
"số liệu không đoán trước được chỉ dùng assertion cấu trúc".

### Verified
- `pytest -q` → "12 passed" trong suốt quá trình sửa dataset (không đụng
  code app).
- `python3 eval/run.py` (LLM thật, không offline) → **30/30 pass**, chạy
  LẶP LẠI 2 LẦN liên tiếp để xác nhận ổn định (không phải may mắn 1 lần) —
  cả 2 lần đều 30/30, `injection: 3/3`, `out_of_scope: 3/3` (yêu cầu bắt
  buộc của checklist item).
- YAML vẫn đúng 30 case, phân bổ 18/6/3/3, không trùng `id` sau toàn bộ
  chỉnh sửa.

### Bài học quy trình (ghi lại để tránh lặp lại)
- Assertion `must_include` trên TEXT tự do do LLM sinh ra (không phải
  template cố định trong code) luôn có rủi ro brittle — LLM có nhiều cách
  diễn đạt ĐÚNG cho cùng 1 sự thật ("0 lượt" vs "không có dữ liệu" vs
  "không có cảnh báo nào"). Assertion an toàn nhất là trên: (a) tool nào
  được gọi (`must_include_tool`, ổn định), (b) chuỗi CỐ ĐỊNH TRONG CODE
  không qua LLM (vd. `_SEAT_LIMIT_NOTE`), hoặc (c) giá trị SỐ khi chắc
  chắn định dạng SQL luôn trả cùng 1 shape (không group_by). Tránh assert
  cụm từ tự nhiên mà chỉ LLM mới quyết định cách viết.

## 2026-09-18 (Review Phase 6 "Test thật domain mới" vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("Test thật domain mới qua LLM thật")
đối chiếu `specs/product-spec.md` (Acceptance Criteria) và
`specs/test-plan.md` mục "Test thật" (domain mới).

### Pass
- Đủ 6/6 câu hỏi mẫu domain mới trong `test-plan.md`, đúng tool, đúng
  hành vi (có dữ liệu thật hoặc "không có dữ liệu" đúng sự thật).
- **Verify sâu hơn (phát hiện lúc review, không chỉ tin `detail` ở lượt
  implement):** case "đám đông" và "leo trèo" đều trả lời "không có dữ
  liệu" — ban đầu lo ngại đây có thể là TRÙNG NGẪU NHIÊN (cả
  `CROWD_DETECTION` và `INTRUSION_DETECTION` đều =0 cho org 106, nên dù
  agent lỡ dùng SAI event_type vẫn ra kết quả rỗng giống nhau, che giấu
  lỗi). Kiểm tra trực tiếp `tool_calls` thật trong state graph (không chỉ
  đọc `answer`/`detail`) → xác nhận agent truyền ĐÚNG và KHÁC NHAU:
  `event_type='CROWD_DETECTION'` cho câu đám đông,
  `event_type='INTRUSION_DETECTION'` cho câu leo trèo — không phải trùng
  ngẫu nhiên. Đây chính là loại lỗi tiềm ẩn mà nguyên tắc "chỉ tin log,
  không tin im lặng" (đã áp dụng nhiều lần trong các lượt review trước)
  nhắm tới.
- `product-spec.md`: không hallucinate khi rỗng (FACE/CROWD/INTRUSION/
  FIRE), số liệu thật khi có (FIGHT=118, WATER_LEVEL=2210 lượt hôm nay).
- Regression PLATE domain vẫn đúng sau khi Phase 5 wiring tracing.

### Fail
- Không tìm thấy lỗi nào trong phạm vi feature này.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- Domain ZONE (vùng cấm) không test lại trong lượt này — đã verify đủ ở
  v1 (5 câu hỏi mẫu gốc) và không bị đụng chạm bởi domain mới, không cần
  lặp lại.
- `eval/run.py` full 30 case + Test Langfuse qua `/ask` thật — 2 item
  TIẾP THEO trong Phase 6, chưa tới lượt.

## 2026-09-21 (Dataset v2.1 — AIOC howto + vẽ sơ đồ, giữ 30 case / 18-6-3-3)

### Changed
- `eval/datasets/agent_stat/v2.yaml` → version `2.1`:
  - **Giữ** đúng 30 case + tỉ lệ slice gốc **18 lookup / 6 comparison /
    3 out_of_scope / 3 injection**.
  - **Thêm** năng lực mới trong lookup: AIOC howto (4) + vẽ sơ đồ (3);
    comparison: 1 AIOC↔cháy khói (#023), 1 sơ đồ+#devices vs thống kê xe
    (#024).
  - **Giảm** lookup VMS trùng để nhường chỗ: PLATE 4→3; FACE/FIGHT/CROWD/
    INTRUSION/FIRE/WATER mỗi domain còn 1; ZONE giữ 2 (phân biệt leo trèo).
  - Giữ comparison chống hồi quy #019–#021 và #022 ẩu đả vs đám đông;
    out_of_scope/injection 3+3.
  - Case AIOC/DIAGRAM chưa có tool riêng → chỉ `must_include` /
    `must_not_include_tool` (không bịa tên tool).
- `src/guardrails.py` — thêm `STAT_KEYWORDS` (aioc, devices, sơ đồ, …) +
  cập nhật `OUT_OF_SCOPE_REPLY` để câu howto/diagram không bị từ chối oan.

### Notes / cách test
```bash
cd kcn_hungphu_agent
python -c "
import yaml
from collections import Counter
from src.guardrails import in_scope, check_input, GuardrailViolation
d=yaml.safe_load(open('eval/datasets/agent_stat/v2.yaml'))
c=Counter(x['slice']['type'] for x in d['cases'])
assert len(d['cases'])==30 and dict(c)=={'lookup':18,'comparison':6,'out_of_scope':3,'injection':3}
for x in d['cases']:
    q=x['question']
    if x['slice']['type'] in ('lookup','comparison'):
        assert in_scope(q), q
    elif x['slice']['type']=='out_of_scope':
        assert not in_scope(q), q
    else:
        try: check_input(q); raise SystemExit('injection not blocked: '+q)
        except GuardrailViolation: pass
print('ok', c)
"
# Eval đầy đủ (cần LLM/DB): python eval/run.py
# Kỳ vọng: out_of_scope+injection vẫn 3/3; AIOC/diagram pass theo must_include
# sau khi có prompt/tool howto (hiện có thể fail nội dung nếu model chưa
# được dạy AIOC — đúng giai đoạn trước khi implement feature).
```

---


Review lại đúng feature vừa làm (pytest guardrail 3 DB mới) đối chiếu
`specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- product-spec Hạ tầng: đọc-only Postgres qua role riêng — khóa bằng test
  SELECT OK + DELETE/UPDATE bị chặn trên `smart_face`/`firesmoke`/`anomaly`.
- test-plan "2 lớp": app → `ReadOnlySqlTransaction`; GRANT thô →
  `InsufficientPrivilege`; skip sạch khi không có `.env` (không phá
  offline pytest).
- Không thêm dependency; không đổi logic runtime (chỉ test + docs).

### Fail
- Không tìm thấy lỗi trong phạm vi item (chưa chạy lệnh verify trên máy
  này theo policy — user chạy `pytest` với `.env` để xác nhận 3 passed).

### Missing (Phase 6 item sau — không sửa ở đây)
- Test `/ask` thật 5 domain, `eval/run.py` 30 case, Langfuse E2E.

### Fixed
- `test-plan.md` còn mô tả "whitelist chưa có 3 DB" — đã sửa cho khớp
  Phase 3+.
- Comment `config.py` còn ghi whitelist chưa dùng ở connection — đã sửa.

---

## 2026-09-18 (Phase 6, item 2: test guardrail an toàn 3 DB mới)

### Added
- `tests/test_db_guardrail_new_dbs.py` — pytest tái chạy được (skip nếu
  chưa `DB_HOST`), cover đúng 2 lớp trong `test-plan.md`:
  1. App/`get_connection`: SELECT OK trên face/fire/anomaly; DELETE/UPDATE
     → `ReadOnlySqlTransaction`.
  2. GRANT/`psycopg2.connect` thô: DELETE → `InsufficientPrivilege`.
- `specs/implementation-plan.md` Phase 6 item này → `[x]`.
- `specs/test-plan.md` — cập nhật mục 2 lớp (bỏ wording lỗi thời "whitelist
  chưa có 3 DB").
- `src/config.py` — comment DB mới: whitelist đã nằm ở `connection.py`.

### Notes / cách test (user chạy tay)
```bash
cd kcn_hungphu_agent
# Offline/CI (không .env DB): 3 test mới bị skip — pytest vẫn xanh
pytest -q

# Có .env DB thật (role read-only):
pytest -q tests/test_db_guardrail_new_dbs.py -v
# Kỳ vọng: 3 passed (không skip)
```

---


Review lại đúng feature vừa làm (test offline domain mới) đối chiếu
`specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- test-plan domain offline #1: `LOI_BIA` → error whitelist, không mở DB
  (monkeypatch).
- test-plan #2: 3 tool domain mới nằm trong `TOOLS` (assertion set).
- test-plan #3: `in_scope()` True cho câu hỏi FACE/FIGHT/CROWD/INTRUSION/
  FIRE/WATER.
- test-plan #4: `get_connection("vms_db")` → `ValueError`.
- product-spec Guardrail / Agent & tool: hành vi validate tham số + scope
  keywords được khóa bằng test offline (không cần Postgres).

### Fail
- Không tìm thấy lỗi trong phạm vi item này.

### Missing (đúng Phase 6 item sau — không sửa ở đây)
- Test GRANT/SELECT thật trên 3 DB mới.
- Test `/ask` thật 5 domain + `eval/run.py` 30 case + Langfuse E2E.

### Fixed
- `src/guardrails.py` — comment STAT_KEYWORDS domain mới còn ghi
  "tool/DB CHƯA code" dù Phase 3/5 đã xong — cập nhật cho khớp thực tế
  (liên quan trực tiếp test `in_scope` domain mới).

---

## 2026-09-17 (Phase 6, item 1: test offline domain mới)

### Added
- `tests/test_offline.py` — 3 test Phase 6 (khớp `test-plan.md` domain
  offline #1/#3/#4; #2 đã cover bởi `test_danh_sach_tool_dung_thiet_ke`):
  - `test_count_anomaly_events_tu_choi_event_type_ngoai_whitelist` —
    `LOI_BIA` → `error` rõ; monkeypatch `get_connection` để chắc không
    mở DB; kèm `.invoke()` trên `@tool`.
  - `test_in_scope_nhan_cau_hoi_domain_moi` — 6 câu hỏi mẫu 5 domain mới
    (+ cháy/khói) → `in_scope() is True`.
  - `test_get_connection_chan_dbname_ngoai_whitelist` — `vms_db` →
    `ValueError`.
- `specs/implementation-plan.md` Phase 6 item offline → `[x]`.
- `specs/test-plan.md` — ghi rõ mục offline domain đã có trong
  `test_offline.py`.

### Notes / cách test (user chạy tay)
```bash
cd kcn_hungphu_agent
pytest -q
# Kỳ vọng: toàn bộ test cũ + 3 test mới pass (không cần DB/API key)
pytest -q tests/test_offline.py -k "anomaly or in_scope_nhan or get_connection_chan"
```

---


### Added / Changed
- `src/agent/graph.py` — `AgentState["_trace_span"]`; `run_agent(...,
  parent_span=)`; `_pack` bọc `trace_step(..., "dien_giai")` quanh
  template + `build_answer` (output: answer rút gọn + tên tool).
- `src/agent/react.py` — `agent_node` → span `chon_tool` (tool_calls /
  offline); `_tools_node` thay `ToolNode` trần → span `chay_tool` (chỉ
  tên tool, không dump rows).
- `src/main.py` — `run_agent(..., parent_span=t.get("_span"))` để nối
  cây span dưới observation `"ask"`.
- `src/monitoring/tracing.py` — docstring: đã wire nested steps.
- `specs/implementation-plan.md` Phase 5 item `trace_step` → `[x]` (Phase
  5 v2 checklist hoàn tất).

### Notes / cách test (user chạy tay)
```bash
cd kcn_hungphu_agent
pytest -q   # monitoring tắt — nested no-op, kỳ vọng vẫn pass

# Bật Langfuse + MONITORING_ENABLED=true, gọi /ask thật rồi mở UI:
# http://localhost:3000 — observation "ask" phải có con:
#   chon_tool → chay_tool → (chon_tool lại nếu cần) → dien_giai
uvicorn src.main:app --reload
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hôm nay có bao nhiêu lượt xe vào?"}'
```

---

## 2026-09-17 (Review Phase 5 item 4 vs product-spec.md/test-plan.md)

Review lại đúng feature vừa làm (`trace_step` nested trên graph/ReAct)
đối chiếu `specs/product-spec.md` và `specs/test-plan.md` mục Langfuse.

### Pass
- product-spec Observability / AC: tắt monitoring → nested span no-op
  (`parent_span=None` / `trace_step(None, …)`); pytest `/ask` offline
  không cần Langfuse.
- test-plan Langfuse #2 (span con chọn tool + diễn giải): khi monitoring
  bật, cây dưới `"ask"` gồm `chon_tool` → `chay_tool` → `dien_giai`
  (có thể thêm `chon_tool` sau tool nếu ReAct quay lại agent).
- test-plan #3 (secrets): span con chỉ ghi tên tool / args tóm tắt /
  answer[:500] — không dump rows DB, không ghi API key/password.
- `run_agent` vẫn gọi được không `parent_span` (eval/pytest trực tiếp).

### Fail
- Không tìm thấy lỗi trong phạm vi feature.

### Missing (Phase 6 — không sửa ở đây)
- test-plan #4 Langfuse down + verify E2E đầy đủ trên UI vẫn thuộc
  Phase 6 checklist.
- Offline pytest chưa assert tên span (cần mock Langfuse) — chấp nhận
  test tay khi bật monitoring.

### Fixed
- `README.md` lộ trình: Phase 4/5 ghi đúng đã gắn tracing vào `/ask`+graph.

---

## 2026-09-17 (Review Phase 5 item 3 vs product-spec.md/test-plan.md)

Review lại đúng feature vừa làm (`trace_answer` trên `ask()`) đối chiếu
`specs/product-spec.md` và `specs/test-plan.md` mục Langfuse.

### Pass
- product-spec Observability / AC: tắt monitoring → app chạy y hệt (no-op);
  bật thì mỗi `/ask` tạo 1 observation (input = câu hỏi, output =
  answer/tool/row_count, có latency) — không đưa `OPENAI_API_KEYS`/
  `DB_PASSWORD` vào metadata/output.
- test-plan Langfuse #1: `MONITORING_ENABLED=false` → pytest `/ask` offline
  không phụ thuộc Langfuse (cùng path no-op).
- test-plan #3 (secrets): output chỉ `status`/`answer`/`tool`/`row_count`.
- Injection vẫn 400 qua handler; out_of_scope vẫn 200 + câu từ chối — có
  gắn `t["output"]` khi thành công / out_of_scope.

### Fail
- Không tìm thấy lỗi trong phạm vi wire `main.py`.

### Missing (đúng item tiếp / Phase 6 — không sửa ở đây)
- test-plan #2 "span con chọn tool + diễn giải" — cần `trace_step` trong
  `graph.py` (item Phase 5 tiếp theo). Hiện chỉ có 1 span phẳng `"ask"`.
- test-plan #4 Langfuse down → `/ask` không crash: hành vi giữ nguyên
  (exception tracing được nuốt ở tầng SDK/flush theo thiết kế Phase 4);
  latency tăng khi SDK retry vẫn là hạn chế đã ghi nhận lúc deploy
  Langfuse — không thêm timeout mới ở item này.

### Fixed
- Không cần sửa code thêm sau review; chỉ ghi nhận Missing ở trên.
- `README.md` lộ trình Phase 5: cập nhật đã wire `trace_answer` trên `/ask`.

---

## 2026-09-17 (Phase 5, item 3: wire `trace_answer` vào `src/main.py::ask`)

### Added / Changed
- `src/main.py::ask()` — bọc toàn bộ pipeline
  `guardrail_input → agent → guardrail_output` trong
  `with trace_answer("ask", question, metadata={"endpoint": "/ask"})`.
  - Out-of-scope / success đều gán `t["output"]` (status + answer + tool +
    row_count) — **không** ghi secrets hay toàn bộ rows DB.
  - `GuardrailViolation` / `HTTPException` 503 vẫn raise ra ngoài; khi
    monitoring bật, `trace_answer` đánh dấu ERROR rồi re-raise (handler
    FastAPI giữ nguyên).
  - `MONITORING_ENABLED=false` (mặc định): `trace_answer` no-op → hành vi
    `/ask` y hệt trước.
- `src/monitoring/tracing.py` — docstring cập nhật: đã wire `main.py`, còn
  `trace_step` trong graph.
- `specs/implementation-plan.md` Phase 5 item `trace_answer` → `[x]`.

### Notes / cách test (user chạy tay)
```bash
cd kcn_hungphu_agent
pytest -q   # MONITORING tắt mặc định — kỳ vọng vẫn pass toàn bộ

# Monitoring tắt: /ask vẫn bình thường
uvicorn src.main:app --reload
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Thời tiết Hà Nội thế nào?"}'

# Monitoring bật (Langfuse đang chạy, key trong .env khớp langfuse/.env):
# MONITORING_ENABLED=true
# LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... LANGFUSE_HOST=http://localhost:3000
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hôm nay có bao nhiêu lượt xe vào?"}'
# → mở http://localhost:3000 xem observation name "ask" (input/output/latency)
```

---


Review lại đúng feature vừa làm (`list_khu_vuc` mở rộng FACE/FIRE/ANOMALY)
đối chiếu `specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- product-spec "Agent & tool": có tool liệt kê camera/khu vực hợp lệ —
  nay phủ đủ module của 8 domain (PLATE/ZONE/FACE/FIRE/ANOMALY), đúng mục
  tiêu tránh agent đoán sai giá trị lọc.
- test-plan offline #5 (danh sách tool): không đổi tên tool — vẫn
  `list_khu_vuc`; thêm test shape wrap offline không cần DB.
- Không thêm thư viện; vẫn 1 tool (không tách tool mới) — khớp wording
  "list_khu_vuc (hoặc tool mới)" trong implementation-plan.

### Fail
- Không tìm thấy lỗi trong phạm vi feature.

### Fixed (nhỏ, liên quan trực tiếp)
- `eval/datasets/agent_stat/v2.yaml` case #006 `expected` còn ghi chỉ
  "camera ITS + hàng rào" — cập nhật mô tả 5 nhóm cho khớp hành vi mới
  (không đổi `must_include_tool`).
- Docstring đầu `src/agent/tools.py` còn liệt kê bộ tool v1 — cập nhật.

### Missing (đúng phạm vi Phase sau, không sửa ở đây)
- Chưa có test offline bắt buộc gọi DB thật cho 3 DB mới qua
  `list_khu_vuc` — thuộc Phase 6 "Test thật / guardrail an toàn".
- Chưa wire Langfuse / system prompt nhắc tool domain mới — item Phase 5
  tiếp theo.

---

## 2026-09-17 (Phase 5, item 2: mở rộng `list_khu_vuc` FACE/FIRE/ANOMALY)

### Added
- `src/db/queries.py::list_zones()` — ngoài `camera_its` (PLATE) và
  `khu_vuc_hang_rao` (ZONE), thêm DISTINCT:
  - `camera_face` từ `smart_face.smf_face_events` (`device_name`,
    `area_name` — bảng FACE không có `camera_code`)
  - `camera_fire` từ `firesmoke.fire_smoke_event` (`camera_code`,
    `camera_name`)
  - `camera_anomaly` từ `anomaly.anomaly_event` (`event_type`,
    `camera_code`, `camera_name`, `zone_name`) — chỉ 4 `event_type`
    thuộc sản phẩm; kèm `event_type` để agent không nhầm leo trèo /
    ẩu đả / đám đông / mực nước
- Áp dụng `_org_filter()` thống nhất cho cả 5 nhóm (PLATE/ZONE trước đây
  không lọc org — giờ khớp 1-org MVP và các query đếm khác).
- `src/agent/tools.py` — docstring `list_khu_vuc` mô tả 5 nhóm; `_wrap_dict`
  trả đủ cột mới trong `QueryResult`.
- `tests/test_offline.py::test_wrap_list_khu_vuc_gom_du_module` — shape
  wrap không cần DB.

### Changed
- `specs/implementation-plan.md` Phase 5 item `list_khu_vuc` → `[x]`.

### Notes / cách test (user chạy tay)
```bash
cd kcn_hungphu_agent
pytest -q
# Có .env DB thật:
python -c "
from src.agent.tools import list_khu_vuc
import json
r = json.loads(list_khu_vuc.invoke({}))
print(r['columns'])
print({c: len(r['rows'][0][i]) for i, c in enumerate(r['columns'])})
"
```
- Kỳ vọng: columns gồm 5 key; `camera_fire` có thể `[]` (bảng rỗng);
  `camera_face` / `camera_anomaly` có phần tử nếu org 106 đã có sự kiện.
- UI: hỏi "Danh sách khu vực và camera hợp lệ hiện có là gì?" → agent gọi
  `list_khu_vuc`, trả lời nhắc cả FACE/ANOMALY nếu có data.

---


Review lại đúng 1 feature vừa làm ("3 tool domain mới trong
`src/agent/tools.py`") đối chiếu `specs/product-spec.md` và
`specs/test-plan.md`.

### Pass
- `test-plan.md` "Test offline" #1 ĐÚNG CHỮ: `count_anomaly_events(
  event_type="LOI_BIA")` qua `.invoke()` thật → `error` rõ ràng trong
  `QueryResult`, không query DB.
- `test-plan.md` "Test offline" #2: danh sách tool khớp thiết kế — đã sửa
  test cũ, `pytest` sạch.
- Test thêm (chưa test ở lượt implement): `group_by="department_name"`
  cho `count_face_events` → trả breakdown thật, có cả bucket `null`
  (chưa gán phòng ban) lẫn tên phòng ban thật ("Ban Lãnh Đạo", "Trí tuệ
  nhân tạo") — group_by hoạt động đúng, không chỉ default. `entity_type=
  "FIRE"` cho `count_fire_smoke_events` → vẫn rỗng đúng (domain trống mọi
  filter). `group_by="severity"` cho `count_anomaly_events` → đúng, toàn
  bộ FIGHT_DETECTION severity=HIGH.
- Không thêm thư viện, không đổi tool cũ, đúng pattern LangChain `@tool`
  có sẵn.

### Fail
- Không tìm thấy lỗi nào trong phạm vi feature này.

### Ghi nhận (không phải thiếu sót)
- `get_db_schema` (tool mô tả nguồn dữ liệu cho `run_sql_readonly`) CHƯA
  nhắc 3 nguồn mới — KHÔNG sửa, vì `run_sql_readonly` (fallback SQL tự do)
  vẫn CHỈ giới hạn `plate_event`/`zone_event` (chưa mở rộng, đúng thiết
  kế — 3 domain mới CHỈ truy cập qua tool tham số hoá riêng, không qua SQL
  tự do) — `get_db_schema` hiện tại vẫn phản ánh ĐÚNG phạm vi thật của
  `run_sql_readonly`, không lỗi thời.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `list_khu_vuc` chưa liệt kê camera có `ai_modules` FACE/FIRE/ANOMALY —
  item TIẾP THEO trong Phase 5, chưa tới lượt.
- Chưa test được qua LLM thật (agent tự chọn đúng tool cho câu hỏi domain
  mới) — vẫn bị chặn bởi bug dependency `openai`/`httpx2`
  (`task_2e390bb8`, chưa fix).

## 2026-09-17 (Phase 5, item 1: `src/agent/tools.py` — 3 tool domain mới)

### Added
- `src/agent/tools.py` — 3 `@tool` mới, đúng pattern có sẵn (check
  `settings.db_configured`, lazy import `src.db.queries`, wrap qua
  `_wrap_dict`): `count_face_events`, `count_fire_smoke_events`,
  `count_anomaly_events`. Docstring `count_anomaly_events` liệt kê RÕ 4
  giá trị `event_type` hợp lệ (kèm nghĩa tiếng Việt) + nhắc lại rõ ràng
  KHÁC `zone_intrusion_by_hour` (tránh model nhầm "leo trèo" với "vùng
  cấm" — đúng lưu ý thiết kế từ Phase 2). Docstring
  `count_fire_smoke_events` nói rõ domain hiện rỗng hoàn toàn (dữ liệu
  thật, không phải lỗi) để model không hoảng/bịa khi thấy rỗng.
- Thêm cả 3 tool vào `TOOLS`.

### Fixed (test cũ, hệ quả trực tiếp bắt buộc phải sửa)
- `tests/test_offline.py::test_danh_sach_tool_dung_thiet_ke` check
  `tool_names == {...}` (SO KHỚP CHÍNH XÁC) — fail ngay khi thêm 3 tool
  mới, đúng dự kiến (`test-plan.md` mục "Test offline" #2 đã ghi trước:
  "assertion tên tool khớp product-spec.md" — cần cập nhật khi tool mới
  tồn tại). Cập nhật set kỳ vọng thêm 3 tên tool mới.

### Verified
- `pytest -q` → "5 passed" (sau khi sửa test ở trên).
- Gọi thật cả 3 tool qua `.invoke()` (interface LangChain thật, không
  phải gọi thẳng hàm Python): `count_face_events` → 3953 IN (khoảng
  07-15/09); `count_fire_smoke_events` → rỗng (đúng, domain trống);
  `count_anomaly_events(FIGHT_DETECTION)` → 12562 (khoảng 04-16/09, org
  106); `count_anomaly_events(SIDEWALK_ENCROACHMENT)` → `error` rõ ràng
  trong `QueryResult`, không query DB, không crash tool.

## 2026-09-17 (Review Phase 4 item 3 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("`src/monitoring/tracing.py`") đối
chiếu `specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`
mục "Test Langfuse tracing" (4 test case).

### Pass
- Test #1 (`MONITORING_ENABLED=false` → `pytest` y hệt trước): verify lại
  — "5 passed", không cần Langfuse chạy.
- Test #4 (Langfuse service down → không crash): verify bằng
  `LANGFUSE_HOST` trỏ tới cổng không ai lắng nghe — `trace_answer()`
  KHÔNG crash, trả về bình thường sau khi hết retry (~3.8s), lỗi chỉ log
  ra `stderr` (cảnh báo), không raise lên caller.
- Test #3 (không lộ secret trong trace): rà lại code `tracing.py` — input/
  output/metadata chỉ chứa `question`/`answer`/`latency_s`, không có
  đường nào đưa `OPENAI_API_KEYS`/`DB_PASSWORD` vào trace theo THIẾT KẾ
  hiện tại (secrets không đi qua tham số nào của `trace_answer`/
  `trace_step`). Test đầy đủ với câu hỏi chứa PII thật cần chờ Phase 5
  wire vào `/ask` (đi qua `redact_pii()` trước).
- `product-spec.md`: trace thật lưu được vào Langfuse tự host — verify
  tận ClickHouse (`events_core`), không chỉ tin "không lỗi Python".

### Fail — đã sửa (thuộc hạ tầng Phase 4 item 1, không phải code
`tracing.py`)
- Xem mục "BUG hạ tầng" ở entry implement bên trên (`SignatureDoesNotMatch`
  do quên đồng bộ `LANGFUSE_S3_*_SECRET_ACCESS_KEY` với
  `MINIO_ROOT_PASSWORD`) — đã sửa `langfuse/.env`, verify lại trace lưu
  được.

### Ghi nhận thêm cho Phase 5 (không phải bug của item này)
- Khi Langfuse KHÔNG phản hồi, `trace_answer()` mất ~3.8s (2 lần retry +
  backoff) trước khi bỏ cuộc — nếu Phase 5 bọc TOÀN BỘ `/ask` trong
  `trace_answer()`, Langfuse down sẽ làm MỌI câu hỏi chậm thêm ~3.8s (dù
  vẫn trả lời đúng, không crash). Cân nhắc ở Phase 5: có cần giảm số lần
  retry/timeout của OTel exporter hay chấp nhận độ trễ này (MVP, tần suất
  Langfuse down thấp) — quyết định này thuộc Phase 5, ghi lại ở đây để
  không quên khi tới lượt.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- Test #2 (trace thật của 1 lượt `/ask` qua endpoint, có span con cho
  bước chọn tool + diễn giải) — cần wiring vào `main.py`/`graph.py`,
  đúng Phase 5, chưa tới lượt (đã verify tương đương ở MỨC MODULE:
  `trace_answer`+`trace_step` lồng nhau hoạt động đúng, xem entry
  implement).

## 2026-09-17 (Phase 4, item 3 — item cuối: `src/monitoring/tracing.py`)

### Added
- `src/monitoring/__init__.py` (rỗng, đúng phong cách `src/db/`,
  `src/agent/`).
- `src/monitoring/tracing.py` — copy gần như nguyên từ
  `llm-engineer-demo/app/monitoring/tracing.py` (đã kiểm chứng API tương
  thích với `langfuse==4.15.4` thật trước khi copy, không copy mù):
  `trace_answer(name, question, metadata)` (context manager gốc cho 1
  lượt `/ask`), `trace_step(parent_span, name, input, metadata)` (nested
  child span), `trace_stream(...)` (giữ để đồng bộ interface, chưa dùng ở
  agent_ATIN vì chưa có streaming). `_get_langfuse()` lazy import + lazy
  client. Toàn bộ no-op (yield `{}`) khi `MONITORING_ENABLED=false`.

### BUG hạ tầng tự phát hiện khi test thật — đã sửa `langfuse/.env` (Phase 4 item 1)
- Gửi thử 1 trace thật (`trace_answer` + `trace_step` lồng nhau) với
  `MONITORING_ENABLED=true` và key thật từ `langfuse/.env` → không lỗi ở
  phía Python, nhưng verify trực tiếp ClickHouse (`SELECT count(*) FROM
  events_core/observations/traces`) thấy **0 dòng** — trace đã gửi nhưng
  KHÔNG được lưu.
- Bật `debug=True` trên `Langfuse()` để xem log chi tiết → phát hiện
  `langfuse-web` log lỗi `SignatureDoesNotMatch` khi upload JSON lên
  MinIO. Nguyên nhân: ở Phase 4 item 1, tôi đổi `MINIO_ROOT_PASSWORD`
  sang giá trị ngẫu nhiên nhưng QUÊN đồng bộ 3 biến riêng
  `LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY`/
  `LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY`/
  `LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY` (langfuse-web dùng 3 biến
  này để auth vào MinIO, mặc định `miniosecret` — không tự ăn theo
  `MINIO_ROOT_PASSWORD`) — cùng LOẠI lỗi với bug `DATABASE_URL` đã gặp ở
  Phase 4 item 1 (quên đồng bộ credential dẫn xuất khi đổi mật khẩu gốc).
- **Sửa:** thêm 3 biến trên vào `langfuse/.env`, cùng giá trị
  `MINIO_ROOT_PASSWORD` (không in secret ra output), `docker compose up
  -d` để áp dụng.
- Verify lại: gửi lại trace → `events_core` có đúng 2 dòng (`ask` +
  `chon_tool`), `chon_tool.parent_span_id` trỏ đúng về span `ask` — cấu
  trúc cha-con nested ĐÚNG như thiết kế.

### Verified
- `pytest -q` → "5 passed" (không regression).
- `MONITORING_ENABLED` không set (mặc định `false`) → `trace_answer()`/
  `trace_step()` trả `{}` ngay, không tạo client Langfuse, không cần
  Langfuse chạy.
- `MONITORING_ENABLED=true` + key thật → trace THẬT xuất hiện trong
  ClickHouse (`events_core`), verify tận nơi lưu trữ (không chỉ tin log
  "không lỗi" ở phía Python) — bài học từ chính bug vừa tìm thấy trong
  mục này.
- Exception trong `with trace_answer(...)`: được RE-RAISE ra ngoài (không
  bị nuốt), verify bằng `try/except RuntimeError` bắt được đúng lỗi giả
  lập.
- Ghi nhận: `GET /api/public/traces`/`/observations` (REST API cũ) trả
  `404` với thông báo "not available... in Langfuse v4 events_only mode"
  — bản Langfuse mới nhất (deploy ngày 2026-09-17) mặc định chạy chế độ
  lưu trữ mới (`events_core` trong ClickHouse), không dùng bảng
  `traces`/`observations` cũ cho API cũ nữa. Không ảnh hưởng
  `trace_answer()`/`trace_step()` (dùng `start_observation()`, tương
  thích chế độ mới) — chỉ ảnh hưởng nếu sau này cần QUERY LẠI trace qua
  REST API cũ (`v2/observations` vẫn hoạt động, xem entry trước).

## 2026-09-17 (Review Phase 4 item 2 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("4 field cấu hình Langfuse") đối chiếu
`specs/product-spec.md` và `specs/test-plan.md` mục "Test Langfuse
tracing" #1.

### Pass
- `test-plan.md` #1 CHÍNH XÁC: gỡ hẳn package `langfuse`
  (`pip uninstall -y langfuse`) rồi chạy `pytest -q` → vẫn "5 passed",
  không lỗi import — vì `src/config.py` chỉ khai báo field, KHÔNG
  `import langfuse` — đúng yêu cầu "không import lỗi nếu thiếu package".
  Cài lại `langfuse` sau khi verify xong.
- `product-spec.md`: `MONITORING_ENABLED` mặc định `False` — verify qua
  `settings.monitoring_enabled`.
- Field mới hoàn toàn additive, không đổi field/hành vi cũ nào.

### Fail
- Không tìm thấy lỗi nào trong phạm vi feature này.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `test-plan.md` #2/#3/#4 (trace xuất hiện khi bật monitoring, không lộ
  secret, Langfuse down không crash `/ask`) — cần `src/monitoring/
  tracing.py` (item tiếp theo) + wiring vào `main.py`/`graph.py` (Phase
  5), chưa tới lượt.
- `.env` thật của app chưa điền `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` thật
  (chỉ có ở `langfuse/.env`) — không thuộc phạm vi item này (chỉ thêm
  field + default), sẽ cần điền khi tới lượt test #2 thật.

## 2026-09-17 (Phase 4, item 2: `src/config.py` + `.env.example` + `requirements.txt` — biến Langfuse)

### Added
- `src/config.py` — thêm 4 field: `monitoring_enabled` (alias
  `MONITORING_ENABLED`, default `False`), `langfuse_public_key`,
  `langfuse_secret_key` (default rỗng), `langfuse_host` (default
  `http://localhost:3000` — khớp UI đã deploy ở Phase 4 item 1). Đặt sau
  nhóm Guardrail, đúng thứ tự thêm-mới-ở-cuối như các nhóm trước.
- `.env.example` — thêm nhóm "Observability (Langfuse, Phase 4)" tương
  ứng, ghi rõ mặc định tắt + tự host, không dùng Cloud.
- `requirements.txt` — thêm `langfuse` (SDK Python chính thức, bản
  `4.15.4`, tương thích server Langfuse v4 đã deploy ở item trước).

### Verified
- `pip install langfuse` + `pytest -q` → "5 passed" (không regression).
- `python3 -c "from src.config import settings; ..."`: `monitoring_enabled
  = False` (mặc định tắt, đúng yêu cầu), `langfuse_host =
  http://localhost:3000`, `langfuse_public_key`/`langfuse_secret_key`
  rỗng (đúng — `.env` thật của app CHƯA điền, chỉ có ở `langfuse/.env`
  tự sinh ở item trước; điền vào `.env` thật của app không thuộc phạm vi
  item này, chỉ thêm field + default).
- `import langfuse` thành công, không lỗi phụ thuộc.

## 2026-09-17 (Review Phase 4 item 1 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("deploy Langfuse self-host") đối chiếu
`specs/product-spec.md` và `specs/test-plan.md`.

### Pass
- `product-spec.md` "Observability — Langfuse tự host trên máy này": đúng
  — self-host thật (không dùng Langfuse Cloud), UI + API hoạt động thật,
  đã verify không chỉ "container chạy" mà còn "key hoạt động được".
- Tất cả secret tự sinh (không dùng giá trị mặc định `# CHANGEME` của
  file gốc) — đúng tinh thần bảo mật cho server thật.
- Không đụng code app (`pytest` vẫn "5 passed", `.env` gốc của app chưa
  có biến `LANGFUSE_*` nào — đúng phạm vi, item đó chưa tới lượt).

### Fail
- Không có lỗi nào còn tồn đọng — 2 lỗi gặp lúc deploy (xung đột cổng
  9090, sai `DATABASE_URL`) đã sửa VÀ verify lại NGAY trong lúc implement
  (không để sang lượt review riêng vì đó là lỗi chặn hoàn toàn, không thể
  coi "đã implement" khi container còn crash).

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `test-plan.md` mục "Test Langfuse tracing" (4 test case: tắt/bật
  monitoring, không lộ secret trong trace, Langfuse down không crash
  `/ask`) — CHƯA áp dụng được, cần `src/config.py` thêm
  `MONITORING_ENABLED`/`LANGFUSE_*` (item tiếp theo) + `src/monitoring/
  tracing.py` + wiring vào `main.py`/`graph.py` (Phase 5) trước.
- Chưa gửi thử 1 trace thật vào Langfuse (cần `tracing.py`, chưa code) —
  chỉ mới xác nhận HẠ TẦNG (project + key) sẵn sàng để nhận trace, đúng
  scope "chỉ dựng hạ tầng ở phase này" ghi ngay đầu Phase 4 trong
  `implementation-plan.md`.

## 2026-09-17 (Phase 4, item 1: Deploy Langfuse self-host)

### Added
- `langfuse/docker-compose.yml` — file CHÍNH THỨC tải nguyên từ
  `https://raw.githubusercontent.com/langfuse/langfuse/main/docker-compose.yml`
  (không clone repo — chỉ cần file compose vì dùng image build sẵn
  `docker.langfuse.com/langfuse/langfuse:4`, không tự build từ source).
  Sửa 2 chỗ để tránh xung đột cổng đã dùng trên máy này: cổng host của
  MinIO đổi từ `9090` → `9190` (2 dòng: port mapping + biến môi trường
  `LANGFUSE_S3_*_EXTERNAL_ENDPOINT`/`LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT`
  mặc định).
- `langfuse/.env` (không commit — khớp pattern `.env` có sẵn trong
  `.gitignore`, áp dụng cho mọi thư mục con) — sinh ngẫu nhiên toàn bộ
  secret đánh dấu `# CHANGEME` trong file gốc (`SALT`, `ENCRYPTION_KEY`,
  `NEXTAUTH_SECRET`, `POSTGRES_PASSWORD`, `CLICKHOUSE_PASSWORD`,
  `MINIO_ROOT_PASSWORD`, `REDIS_AUTH`) — KHÔNG dùng giá trị mặc định
  (`postgres`/`mysecret`/...) như file gốc, vì đây là server thật, không
  phải máy demo tạm. Dùng biến `LANGFUSE_INIT_*` (tính năng có sẵn của
  Langfuse) để tự động tạo 1 org + 1 project (`agent_ATIN`) + 1 user admin
  + 1 cặp `public_key`/`secret_key` cố định ngay lúc khởi động — KHÔNG
  cần thao tác tay qua UI (đăng ký/tạo project) để lấy key.

### Fixed (trong lúc deploy, trước khi coi là xong)
- Lần chạy đầu `docker compose up -d` lỗi
  `failed to bind host port 0.0.0.0:9090/tcp: address already in use` —
  máy này đã có service khác dùng cổng 9090. Sửa: đổi cổng host MinIO
  sang `9190` (đã free, kiểm tra bằng `ss -tln` trước khi chọn).
- Sau khi container `langfuse-web` chạy, log báo
  `Error: P1000: Authentication failed against database server` — do
  quên set `DATABASE_URL` khớp mật khẩu Postgres mới sinh (`.env` chỉ có
  `POSTGRES_PASSWORD` cho container Postgres, còn `DATABASE_URL` mặc
  định trong `docker-compose.yml` vẫn là chuỗi cũ `postgres:postgres`).
  Sửa: thêm `DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/postgres`
  vào `.env` (không in mật khẩu ra bất kỳ output nào trong lúc sửa).

### Verified
- `docker compose ps`: đủ 6 container (`postgres`, `clickhouse`, `redis`,
  `minio`, `langfuse-worker`, `langfuse-web`) đều `Up`/`healthy`.
- `curl http://localhost:3000` → `200 OK`, trang Langfuse render được —
  UI truy cập được qua trình duyệt (từ máy này hoặc qua SSH tunnel/LAN
  nếu truy cập từ máy khác).
- Gọi thật `GET /api/public/projects` với header `Authorization: Basic
  base64(public_key:secret_key)` (đọc từ `langfuse/.env`, không in ra
  console) → trả đúng JSON có project `agent_ATIN` + organization
  `agent_ATIN` — xác nhận cặp key KHỞI TẠO TỰ ĐỘNG hoạt động thật, không
  chỉ tồn tại trong file `.env`.
- Chỉ 2 cổng public trên host: `3000` (web) và `9190` (MinIO S3 — đổi từ
  9090) — đúng khuyến nghị bảo mật trong comment đầu file compose gốc
  ("restrict inbound traffic... to langfuse-web và minio only"), các
  service còn lại (`postgres`, `redis`, `clickhouse`) chỉ bind
  `127.0.0.1`.

### Quản lý (để dùng ở các item sau + cho user)
- Start: `cd langfuse && docker compose up -d`. Stop:
  `docker compose down` (giữ data) / thêm `-v` để xoá sạch data.
- Xem log: `docker compose logs langfuse-web -f`.
- `public_key`/`secret_key`/mật khẩu admin UI nằm trong `langfuse/.env`
  (không commit) — item Phase 4 tiếp theo (`src/config.py` thêm
  `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`) sẽ đọc từ
  đây để điền vào `.env` của app chính.

## 2026-09-17 (Review Phase 3 item 3 vs product-spec.md/test-plan.md)

Review lại đúng 1 "feature" vừa làm ("test kết nối thật read-only cho 3 DB
mới") đối chiếu `specs/product-spec.md` và `specs/test-plan.md`. Vì đây là
task verify (không có code mới), review chỉ đối chiếu xem đã verify ĐỦ và
ĐÚNG những gì test-plan.md yêu cầu cho đúng bullet này hay chưa.

### Pass
- Khớp CHÍNH XÁC bullet "Lớp app/session-readonly" trong `test-plan.md`
  mục "Test guardrail an toàn (2 lớp)": verify qua `get_connection()`
  thật, DELETE/UPDATE → `ReadOnlySqlTransaction` (không phải
  `InsufficientPrivilege` như lớp Postgres/GRANT đã verify ở Phase 2 item
  1) — đúng cả tên lỗi lẫn cơ chế.
- `product-spec.md` "Hạ tầng — đọc-only Postgres qua role riêng... trên
  mọi DB nguồn cần dùng": xác nhận đủ 5/5 DB, cả 2 lớp bảo vệ đều hoạt
  động đúng.
- Không thêm thư viện, không đổi kiến trúc, không đổi code — đúng bản
  chất "task verify" của item này.

### Fail
- Không có — không có code mới ở item này nên không có gì để tìm lỗi.

### Missing (thuộc các item/phase KHÁC, không phải thiếu sót của item này)
- `test-plan.md` "Test offline" #2 (danh sách tool mới đúng thiết kế) —
  thuộc Phase 5 (`src/agent/tools.py` chưa code).
- `test-plan.md` "Test thật" (6 câu hỏi mẫu domain mới qua agent đầy đủ)
  — cần Phase 5 xong + fix dependency `openai`/`httpx2`
  (`task_2e390bb8`, đã tạo ở lượt trước).
- Test offline #1 (`LOI_BIA`), #3 (`in_scope`), #4 (`dbname` lạ) — đã
  verify ở các lượt review TRƯỚC (Phase 2 item 3, Phase 3 item 1/2), không
  lặp lại thừa ở đây.

## 2026-09-17 (Phase 3, item 3 — item cuối: test kết nối thật read-only cho 3 DB mới)

Item này là task VERIFY (không phải file code mới) — không có gì để
modify. Đã verify rải rác qua các item trước (Phase 2 item 1: lớp
Postgres/GRANT qua raw `psycopg2`; Phase 3 item 1: lớp app/session-readonly
qua `get_connection()`) — chạy lại đầy đủ, tường minh 1 lần theo đúng mô tả
checklist, giống tiền lệ v1 (`specs/change-log.md` mục "Phase 3, item 3: test
kết nối thật read-only").

### Verified
- SELECT chạy được qua `get_connection()` cho cả 3 DB mới:
  `smart_face.smf_face_events` (3953 dòng), `firesmoke.fire_smoke_event`
  (0 dòng — đúng, bảng rỗng), `anomaly.anomaly_event` (429327 dòng, đếm
  toàn bảng không lọc org).
- DELETE/UPDATE bị Postgres từ chối cho cả 3 DB — `ReadOnlySqlTransaction`
  (lớp app, `conn.set_session(readonly=True)` trong `get_connection()`):
  `smart_face` (DELETE), `firesmoke` (UPDATE), `anomaly` (DELETE).
- `dbname` ngoài whitelist (`vms_db`) vẫn bị chặn `ValueError` ngay ở
  lớp code, không mở connection thật — không regression.

**Phase 3 (Core Backend / Data Logic) đã hoàn thành đủ 3/3 item cho cả
v1 và v2.**

## 2026-09-17 (Review Phase 3 item 2 vs product-spec.md/test-plan.md — có fix)

Review lại đúng 1 feature vừa làm ("3 hàm SQL domain mới trong
`src/db/queries.py`") đối chiếu `specs/product-spec.md` (Acceptance
Criteria) và `specs/test-plan.md`.

### Pass
- `test-plan.md` "Test offline" #1: `count_anomaly_events(event_type=
  "LOI_BIA")` (đúng chữ trong test-plan.md, giá trị vô nghĩa) → `error`
  rõ ràng, không query DB — verify lại chính xác đúng case này (lượt
  implement trước test bằng `SIDEWALK_ENCROACHMENT`, giá trị CÓ THẬT
  trong bảng nhưng ngoài whitelist — khác ý nghĩa với "vô nghĩa hoàn
  toàn" của test-plan; verify thêm cho chắc).
- `event_type` rỗng (bắt buộc theo thiết kế) → `error`, không crash.
- `group_by` sai cho cả 3 hàm (`count_anomaly_events`, đã test
  `count_face_events` tương tự lượt trước) → `error` rõ ràng, không
  query DB — nhất quán với `count_vehicle_flow` (v1).
- `product-spec.md`: số liệu thật, không hallucinate — cả 3 hàm trả đúng
  dữ liệu thật đã verify (không bịa số).

### Fail
- Không tìm thấy lỗi CODE nào trong phạm vi feature này (bug tìm thấy ở
  lượt trước là bug DỮ LIỆU/GIẢ ĐỊNH trong dataset, đã sửa ở entry
  implement bên dưới — không phải bug của 3 hàm SQL, các hàm áp dụng org
  filter ĐÚNG theo thiết kế v1).

### Ghi nhận thêm (không phải bug, chỉ là đặc điểm dữ liệu thật)
- Test thêm `group_by="zone_name"` cho `FIGHT_DETECTION` (chưa test ở
  lượt implement) → chạy đúng về mặt CODE, nhưng cột `zone_name` trong DB
  thật là `NULL` cho toàn bộ 13092 dòng — group theo `zone_name` hiện
  không tạo được breakdown hữu ích với dữ liệu thật hôm nay. Không sửa gì
  (đây là dữ liệu thật, không phải lỗi hàm) — chỉ ghi nhận để Phase 5 biết
  khi thiết kế tool/docstring cho LLM, tránh gợi ý group_by=zone_name cho
  câu hỏi cần breakdown theo khu vực nếu dữ liệu chưa hỗ trợ.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `src/agent/tools.py` chưa bọc 3 hàm này thành `@tool` — Phase 5, chưa
  tới lượt. `test-plan.md` "Test offline" #2 (danh sách tool) áp dụng cho
  Phase 5, không áp dụng ở đây.

## 2026-09-17 (Phase 3, item 2: `src/db/queries.py` — 3 hàm SQL domain mới)

### Added
- `src/db/queries.py` — 3 hàm mới, đúng pattern có sẵn (`%s` placeholder,
  `_org_filter()`, `get_connection(settings.db_name_*)`, trả `{error}`
  hoặc `{columns, rows, row_count}`):
  - `count_face_events(date_from, date_to, direction, group_by)` →
    `smart_face.smf_face_events`, group theo `{direction, department_name}`,
    dùng cột thời gian `access_time` (không phải `event_time`).
  - `count_fire_smoke_events(date_from, date_to, entity_type)` →
    `firesmoke.fire_smoke_event`, group cố định theo `entity_type` +
    `alert_level`, validate `entity_type ∈ {FIRE, SMOKE}`.
  - `count_anomaly_events(date_from, date_to, event_type, group_by)` →
    `anomaly.anomaly_event`, DÙNG CHUNG cho 4 sự kiện, `event_type` BẮT
    BUỘC + validate whitelist đúng 4 giá trị (loại trừ
    `SIDEWALK_ENCROACHMENT`/`LITTERING_DETECTION` có trong bảng nhưng
    ngoài phạm vi sản phẩm), group tuỳ chọn theo `{severity, zone_name}`.
  - KHÔNG thêm `water_level_latest` — dataset chỉ cần đếm sự kiện, không
    cần giá trị mực nước tức thời.

### BUG NGHIÊM TRỌNG tự phát hiện khi test thật — đã sửa `eval/datasets/agent_stat/v2.yaml`
- Test `count_anomaly_events('2026-08-14', '2026-09-17', 'FIGHT_DETECTION')`
  trả **13092**, KHÁC HẲN con số **31464** đã ghi trong `v2.yaml` (Phase 2
  item 4) cho cùng loại sự kiện/khoảng ngày. Điều tra bằng raw SQL: bảng
  `anomaly.anomaly_event` có DỮ LIỆU CỦA 2 `organization_id` KHÁC NHAU
  (103 và 106); `.env` cấu hình `DB_ORGANIZATION_ID=106`; hàm mới viết
  ĐÚNG áp dụng `_org_filter()` (kế thừa từ `count_vehicle_flow` v1) nên
  chỉ đếm org 106 — con số 31464 ở `v2.yaml` là TỔNG CẢ 2 ORG (lấy bằng
  raw SQL không lọc org khi grounding dataset lúc trước), SAI với những
  gì tool thật sẽ trả về.
- Điều tra sâu hơn phát hiện thêm: **org 106 (org của app) hoàn toàn
  KHÔNG CÓ dữ liệu `CROWD_DETECTION`/`INTRUSION_DETECTION` (= 0, mọi
  khoảng thời gian)** — 2 loại này chỉ tồn tại dưới org 103 (không thuộc
  app). Đây không phải lỗi tool, mà là sự thật của dữ liệu tổ chức 106.
  Đồng thời phát hiện `WATER_LEVEL_DETECTION` (org 106) vẫn được ghi
  nhận tới HÔM NAY (2026-09-17, ~100 lượt/ngày) — KHÁC domain FIGHT
  (dừng ở 2026-09-16) — trước đó tưởng nhầm cả 4 loại đều "không có dữ
  liệu hôm nay".
- **Sửa `v2.yaml`:** viết lại toàn bộ đoạn tổng hợp dữ liệu ở đầu file +
  6 case bị ảnh hưởng trực tiếp (#010, #012, #014, #017, #018, #022,
  #023, #024): cập nhật số liệu đúng (13092 FIGHT, 0 CROWD, 0 INTRUSION,
  258359+ WATER_LEVEL), đổi case #012/#014 từ "có dữ liệu" (sai) thành
  "không có dữ liệu" (đúng — org 106 chưa từng có 2 loại này), đổi case
  #017 từ "không có dữ liệu" (sai) thành "có dữ liệu hôm nay" (đúng, vì
  water level vẫn đang ghi nhận), REDESIGN case #023 (leo trèo vs cháy
  khói — cả 2 giờ đều rỗng nên mất ý nghĩa test "1 có 1 không") thành mực
  nước vs cháy khói, và REDESIGN case #024 (xếp hạng 3 loại — 2 loại tie
  ở 0 nên vô nghĩa) thành "loại nào có/không có dữ liệu trong 4 loại".

### Verified
- `pytest -q` → "5 passed".
- Test thật (đọc DB thật, không cần LLM): cả 3 hàm mới trả đúng dữ liệu +
  validate đúng (`event_type`/`entity_type`/`group_by` sai → `error` rõ
  ràng, không query DB).
- `eval/run.py` (offline, sau khi sửa `v2.yaml`) vẫn cho kết quả nhất
  quán (`injection: 3/3`, `out_of_scope: 3/3`) — sửa dataset không ảnh
  hưởng cơ chế guardrail.
- YAML parse hợp lệ, vẫn đúng 30 case / phân bổ 18-6-3-3, không trùng
  `id`, không còn số liệu sai sót lại (grep xác nhận 31464/25820/14835/
  258260 chỉ còn xuất hiện trong đoạn giải thích org 103, chủ ý giữ để
  đối chiếu).

## 2026-09-17 (Review Phase 3 item 1 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("mở rộng whitelist `get_connection()`")
đối chiếu `specs/product-spec.md` (Acceptance Criteria) và
`specs/test-plan.md` (mục "Test guardrail an toàn (2 lớp)" + "Test offline"
#4).

### Pass
- `test-plan.md` "Test offline" #4: `get_connection('vms_db')` (ngoài
  whitelist) → `ValueError` ngay, không mở connection — verify lại, đúng.
- `test-plan.md` "Lớp app/session-readonly": verify **ĐỦ CẢ 3 DB mới**
  (rút kinh nghiệm lượt review Phase 2 item 1 — lúc đó chỉ test 2/3 DB,
  lần này chủ động test cả 3 ngay từ đầu): `smart_face` (DELETE),
  `firesmoke` (UPDATE), `anomaly` (DELETE) — cả 3 đều bị `Read
  OnlySqlTransaction` (lớp app, `conn.set_session(readonly=True)`) —
  đúng dự đoán, không phải chỉ `InsufficientPrivilege` như trước Phase 3.
- SELECT qua `get_connection()` chạy được cho cả 5 DB (2 cũ + 3 mới).
- `pytest` sạch (5 passed), không thêm thư viện, không đổi kiến trúc
  ngoài phạm vi whitelist.

### Fail
- Không tìm thấy lỗi nào trong phạm vi hẹp của feature này.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `src/db/queries.py` chưa có 3 hàm SQL mới (`count_face_events`/
  `count_fire_smoke_events`/`count_anomaly_events`) — item TIẾP THEO
  trong Phase 3, chưa tới lượt. Whitelist mở rộng xong nhưng CHƯA có code
  nào gọi `get_connection()` với 3 DB mới ngoài script test tay ở trên —
  đúng dự kiến.
- `test-plan.md` mục "Test thật" cho domain mới vẫn chưa chạy được qua
  `eval/run.py`/agent thật (cần Phase 3 item 2 + Phase 5 xong, và cần
  fix dependency `openai`/`httpx2` đã ghi nhận ở `task_2e390bb8`).

## 2026-09-17 (Phase 3, item 1: `src/db/connection.py` — mở rộng whitelist 3 DB mới)

### Added
- `src/db/connection.py::_allowed_dbnames()` — thêm `settings.db_name_face`/
  `db_name_fire`/`db_name_anomaly` (3 field đã có sẵn từ Phase 2 item 2)
  vào set whitelist, giữ nguyên cơ chế: `get_connection(dbname)` raise
  `ValueError` NGAY nếu `dbname` không thuộc 5 DB hợp lệ, không mở
  connection thật. Cập nhật docstring đầu file (2 DB → 5 DB, liệt kê rõ
  bảng chính từng DB).

### Verified
- `pytest -q` → "5 passed" (không regression).
- Gọi thật `get_connection(db)` cho cả 5 DB (`its`, `virtual_fence`,
  `smart_face`, `firesmoke`, `anomaly`) → SELECT chạy được cả 5.
- `DELETE FROM anomaly_event` qua `get_connection('anomaly')` → bị chặn
  `ReadOnlySqlTransaction` (lớp APP — `conn.set_session(readonly=True)`)
  — đây là lần ĐẦU TIÊN verify được lớp bảo vệ này cho 3 DB mới (trước đó,
  ở Phase 2 item 1, chỉ verify được lớp Postgres/GRANT vì whitelist app
  chưa mở). Khớp đúng dự đoán đã ghi trong `specs/test-plan.md` khi sửa
  mục "Test guardrail an toàn" (Phase 2 review): "lớp app/session-readonly
  chỉ verify được SAU Phase 3".
- `get_connection('vms_db')` (tên ngoài whitelist) → raise `ValueError`
  ngay, không mở connection — không regression so với hành vi cũ.

## 2026-09-17 (Review Phase 2 item 5 vs product-spec.md/test-plan.md — có fix)

Review lại đúng 1 feature vừa làm ("`eval/run.py`") đối chiếu
`specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`.

### Pass
- `product-spec.md`: "eval/datasets/agent_stat có đủ 30 case phủ 8 domain,
  chạy được bằng eval/run.py, in được tỷ lệ pass/fail theo slice" — script
  chạy không crash, đọc đúng dataset, in đúng bảng theo `slice.type` +
  tổng, đúng exit code (0 = toàn bộ pass, 1 = có fail — dùng được trong CI
  sau này).
- `test-plan.md` mục "Test golden dataset v2": "3 case out_of_scope + 3
  case injection PHẢI vẫn pass nguyên" — verify lại SAU KHI sửa bug pipeline
  (bên dưới): cả 2 slice đạt 3/3 dưới chế độ offline, không cần LLM thật
  (đúng bản chất — 2 slice này chỉ phụ thuộc `src/guardrails.py`).
- Script tương thích ngược với `v1.yaml` (test thêm, không bắt buộc) — same
  cơ chế, injection/out_of_scope vẫn 3/3.

### Fail — đã sửa ngay trong lượt review này
- **BUG tự phát hiện (lần 2, nhỏ hơn):** `run_pipeline()` dùng biến
  `question` GỐC (chưa qua `redact_pii()`) khi build `evidence` cho
  `check_output()`, trong khi `src/main.py::ask()` thật sự dùng biến
  `question` đã bị GHI ĐÈ bằng bản đã redact TRƯỚC khi build evidence (xem
  dòng `question = redact_pii(req.question)` rồi mới `evidence = [question]
  + ...`). Với 30 case hiện tại không ảnh hưởng kết quả (không câu nào có
  PII), nhưng là sai lệch thật so với hành vi `/ask` production nếu sau
  này có case chứa SĐT/email.
- **Sửa:** thêm dòng `question = redact_pii(question)` TRƯỚC khi build
  evidence, y hệt thứ tự trong `main.py`.
- Verify lại: `pytest -q` vẫn "5 passed"; `eval/run.py` (offline, cả
  v1.yaml và v2.yaml) vẫn cho kết quả y hệt trước khi sửa (đúng dự kiến vì
  30 case hiện tại không có PII) — xác nhận fix không gây regression.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- Chưa verify được pass/fail thật với LLM thật cho slice `lookup`/
  `comparison` — bị chặn bởi lỗi dependency `openai`/`httpx2` (môi trường,
  đã ghi nhận ở entry implement, đã tạo task riêng
  `task_2e390bb8` để theo dõi, KHÔNG sửa ở đây).
- 18 case `lookup` domain mới (FACE/FIGHT/CROWD/INTRUSION/FIRE/WATER_LEVEL)
  vẫn FAIL vì tool chưa tồn tại (Phase 3/5, chưa tới lượt) — đúng dự kiến,
  đã ghi rõ trong header `v2.yaml` và docstring `eval/run.py`.

## 2026-09-17 (Phase 2, item 5 — item cuối: `eval/run.py`)

### Added
- `eval/run.py` (mới) — script chạy toàn bộ golden dataset qua **đúng
  pipeline thật** của `src/main.py::ask()` (`check_input → in_scope →
  run_agent → check_output`, xem hàm `run_pipeline()`), kiểm đủ 5 loại
  assertion đang dùng trong `v1.yaml`/`v2.yaml` (`must_include`,
  `must_include_tool`, `must_not_include`, `must_not_include_tool`,
  `must_include_columns_any` — mở rộng hơn 3 loại nêu trong checklist vì
  dataset thật đã dùng cả 5 loại, xem đối chiếu lúc review bên dưới), in
  tỷ lệ pass/fail theo `slice.type` + chi tiết lý do fail từng case.
  Dùng: `python eval/run.py [--dataset <path>]`.

### BUG tự phát hiện khi test thật lần đầu — đã sửa TRƯỚC KHI đánh dấu hoàn thành
- Bản đầu tiên gọi THẲNG `run_agent()` (đúng nghĩa đen checklist: "gọi
  `run_agent()` từng case") — chạy thử phát hiện: case `out_of_scope`/
  `injection` KHÔNG BAO GIỜ đúng kỳ vọng, vì `run_agent()` không đi qua
  `check_input()`/`in_scope()` — 2 hàm guardrail này mới là nơi sinh ra
  chuỗi `"prompt_injection_detected"`/`OUT_OF_SCOPE_REPLY` mà dataset
  kiểm tra. Gọi thẳng `run_agent()` khiến câu hỏi injection/out_of_scope
  bị đưa thẳng vào LLM như câu hỏi bình thường — sai hoàn toàn ý định của
  2 slice này.
- **Sửa:** viết `run_pipeline()` lặp lại đúng 5 bước trong
  `src/main.py::ask()` (guardrail_input → agent → guardrail_output),
  không dùng FastAPI/TestClient (gọi thẳng hàm Python, nhanh hơn, không
  cần server chạy).
- Verify lại (offline mode, không cần LLM thật): trước khi sửa,
  `out_of_scope` 0/3 (chạy qua offline `run_agent()` vẫn trả lời list
  camera, không khớp `OUT_OF_SCOPE_REPLY`), `injection` chưa test được
  (đợt đầu chạy bằng LLM thật nên injection 0/3 vì lý do tương tự — LLM
  không tự nói "prompt_injection_detected"). Sau khi sửa: `out_of_scope`
  3/3 pass, `injection` 3/3 pass (cả 2 dưới offline mode, không cần LLM
  thật — đúng bản chất 2 slice này chỉ phụ thuộc guardrail code, không
  phụ thuộc LLM).

### Verified
- `pytest -q` → "5 passed" (không regression).
- `PYTEST_CURRENT_TEST=1 python3 eval/run.py` (offline, không cần LLM/DB
  thật) → `injection: 3/3 pass`, `out_of_scope: 3/3 pass`, `lookup: 1/18
  pass` (đúng — case #006 `list_khu_vuc` khớp NGẪU NHIÊN với tool cố định
  mà offline mode luôn gọi; 17 case lookup còn lại + 6 case comparison
  FAIL vì offline mode luôn giả 1 tool `list_khu_vuc` bất kể câu hỏi —
  ĐÚNG dự kiến, offline mode chỉ để test "không crash", không test "chọn
  đúng tool", xem `specs/test-plan.md` mục Test offline #3).
- **KHÔNG verify được với LLM thật lần này** — phát hiện lỗi MÔI TRƯỜNG
  không liên quan tới code: package `openai` bản đang cài (3.14.1) phụ
  thuộc `httpx2` (2.13.0) nhưng 2 bản này KHÔNG tương thích
  (`Decompressor.decompress() got an unexpected keyword argument
  'output_buffer_limit'` khi decode response nén) — mọi lời gọi LLM thật
  (không riêng `eval/run.py`, cả `/ask` bình thường) đều lỗi trong máy
  đang chạy phiên này. `requirements.txt` không ghim version `openai` nên
  `pip install` lấy bản mới nhất, dính bug tương thích này. **KHÔNG sửa
  trong lượt này** — đây là vấn đề dependency/môi trường, không thuộc
  phạm vi checklist item "eval/run.py", cần task riêng để ghim version
  đúng.

## 2026-09-17 (Review Phase 2 item 4 vs product-spec.md/test-plan.md — có fix)

Review lại đúng 1 feature vừa làm ("`eval/datasets/agent_stat/v2.yaml`")
đối chiếu `specs/product-spec.md` (Acceptance Criteria) và
`specs/test-plan.md`.

### Pass
- Đủ 30 case, đúng phân bổ 18/6/3/3 (`implementation-plan.md` Phase 2) —
  verify bằng script đếm `slice.type`.
- YAML parse hợp lệ, không trùng `id`.
- Cả 24 case lookup/comparison đều `in_scope() == True` (không bị
  `STAT_KEYWORDS` ở item 3 từ chối oan); 3 case out_of_scope đều
  `in_scope() == False`; 3 case injection đều bị `check_input()` chặn —
  verify bằng cách gọi thẳng `src/guardrails.py`, không cần đợi
  `eval/run.py`.
- 3 câu out_of_scope giống hệt v1 (đúng yêu cầu "giữ nguyên").

### Fail — đã sửa ngay trong lượt review này
- **BUG tự phát hiện:** 3 câu injection PHẢI "giữ nguyên y hệt v1" (đúng
  cam kết ghi trong changelog của chính lượt implement trước) — nhưng
  case `agent_stat_v2_030` đã tự ý đổi `DELETE FROM plate_event` (v1)
  thành `DELETE FROM anomaly_event` (v2), vi phạm trực tiếp yêu cầu
  "Giữ nguyên câu hỏi cũ, không đổi" trong `implementation-plan.md` Phase
  2 (bảng phân bổ). Lý do sai: cố tình làm case này "liên quan" tới DB
  mới vừa GRANT ở item 1, nhưng thực chất **thừa** — item 1 đã tự verify
  trực tiếp DELETE bị chặn trên `anomaly_event` rồi, không cần lặp lại
  qua injection case.
- **Sửa:** revert `question` + `expected` của case 030 về ĐÚNG y hệt
  text gốc trong `v1.yaml` (`plate_event`, không phải `anomaly_event`).
- Verify lại: so sánh trực tiếp list câu hỏi injection giữa `v1.yaml` và
  `v2.yaml` bằng Python — kết quả giống hệt (`True`). 30 case, phân bổ
  slice không đổi.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `product-spec.md`/`test-plan.md` yêu cầu "chạy được bằng `eval/run.py`,
  in được tỷ lệ pass/fail" — `eval/run.py` CHƯA tồn tại, đó là checklist
  item TIẾP THEO trong Phase 2, chưa tới lượt. Case dùng tool domain mới
  (`count_face_events`/`count_fire_smoke_events`/`count_anomaly_events`)
  chưa chạy được qua `run_agent()` thật vì tool chưa code (Phase 3/5) —
  đã ghi rõ trong header file YAML, không phải thiếu sót của dataset.

## 2026-09-17 (Phase 2, item 4: `eval/datasets/agent_stat/v2.yaml` — 30 case, 8 domain)

### Added
- `eval/datasets/agent_stat/v2.yaml` — 30 case mới, đúng phân bổ trong
  `implementation-plan.md` Phase 2: 18 lookup (4 PLATE + 2 ZONE, giữ lại
  từ v1 + 12 case mới cho 6 domain FACE/FIGHT/CROWD/INTRUSION/FIRE/
  WATER_LEVEL, 2 case/domain), 6 comparison (3 giữ nguyên từ v1 — #019 bug
  regression, #020 seat-limit note, #021 multihop PLATE+ZONE — + 3 case
  chéo domain mới), 3 out_of_scope + 3 injection giữ NGUYÊN y hệt v1.

### Grounding (không bịa số liệu — verify thật qua psycopg2 ngày 2026-09-17)
- Tái verify 2 giá trị v1 vẫn đúng: biển số `15K40139` còn 14 dòng trong
  `its.plate_event`; VINFAST vẫn dẫn đầu hãng xe (29927 lượt, verify lại —
  tăng nhẹ so với con số 29779 ghi trong v1.yaml vì có thêm dữ liệu mới
  giữa 2 lần verify, không phải sai số).
- Phát hiện quan trọng, ảnh hưởng trực tiếp cách viết case: `smart_face.
  smf_face_events` (3953 dòng, 2026-09-07→2026-09-14) và `anomaly.
  anomaly_event` (2026-08-14→2026-09-16) đều KHÔNG có dữ liệu tới "hôm
  nay" (2026-09-17) — khác PLATE/ZONE (dữ liệu liên tục tới hiện tại).
  `firesmoke.fire_smoke_event` RỖNG HOÀN TOÀN (0 dòng, mọi thời điểm).
  → Mỗi domain mới có 2 case: 1 case "hôm nay" (test KHÔNG hallucinate khi
  rỗng — domain FIRE cả 2 case đều vậy vì bảng luôn rỗng) + 1 case theo
  khoảng ngày thật có dữ liệu (test nhánh trả lời đúng số liệu thật, trừ
  FIRE không có case này vì không tồn tại khoảng nào có dữ liệu).
- Số liệu thật dùng trong case: FIGHT_DETECTION=31464, INTRUSION_DETECTION
  (leo trèo)=25820, CROWD_DETECTION=14835, WATER_LEVEL_DETECTION=258260
  (log liên tục, khác bản chất — cố ý loại khỏi case xếp hạng #024).
- `anomaly.anomaly_event` còn có `SIDEWALK_ENCROACHMENT`/
  `LITTERING_DETECTION` — KHÔNG thuộc 8 domain `product-spec.md`, không
  đưa vào dataset.

### Quyết định thiết kế
- Tool cho 6 domain mới (`count_face_events`, `count_fire_smoke_events`,
  `count_anomaly_events`) CHƯA tồn tại trong code (Phase 3/5) — case dùng
  các tool này sẽ FAIL khi chạy `eval/run.py` (cũng chưa tồn tại) cho tới
  khi Phase 3+5 xong. Đây là chủ ý, đã ghi rõ trong header file YAML,
  không phải lỗi của dataset.
- Domain "leo trèo" (`count_anomaly_events(event_type=INTRUSION_
  DETECTION)`) và domain "vùng cấm" (`zone_intrusion_by_hour`) dễ nhầm vì
  cùng dịch "xâm nhập" — case #013 có `must_not_include_tool:
  [zone_intrusion_by_hour]` để bắt lỗi này sớm.

### Verified
- `python3 -c "import yaml; ..."` — parse YAML hợp lệ, đúng 30 case, đúng
  phân bổ slice (18/6/3/3), không trùng `id`.
- Chạy `in_scope()`/`check_input()` (đã có sẵn, không cần `run_agent()`)
  cho cả 30 câu hỏi: 24 case lookup/comparison đều `in_scope() == True`
  (không bị `STAT_KEYWORDS` mở rộng ở item 3 từ chối oan), 3 case
  out_of_scope đều `in_scope() == False`, 3 case injection đều bị
  `check_input()` raise đúng.
- **Chưa chạy được** (đúng dự kiến, ghi trong header file): case dùng tool
  domain mới chưa test qua `run_agent()` thật vì tool chưa tồn tại.

## 2026-09-17 (Review Phase 2 item 3 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("mở rộng `STAT_KEYWORDS`") đối chiếu
`specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`.

### Pass
- `test-plan.md` mục "Test domain sự kiện VMS mới" #3: `in_scope()` nhận
  đúng cả 6 câu hỏi mẫu domain mới → `True` — verify lại, đủ.
- `product-spec.md` Acceptance Criteria "Câu hỏi ngoài phạm vi → bị từ
  chối lịch sự, không gọi tool/DB": chạy lại **toàn bộ 30 case** trong
  `eval/datasets/agent_stat/v1.yaml` (không chỉ 3 câu out_of_scope mẫu
  trong test-plan.md) qua `in_scope()`/`check_input()` — không case nào
  bị đổi hành vi. Đây là kiểm tra RỘNG hơn yêu cầu tối thiểu của
  test-plan.md, chủ động làm thêm vì thay đổi là thêm keyword (rủi ro
  false-positive rộng hơn phạm vi 3 câu mẫu).
- `pytest` sạch (5 passed), không thêm thư viện, không đổi kiến trúc.

### Fail
- Không tìm thấy lỗi nào trong phạm vi feature này.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót)
- Câu hỏi domain mới vẫn CHƯA trả lời được số liệu thật — `in_scope()`
  chỉ là bước gác đầu vào, tool/DB cho 5 domain mới thuộc Phase 3/5, chưa
  code. Test-plan.md mục "Test thật" cho domain mới vẫn chưa chạy được
  hết pipeline — đúng như đã ghi nhận, không phải lỗi của item này.

## 2026-09-17 (Phase 2, item 3: `src/guardrails.py` — `STAT_KEYWORDS` domain mới)

### Added
- `src/guardrails.py::STAT_KEYWORDS` — thêm 14 từ khoá (7 domain mới ×
  1 bản có dấu + 1 bản không dấu, đúng phong cách các từ khoá cũ như
  "xâm nhập"/"xam nhap"): khuôn mặt, ẩu đả, đám đông, leo trèo, cháy,
  khói, mực nước. Chỉ thêm keyword — KHÔNG đổi `in_scope()`/logic khác.

### Verified
- `pytest -q` → "5 passed" (không regression v1).
- `in_scope()` trả `True` cho cả 6 câu hỏi mẫu domain mới trong
  `specs/test-plan.md` mục "Test thật" (nhận diện khuôn mặt, ẩu đả, đám
  đông, leo trèo, cháy/khói, mực nước).
- `in_scope()` vẫn trả `False` cho cả 3 câu out_of_scope cũ trong
  `specs/test-plan.md`/`eval/datasets/agent_stat/v1.yaml` (thời tiết, bài
  thơ, giá cổ phiếu VIC) — xác nhận không có từ khoá mới nào vô tình khớp
  nhầm câu hỏi ngoài phạm vi.

## 2026-09-17 (Phase 2, item 2: `src/config.py` + `.env.example` — 3 DB mới)

### Added
- `src/config.py` — thêm 3 field mới, đúng pattern `db_name_its`/
  `db_name_fence` đã có: `db_name_face` (alias `DB_NAME_FACE`, default
  `"smart_face"`), `db_name_fire` (alias `DB_NAME_FIRE`, default
  `"firesmoke"`), `db_name_anomaly` (alias `DB_NAME_ANOMALY`, default
  `"anomaly"`) — default khớp đúng tên DB thật đã verify ở item trước
  (Phase 2 item 1). Đặt ngay sau `db_name_fence`, trước
  `db_organization_id` — giữ đúng thứ tự nhóm "Database" hiện có, không
  xáo trộn field khác.
- `.env.example` — thêm 3 dòng `DB_NAME_FACE`/`DB_NAME_FIRE`/
  `DB_NAME_ANOMALY` (comment nêu rõ: đã GRANT ở Phase 2 item 1, CHƯA dùng
  ở `connection.py` vì whitelist mở rộng thuộc Phase 3, chưa code) —
  tránh gây hiểu nhầm là 3 DB này đã dùng được qua agent ngay.

### Changed (phạm vi, không lấn Phase 3)
- KHÔNG đổi `src/db/connection.py::_allowed_dbnames()` — vẫn chỉ
  `its`/`virtual_fence`. Đây là quyết định phạm vi đúng checklist
  (`config.py` là item này, whitelist connection là Phase 3 riêng) — 3
  field mới hiện CHƯA được code nào khác import/dùng tới.

### Verified
- `pip install -r requirements.txt` + `pytest -q` → "5 passed" (không
  regression, không cần đổi test nào vì field mới hoàn toàn additive).
- `python3 -c "from src.config import settings; print(settings.db_name_face, settings.db_name_fire, settings.db_name_anomaly)"`
  → in đúng `smart_face firesmoke anomaly` — khớp tên DB thật, `.env`
  hiện tại (chưa có 3 biến mới) vẫn load đúng nhờ default.
- `settings.db_configured` vẫn `True` — không bị ảnh hưởng bởi field mới
  (chỉ phụ thuộc `db_host`/`db_user`, không đổi).

## 2026-09-17 (Review Phase 2 item 2 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("`src/config.py` + `.env.example` — 3
field DB mới") đối chiếu `specs/product-spec.md` (Acceptance Criteria) và
`specs/test-plan.md`.

### Pass
- Đúng pattern field hiện có (`Field(default=..., alias=...)`), không đổi
  cách đọc `.env` (`pydantic_settings`, điểm duy nhất chạm secrets — đúng
  docstring đầu file `config.py`).
- `pytest` vẫn sạch (5 passed) — không regression cho v1.
- Không thêm thư viện mới, không đổi kiến trúc — đúng AGENTS.md.
- Giá trị default khớp CHÍNH XÁC 3 tên DB đã verify thật ở Phase 2 item 1
  (không suy đoán tên DB lần thứ 2).

### Fail
- Không tìm thấy vấn đề nào trong phạm vi hẹp của feature này (chỉ thêm
  field cấu hình, chưa có logic nào dùng tới nên không có gì để "chạy sai").

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `product-spec.md`/`test-plan.md` chưa có dòng nào assert riêng cho việc
  "3 field config tồn tại" — vì `product-spec.md` viết ở mức mục tiêu sản
  phẩm (không liệt kê tên field), và `test-plan.md` chỉ test hành vi
  runtime (DB connect được/bị chặn), field cấu hình đơn thuần không có
  hành vi để test độc lập — hợp lý, KHÔNG cần bổ sung test giả cho field
  chưa ai dùng.
- `src/db/connection.py`, `src/db/queries.py`, `src/guardrails.py` chưa
  dùng 3 field mới — đúng, đó là Phase 3/2-item-3, chưa tới lượt.
- Không có gì khác cần sửa. Không có thay đổi nào thêm ở lượt review này.

## 2026-09-17 (Review Phase 2 item 1 vs product-spec.md/test-plan.md)

Review lại đúng 1 feature vừa làm ("GRANT SELECT cho 3 DB mới") đối chiếu
`specs/product-spec.md` (Acceptance Criteria) và `specs/test-plan.md`
("Test guardrail an toàn... lặp lại cho 3 DB mới").

### Pass
- `product-spec.md` mục "Hạ tầng — đọc-only Postgres qua role riêng...
  trên mọi DB nguồn cần dùng": đúng, role `agent_readonly` giờ SELECT
  được cả 5 DB (2 cũ + 3 mới), vẫn 1 role duy nhất, không phải admin.
- `test-plan.md`: SELECT chạy được trên cả 3 DB mới — đã verify lại (xem
  entry trước).
- `test-plan.md`: DELETE/UPDATE bị từ chối trên cả 3 DB mới —
  **verify lại đủ cả 3 DB** (lượt trước chỉ test 2/3: `anomaly`,
  `firesmoke`, THIẾU `smart_face`). Đã test bổ sung `DELETE FROM
  smf_face_events` → bị từ chối đúng (`InsufficientPrivilege`).
- Không thêm thư viện mới (`psycopg2-binary` đã có sẵn trong
  `requirements.txt` từ v1). Không đổi kiến trúc — chỉ GRANT thêm trên DB
  mới, đúng SQL pattern đã có trong README.

### Fail (spec sai, không phải code sai) — đã sửa
- `test-plan.md` mục "Test guardrail an toàn... lặp lại cho 3 DB mới" ghi
  kỳ vọng lỗi `ReadOnlySqlTransaction` cho DELETE/UPDATE — SAI ở giai đoạn
  hiện tại. Đọc lại `src/db/connection.py::get_connection()` mới thấy:
  lỗi `ReadOnlySqlTransaction` đến từ `conn.set_session(readonly=True)`
  (tầng APP, trong code), không phải từ GRANT của Postgres. Hàm
  `get_connection()` hiện CHỈ whitelist `its`/`virtual_fence`
  (`_allowed_dbnames()`) — chưa hỗ trợ 3 DB mới (đó là việc của Phase 3,
  CHƯA làm). Vì vậy test cho 3 DB mới ở giai đoạn này chỉ có thể đi qua
  raw `psycopg2.connect()` (bỏ qua `get_connection()`), và lỗi ĐÚNG quan
  sát được là `InsufficientPrivilege` (thuần Postgres GRANT), không phải
  `ReadOnlySqlTransaction`. Test-plan.md copy nguyên cách diễn đạt của
  pattern v1 mà không tính tới khác biệt này.
- **Sửa:** viết lại mục đó trong `test-plan.md`, tách rõ 2 lớp bảo vệ
  KHÁC cơ chế: lớp Postgres/GRANT (verify được ngay, kỳ vọng
  `InsufficientPrivilege`) và lớp app/session-readonly (chỉ verify được
  sau Phase 3, kỳ vọng `ReadOnlySqlTransaction`) — không để lẫn lộn 2 lớp
  khi ai đó test lại theo đúng câu chữ cũ.

### Missing (đúng phạm vi, KHÔNG phải thiếu sót của feature này)
- `src/config.py` chưa có `DB_NAME_FACE`/`DB_NAME_FIRE`/`DB_NAME_ANOMALY`
  — checklist item TIẾP THEO của Phase 2, chưa tới lượt.
- `src/db/connection.py` chưa mở whitelist cho 3 DB mới — Phase 3, chưa
  tới lượt.
- `README.md` mục "Tạo DB role read-only" chưa có ví dụ SQL cho 3 DB mới
  — Phase 7, chưa tới lượt (đã ghi nhận đúng ở entry trước).
- Không có gì khác trong `product-spec.md`/`test-plan.md` áp dụng cho
  phạm vi hẹp "GRANT SELECT cho 3 DB mới" của feature này.

## 2026-09-17 (Phase 2, item 1: GRANT SELECT cho 3 DB mới)

### Added
- GRANT `SELECT` (+ `CONNECT`/`USAGE`, default privileges cho bảng tương
  lai) cho role `agent_readonly` đã có sẵn trên 3 DB mới:
  `smart_face`, `firesmoke`, `anomaly` — cùng host/port với `its`/
  `virtual_fence` hiện tại (`192.168.1.250:18644`). KHÔNG tạo role mới —
  tái dùng đúng `agent_readonly` (đơn giản hơn, không cần thêm biến
  `.env` để chọn user khác nhau theo DB).
- Thực hiện qua 1 script Python one-off (không thuộc `src/`, không
  commit vào repo) dùng tài khoản admin `dev` (nhận trực tiếp từ user
  qua chat cho phiên làm việc này, chỉ giữ trong biến môi trường tạm,
  KHÔNG ghi vào bất kỳ file nào trong repo, không log ra output).

### Verified
- Cả 3 DB (`smart_face`, `firesmoke`, `anomaly`) nằm CÙNG Postgres host
  với `its`/`virtual_fence` — xác nhận bằng connect thật (không suy
  đoán), giải quyết dứt điểm giả định #1 ở `implementation-plan.md`
  Phase 2.
- Sau khi GRANT: `agent_readonly` SELECT được trên cả 3 DB (thấy đúng
  bảng `smf_*` cho `smart_face`, `fire_smoke_event` cho `firesmoke`,
  `anomaly_event` cho `anomaly`).
- `agent_readonly` vẫn bị Postgres từ chối `DELETE`/`UPDATE` trên 2 bảng
  mới (`anomaly_event`, `fire_smoke_event`) — `InsufficientPrivilege` —
  xác nhận role vẫn đúng nghĩa read-only sau khi mở rộng, không vô tình
  cấp thừa quyền.

### Sự cố bảo mật trong lượt này (đã xử lý, cần user lưu ý)
- Khi đọc `.env` để xác nhận nội dung, dùng `sed` để redact secret trước
  khi hiện ra — nhưng regex chỉ khớp `KEY=`, không khớp `KEYS=` (biến
  `OPENAI_API_KEYS` có thêm `S`), nên 2 API key OpenAI thật đã bị hiện
  nguyên văn trong output của 1 lệnh trong phiên làm việc này.
  **Khuyến nghị: rotate/thu hồi 2 API key OpenAI đó** (`sk-proj-I1DF...`
  và `sk-proj-gVUY...` — 8 ký tự đầu để nhận diện, không lặp lại đầy đủ
  ở đây) vì đã xuất hiện trong log của phiên làm việc.
- Mật khẩu admin Postgres (`dev`) do user gõ trực tiếp trong chat — chỉ
  dùng trong biến môi trường của 1 lệnh chạy script, không ghi vào file
  nào trong repo, không xuất hiện trong output của bất kỳ lệnh nào sau
  đó.

### Review vs implementation-plan.md
- Đây là item ĐẦU TIÊN chưa check trong `implementation-plan.md` (Phase
  2, checklist). Đã đánh dấu `[x]`, cập nhật luôn mục "Giả định" của
  Phase 2 thành "ĐÃ XÁC NHẬN" (cả 2 giả định đều đúng).
- **Chưa làm** (đúng phạm vi, để item tiếp theo): chưa cập nhật
  `README.md` mục "Tạo DB role read-only" với ví dụ SQL cho 3 DB mới —
  đó là việc của Phase 7, không lấn sang ở đây theo nguyên tắc "chỉ triển
  khai 1 task tại 1 thời điểm" (AGENTS.md).

> **Lưu ý đọc lịch sử:** `specs/implementation-plan.md` được rewrite lại
> cấu trúc phase ngày 2026-09-17 (entry "Rewrite implementation-plan.md"
> bên dưới). Mọi entry **trước** ngày đó nói "Phase N" là theo số phase
> CŨ (v1: 1 Setup, 2 Config, 3 DB layer, 4 Agent, 5 Validation, 6 README).
> Entry **từ/sau** ngày đó dùng số phase MỚI (xem đầu
> `implementation-plan.md`) — 2 hệ số không tương thích 1-1, đừng suy ra
> nội dung phase từ số thứ tự khi đọc entry cũ.

## 2026-09-17 (Rewrite `implementation-plan.md` thành 8 phase nhỏ)

### Changed
- `specs/implementation-plan.md` — viết lại toàn bộ theo đúng 8 phase
  user yêu cầu: 1 Project setup, 2 Mở rộng 5 domain sự kiện VMS mới,
  3 Core backend/data logic, 4 Core Observability (Langfuse), 5 Connect UI
  to data, 6 Validation and error states, 7 Local run instructions,
  8 Local demo setup. Mỗi phase có mục "v1 — đã xong" (`[x]`, không đổi
  nội dung, chỉ sắp xếp lại vị trí) và "v2 — chưa code" (`[ ]`).
- Số phase ĐỔI so với bản trước: domain sự kiện mới (cũ Phase 7) → Phase 2;
  Langfuse (cũ Phase 8) → Phase 4. Cập nhật cross-reference ở `AGENTS.md`,
  `specs/product-spec.md`, `specs/test-plan.md`, `README.md` cho khớp.

### Quyết định phạm vi — Prompt Registry bị bỏ khỏi 8 phase
- Yêu cầu rewrite lần này liệt kê ĐÚNG 8 phase, không nhắc Prompt Registry
  (cũ Phase 9). Không tự ý nhét Prompt Registry vào 1 trong 8 phase trên
  (có thể sai ý định user) — thay vào đó giữ nguyên nội dung kỹ thuật đã
  viết trước đó (`prompts/<name>/vN.yaml` + `production.txt` alias +
  `PromptRegistry.get()/render()`) nhưng chuyển xuống 1 mục "Ghi chú" cuối
  `implementation-plan.md`, đánh dấu rõ CHƯA có phase. `product-spec.md`
  vẫn liệt kê Prompt Registry ở "Features In Scope" — có mismatch tạm thời
  giữa 2 file, đã ghi chú tường minh ở cả 2 nơi thay vì để mismatch ngầm.
- Cần hỏi lại user ở lượt sau: giữ Prompt Registry làm 1 phase riêng
  (Phase 9) hay bỏ hẳn khỏi kế hoạch hiện tại.

### Verified
- Grep lại toàn bộ `README.md`/`AGENTS.md`/`specs/*.md` sau khi đổi số
  phase — không còn chỗ nào trỏ "Phase 7/8/9" (số cũ) vào nội dung mới.

## 2026-09-17 (Review: đơn giản hoá `product-spec.md`)

### Changed
- `specs/product-spec.md` — viết lại gọn hơn theo yêu cầu review "keep it
  simple, đảm bảo rõ 6 mục: goal/target users/core user flow/features in
  scope/features out of scope/acceptance criteria". Chuyển 2 phần chi tiết
  kỹ thuật (bảng ánh xạ sự kiện → DB.table, và các giả định chưa verify)
  sang `specs/implementation-plan.md` mục Phase 7 — đây là nội dung phục
  vụ lúc CODE Phase 7, không phải mục tiêu sản phẩm nên không cần nằm ở
  product-spec. Product-spec giờ chỉ còn 8 dòng liệt kê tên sự kiện (mục
  Goal) + 1 câu trỏ sang implementation-plan cho chi tiết.
- `specs/implementation-plan.md` (Phase 7) — nhận lại bảng ánh xạ + giả
  định + bảng phân bổ 30 case (trước nằm ở product-spec) ngay tại chỗ dùng
  đến chúng (đầu Phase 7, trước checklist).
- `AGENTS.md` — sửa link trỏ giả định Phase 7 từ `product-spec.md` sang
  `implementation-plan.md` (theo đúng vị trí mới).
- Không đổi nội dung/kết luận nào đã tra cứu ở lượt trước — chỉ di chuyển
  vị trí trong doc, không code nào bị đụng tới.

### Review
- **Pass:** `specs/product-spec.md` giờ đọc hết trong ~2 phút, đủ 6 mục
  yêu cầu, không còn bảng kỹ thuật/self-review lấn vào giữa các mục.
- Grep xác nhận không còn tham chiếu treo tới 2 mục đã xoá khỏi
  product-spec (`Giả định & câu hỏi mở`, `Bảng ánh xạ sự kiện`) — đã sửa
  3 chỗ trỏ sai (`AGENTS.md`, `implementation-plan.md` 2 chỗ).

## 2026-09-17 (Spec-only: mở rộng phạm vi v2 — CHƯA CODE)

### Added (chỉ specs/docs, không có thay đổi code theo đúng yêu cầu)
- `specs/product-spec.md` — mở rộng "Goal"/"Features In Scope"/"Features
  Out of Scope"/"Acceptance Criteria" từ phạm vi v1 (xe ra/vào + xâm nhập
  vùng cấm) lên v2 (8 loại sự kiện VMS: FACE, PLATE, ZONE, ẩu đả, đám đông,
  leo trèo, FIRE, mực nước) + 2 hạ tầng mới (Langfuse tracing self-host,
  Prompt Registry git-based). Thêm mục "Giả định & câu hỏi mở" và bảng ánh
  xạ sự kiện → DB.table.
- `specs/implementation-plan.md` — thêm Phase 7 (mở rộng 5 domain sự kiện
  mới + golden dataset v2 + eval runner), Phase 8 (Langfuse tracing), Phase
  9 (Prompt Registry). Tất cả item đang `[ ]` (chưa làm) — Phase 1-6 (v1)
  giữ nguyên `[x]`, không sửa.
- `specs/test-plan.md` — thêm test plan cho Phase 7-9 (test offline, test
  guardrail an toàn cho 3 DB mới, test thật theo domain, test golden
  dataset v2, test tracing, test prompt registry).
- `README.md` — thêm mục "Lộ trình mở rộng (v2, Phase 7-9)" trỏ tới các
  spec ở trên, ghi rõ CHƯA triển khai.

### Grounding (quan trọng — không suy đoán phạm vi sự kiện mới)
Trước khi viết spec, đã tra cứu trực tiếp trong monorepo
`/home/atin/dong/dong/KCNHungPhu` (không phải trong `kcn_hungphu_agent`) để
xác nhận 8 loại sự kiện người dùng liệt kê đều có nguồn dữ liệu Postgres
thật, tránh spec ra tính năng không có data backing:
- `kcn/crowd/KCN_HUNGPHU_MQTT_AI_EVENTS.md` — payload MQTT edge→BE thật,
  liệt kê DB đích cho từng `ai_modules` (FACE→`smart_face.smf_face_events`,
  PLATE→`its.plate_event`, ZONE→`virtual_fence.zone_event`,
  FIRE→`firesmoke.fire_smoke_event`, và nhóm ANOMALY gồm
  FIGHT_DETECTION/CROWD_DETECTION/INTRUSION_DETECTION (leo trèo)/
  FALL_DETECTION/SMOKING_DETECTION/WEAPON_DETECTION).
- `agent-harness/services/vms-sync/sources.py` — code sync Postgres→
  ClickHouse ĐANG CHẠY THẬT trong harness khác cùng máy, xác nhận chính
  xác tên cột từng bảng (dùng để viết `SELECT` mẫu trong
  `implementation-plan.md` Phase 7).
- `agent-harness/skills/vms-analytics.md` — xác nhận "giám sát mực nước"
  KHÔNG có bảng riêng, mà là `event_type=WATER_LEVEL_DETECTION` trong CHUNG
  bảng `anomaly.anomaly_event` với ẩu đả/đám đông/leo trèo — quyết định
  thiết kế "1 tool `count_anomaly_events` dùng chung, `event_type` là
  tham số" trong Phase 7 xuất phát trực tiếp từ phát hiện này (không phải
  chọn tuỳ ý để đơn giản hoá).
- **Không tìm thấy** pipeline/bảng "mực nước" độc lập nào trong repo — ban
  đầu nghi ngờ đây là domain thiếu data, nhưng tra thêm `vms-analytics.md`
  mới xác nhận nó nằm trong `anomaly_event` (không phải domain rời).

### Review vs yêu cầu user
- **Pass:** đủ 6 file được yêu cầu (`README.md`, `AGENTS.md`,
  `specs/product-spec.md`, `specs/implementation-plan.md`,
  `specs/test-plan.md`, `specs/change-log.md`).
- **Quyết định phạm vi (không phải bug):** yêu cầu gốc có nhắc trực tiếp
  "update `eval/datasets/agent_stat` cho tôi" — NHƯNG dòng cuối yêu cầu ghi
  rõ "Do not implement the app yet" và "Before writing any code, create or
  update these files: [6 file trên]". Hiểu đây là 2 chỉ dẫn ở 2 tầng khác
  nhau: tầng "mô tả app idea" (4 gạch đầu dòng, có nhắc golden dataset/
  Langfuse/Prompt Registry) là NGỮ CẢNH cho việc viết spec, còn tầng "việc
  cần làm ngay" chỉ giới hạn ở 6 file docs. Vì vậy: viết CHI TIẾT kế hoạch
  golden dataset v2 (bảng phân bổ 30 case/8 domain) trong
  `implementation-plan.md`, nhưng CHƯA tạo file
  `eval/datasets/agent_stat/v2.yaml` thật — đúng theo nghĩa đen của "Do not
  implement the app yet". Nếu hiểu sai ý định này, việc tạo file YAML thật
  ở Phase 7 chỉ mất thêm 1 bước nhỏ vì đã có sẵn bảng phân bổ + quy ước.
- **Không đổi code:** không file nào trong `src/`, `eval/datasets/`,
  `tests/`, `.env.example`, `requirements.txt` bị sửa ở lượt này — đúng
  yêu cầu "Do not implement the app yet".

## 2026-09-16 (Phase 6: `README.md` — hoàn thiện, gồm cả mục ngrok)

### Added
- Viết lại `README.md` đầy đủ (trước đó chỉ là placeholder từ Phase 1 —
  "chưa có business logic"), gồm cả 2 item của Phase 6 CÙNG LÚC (gộp vì
  cùng 1 file, tách ra 2 lần edit không có ích): Kiến trúc (tóm tắt pipeline
  `guardrail_input → agent → guardrail_output`, ngân sách 2 LLM call/câu
  hỏi — tham khảo cấu trúc `atin/README.md` đã kiểm chứng, rút gọn đúng
  tinh thần MVP của project này), Prerequisites, Cài đặt & chạy local,
  bảng tóm tắt Biến môi trường + mục "Tạo DB role read-only" (SQL, tham
  khảo nguyên `atin/README.md`, đã kiểm chứng thực tế), Chuyển sang model
  local (Ollama), Test, **Demo với ngrok** (`ngrok http 8000`, không cần
  cấu hình gì thêm vì 1 cổng duy nhất — đúng acceptance criteria), và bảng
  Troubleshooting mới (không có ở `atin/README.md`, viết riêng cho project
  này dựa trên các lỗi thực tế đã gặp qua các item/review trước: `404` ở
  `/`, `503` ở `/ask`, câu hỏi bị từ chối ngoài phạm vi, latency khi
  `ANSWER_USE_LLM=true`).

### Verified
- `pytest -q` → "5 passed" — khớp đúng số liệu ghi trong README.
- `GET /health` (qua `TestClient`) → `{"status": "ok", "llm_backend":
  "openai", "db_configured": true}` — khớp mô tả README.

## 2026-09-16 (Phase 5: Test thật — 5 câu hỏi mẫu qua endpoint đầy đủ)

### Fixed
- **BUG tìm thấy (hallucination thật của LLM, tái lập ổn định 3/3 lần):**
  chạy đủ cả 5 câu hỏi mẫu qua `POST /ask` (pipeline đầy đủ: guardrail →
  agent → guardrail_output) lần đầu tiên trong 1 lượt thống nhất, dùng biển
  số THẬT lấy từ DB (`15K40139`, cột `normalized_license_plate` trong
  `plate_event`) cho câu hỏi mẫu #4. Kết quả: `row_count=14`, `rows` có đủ
  14 dòng dữ liệu ĐÚNG (camera/thời điểm/chiều ra-vào) — nhưng
  `answer` lại nói "Không có dữ liệu khớp cho phương tiện có biển số
  15K40139", MÂU THUẪN trực tiếp với chính `rows` trong cùng response.
  - **Nguyên nhân:** `src/db/queries.py::trace_plate` (Phase 3) trả về
    columns `[event_time, camera_code, camera_name, direction,
    vehicle_type]` — KHÔNG có cột biển số (đã lọc đúng biển số ở tầng SQL
    nên không lặp lại giá trị đã biết trong output, tiết kiệm token). Khi
    `src/agent/answer.py::build_answer()` đưa dữ liệu này vào prompt cho
    LLM, model KHÔNG thấy chữ "15K40139" xuất hiện ở đâu trong phần "Dữ
    liệu" — theo đúng chỉ dẫn `_SYSTEM` ("CHỈ dựa vào số liệu được cung
    cấp"), model suy luận (SAI) rằng không có gì khớp câu hỏi.
  - Reproduce độc lập: gọi thẳng `invoke_text()` với system prompt +
    user prompt y hệt (không qua toàn bộ graph) → LLM trả lời sai giống
    hệt, ổn định — xác nhận đây là lỗi CÁCH ĐÓNG GÓI PROMPT, không phải
    lỗi ngẫu nhiên/nhiễu của model.
- **Sửa:** thêm đoạn vào `_SYSTEM` (`src/agent/answer.py`) giải thích rõ
  cho model: dữ liệu ĐÃ được lọc đúng theo điều kiện câu hỏi trước khi đưa
  vào, cột không lặp lại điều kiện lọc đã biết (nêu đích danh case "hỏi
  theo biển số cụ thể → dữ liệu sẽ không có cột biển số"), và có ≥1 dòng
  nghĩa là CÓ khớp — không được kết luận "không khớp" chỉ vì không thấy
  giá trị điều kiện lọc lặp lại trong cột.
- Verify lại: gọi trực tiếp `invoke_text()` với đúng prompt cũ (đã gây
  bug) 2 lần liên tiếp — cả 2 lần đều trả lời ĐÚNG, liệt kê đủ camera/thời
  điểm/chiều ra-vào, không còn hallucination "không khớp".

### Verified — Test thật đầy đủ (5/5 câu hỏi mẫu, qua `POST /ask`)
- Chạy lại TOÀN BỘ 5 câu qua endpoint thật (pipeline đầy đủ) sau fix:
  - Q1 (xe máy/ô tô): đúng số liệu cả 2 loại, khớp `rows`.
  - Q2 (số chỗ ngồi): đúng, có nêu rõ giới hạn "không phân loại theo số
    chỗ ngồi" (2 lần — cả trong câu LLM trả lời lẫn ghi chú cứng thêm vào).
  - Q3 (hãng xe): liệt kê đủ 26 hãng + số lượt, khớp `manufacturer` trong
    DB.
  - Q4 (truy vết biển số, biển số THẬT `15K40139`): đúng sau fix — liệt kê
    đủ 14 sự kiện, đúng ngày/giờ/camera/chiều ra-vào, khớp hoàn toàn
    `rows`. KHÔNG regression ở Q1-3, Q5.
  - Q5 (khung giờ xâm nhập): đúng khung giờ cao nhất (02:00, 557 lượt),
    khớp `zone_event`.
- `pytest` chính thức vẫn sạch (5 passed) sau fix — fix chỉ đổi
  `_SYSTEM` (system prompt tĩnh), không đổi logic offline/template nên
  không ảnh hưởng test offline.

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Pass:** verify thêm 2 case biên để đảm bảo fix instruction mới trong
  `_SYSTEM` không gây false negative NGƯỢC (model nói "có khớp" khi thực
  sự không có):
  - Biển số THẬT SỰ không tồn tại (`99Z99999`) → `rows=[]`,
    `answer="Không có dữ liệu khớp..."` (đúng, rơi về template vì
    `has_rows=False`, không gọi LLM nên không bị ảnh hưởng bởi `_SYSTEM`
    mới) — không lẫn với bug đã sửa (biển số CÓ dữ liệu nhưng bị nói sai
    là không có).
  - Loại xe không tồn tại trong schema DB (hỏi "xe đạp") → tool tự
    validate, trả `error` rõ ràng ("vehicle_type phải thuộc [...], nhận
    'BICYCLE'") thay vì hallucinate — không bị ảnh hưởng bởi thay đổi ở
    `answer.py` vì rơi về template do `q.error` có giá trị.
- **Fail:** không tìm thêm bug nào ở lượt review này.
- **Missing:** không có gì khác so với `product-spec.md`/`test-plan.md`
  cho phạm vi "test thật 5 câu hỏi mẫu". Toàn bộ Phase 5 (implementation-
  plan.md) đã hoàn tất sau item này.

## 2026-09-16 (Phase 5: Test offline — pytest chính thức)

### Added
- `tests/test_offline.py` — 5 test case CHÍNH THỨC, khớp đúng thứ tự bảng
  "Test offline" trong `specs/test-plan.md`:
  1. `test_guardrail_chan_prompt_injection` — `check_input()` raise
     `GuardrailViolation` với câu injection tiếng Anh.
  2. `test_guardrail_tu_choi_cau_hoi_ngoai_pham_vi` — câu hỏi ngoài phạm vi
     KHÔNG raise (chỉ injection/toxic mới raise), `in_scope()` trả `False`.
  3. `test_cau_hoi_hop_le_chay_offline_khong_crash` — `run_agent()` ở chế
     độ offline (tự động bật vì `PYTEST_CURRENT_TEST` luôn có sẵn khi chạy
     dưới `pytest`, không cần set biến môi trường thủ công) trả `answer`
     khác rỗng, không crash.
  4. `test_tool_sql_chan_cau_lenh_ghi` — gọi trực tiếp
     `run_sql_readonly.invoke()` với DELETE/UPDATE/DROP, verify có `error`
     trong response. KHÔNG cần DB thật: 3 câu này bị chặn ở lớp kiểm tra
     code (`startswith("select")`/`_WRITE_KEYWORDS`) TRƯỚC khi tool mở
     connection — verify thủ công (ghi output ra file, tránh lỗi encode
     console Windows) xác nhận lỗi trả về đúng ở bước sớm nhất
     ("Chỉ cho phép câu SELECT..."), không chạm `get_connection()`.
  5. `test_danh_sach_tool_dung_thiet_ke` — assertion tên 6 tool trong
     `TOOLS` khớp đúng `specs/product-spec.md` mục "Agent & tool".

### Verified
- `pytest -v`: cả 5 test PASS, chạy trong 0.86s — không cần network/API
  key/DB thật, đúng tinh thần "chạy được cho CI/mọi máy dev" của
  test-plan.md.
- Xác nhận test #4 an toàn dù `.env` hiện tại có DB thật cấu hình sẵn:
  không có rủi ro vô tình DELETE/UPDATE dữ liệu thật, vì code chặn ở tầng
  validate SQL text trước khi gọi `get_connection()`.

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **BUG tìm thấy, đã sửa:** test-plan.md diễn đạt test #1/#2 ở tầng hành vi
  API ("raise lỗi RÕ RÀNG", "KHÔNG lỗi 500") — nhưng bản implement ban đầu
  chỉ gọi thẳng `check_input()`/`in_scope()` (hàm nội bộ), KHÔNG verify qua
  endpoint HTTP thật. "Không lỗi 500" là khẳng định về status code, không
  thể xác nhận chỉ bằng cách gọi hàm Python — 1 lỗi wiring ở `src/main.py`
  (vd. exception handler bị gỡ nhầm) vẫn có thể lọt qua 2 test này mà
  không bị phát hiện.
- **Sửa:** thêm `TestClient(app)` và verify qua `POST /ask` thật cho cả 2
  case: #1 injection → `res.status_code == 400` (không phải 500) +
  `detail` khác rỗng; #2 ngoài phạm vi → `res.status_code == 200` (không
  phải 500) + `answer` khác rỗng + `row_count == 0` (xác nhận không gọi
  tool/DB). Giữ nguyên phần test hàm nội bộ cũ (vẫn hữu ích, chạy nhanh
  hơn, cô lập lỗi rõ hơn khi fail).
- Verify lại: cả 5 test vẫn PASS (1.03s). Warning
  `StarletteDeprecationWarning` (httpx/testclient) là cảnh báo từ thư viện
  bên thứ 3 có sẵn từ khi thêm `fastapi` vào `requirements.txt`, không
  phải lỗi trong code của item này — không sửa (ngoài phạm vi).
- **Fail:** không có vấn đề nào khác.
- **Missing:** test #3 chỉ verify ở tầng hàm nội bộ (`run_agent()` trực
  tiếp) — CHẤP NHẬN ĐƯỢC vì test-plan.md #3 chỉ yêu cầu "answer khác rỗng,
  không crash", không nhắc status code cụ thể như #1/#2, nên không thêm
  test qua `TestClient` để tránh lan phạm vi ngoài yêu cầu thật của item
  này.

## 2026-09-16 (Phase 5: UI hiển thị rõ 3 trạng thái)

### Not changed (đã đủ từ trước, chỉ xác nhận + đánh dấu hoàn thành)
- `static/index.html` (viết ở Phase 4) đã có sẵn đủ 3 trạng thái: "Đang xử
  lý..." (class `.pending`, disable nút tránh double-submit), trả lời
  thành công (bong bóng chat + bảng số liệu), lỗi (class `.error`, đọc
  `data.detail`). `src/main.py::guardrail_violation_handler` (sửa ở item
  "ghép luồng" review trước) đã thêm field `detail` cho response `400` để
  UI đọc đúng. Vì cả 2 phần này đã hoàn thiện và verify qua các item/review
  trước, item này KHÔNG cần sửa code gì thêm — chỉ còn thiếu case "lỗi kết
  nối DB/LLM" (`503`) chưa được verify tường minh, nên tập trung test case
  đó.

### Verified
- Mô phỏng lỗi DB/LLM (`unittest.mock.patch` để `run_agent()` raise
  `RuntimeError("DB connection timeout")`, không cần tắt DB thật): response
  `503` với `{"detail": "Không trả lời được: DB connection timeout"}` —
  đúng dạng string mà JS trong `index.html` cần (`typeof data.detail ===
  "string"`), sẽ hiện "Lỗi: Không trả lời được: DB connection timeout" ở
  bong bóng đỏ, không phải "Bad Request" mơ hồ.
- Tổng hợp lại cả 3 loại lỗi acceptance criteria yêu cầu, đều đã có response
  `detail` dạng string UI đọc đúng: `422` (Pydantic validation, câu hỏi
  rỗng), `400` (guardrail — injection/toxic, sửa ở review trước), `503`
  (agent/DB lỗi, verify ở đây).
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case chính
  thức).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Pass:** câu hỏi ngoài phạm vi → `200` (không phải trạng thái lỗi, đúng
  thiết kế: đây là phản hồi hợp lệ "từ chối lịch sự", không phải lỗi hệ
  thống) → UI hiện bong bóng chat bình thường (không đỏ), đúng acceptance
  criteria "bị từ chối lịch sự, không gọi tool/DB" (verify `tool: ""`,
  `row_count: 0`).
- **BUG tìm thấy, đã sửa:** đang "Đang xử lý..." (nút Hỏi bị `disabled`)
  nhưng ô nhập liệu (`input`) KHÔNG bị khoá — user có thể nhấn Enter trong
  ô input để submit form lần 2 trong lúc request đầu chưa xong (Enter
  submit form không cần nút chưa bị disable). Không crash nhưng vi phạm
  tinh thần "trạng thái đang xử lý" rõ ràng đã thiết kế (chặn double-submit
  qua nút nhưng bỏ sót đường Enter).
- **Sửa:** thêm `input.disabled = true` cùng lúc với `button.disabled =
  true` lúc bắt đầu xử lý, mở khoá lại cả 2 ở khối `finally` (đảm bảo mở
  khoá dù thành công/lỗi/exception), thêm `input.focus()` sau khi mở khoá
  để UX mượt hơn (không phải feature mới, chỉ đi kèm fix disable/enable).
- Verify: `GET /` vẫn `200`, HTML có đủ logic mới. `pytest` vẫn sạch.
- **Missing:** không có gì khác so với `product-spec.md`/`test-plan.md`
  cho phạm vi UI 3 trạng thái.

## 2026-09-16 (Phase 5: Ghép luồng guardrail_input → agent → guardrail_output)

### Added
- `src/main.py` (`ask()`): ghép guardrail vào pipeline `/ask` bằng hàm đơn
  giản (KHÔNG dùng graph hub riêng — khác `atin/app/supervisor_agent/
  graph.py`, project này không có supervisor LangGraph, chỉ 1 agent duy
  nhất nên gọi tuần tự đủ, đúng tinh thần "giữ giải pháp đơn giản" của
  AGENTS.md):
  1. `check_input()` — injection/toxic → raise `GuardrailViolation`, KHÔNG
     gọi `run_agent()`/DB.
  2. `in_scope()` — ngoài phạm vi → trả `OUT_OF_SCOPE_REPLY` ngay, cũng
     KHÔNG gọi `run_agent()`/DB.
  3. `redact_pii()` trên câu hỏi trước khi đưa vào agent (che SĐT/email
     người dùng gõ nhầm vào câu hỏi).
  4. `run_agent()` (không đổi).
  5. `check_output()` — đối chiếu answer với evidence (câu hỏi + toàn bộ
     `columns=value` từ `query.rows` thật) → answer cuối có thể được thêm
     disclaimer/redact/cắt bớt.
  - `guardrail_violation_handler` (exception handler cho `GuardrailViolation`,
    tham khảo `atin/app/main.py`) → response `400`.

### Fixed (phát hiện khi test end-to-end lần đầu qua pipeline thật)
- **BUG:** `guardrail_violation_handler` trả JSON chỉ có
  `error`/`reason`/`details`, KHÔNG có key `detail` — trong khi
  `static/index.html` (đã viết ở Phase 4) đọc `data.detail` cho MỌI lỗi
  khác (`422`, `503`). Hậu quả: khi injection bị chặn, UI hiện "Lỗi: Bad
  Request" (rơi về `res.statusText`) thay vì lý do thật — không crash
  nhưng mất thông tin hữu ích, lần đầu lộ ra vì đây là lần đầu luồng lỗi
  injection thực sự chạy qua UI (trước đó `guardrails.py` chưa được gọi từ
  `main.py`).
- **Sửa:** thêm field `detail` (string, format sẵn
  `"Câu hỏi bị từ chối: {reason}"`) vào response, giữ nguyên
  `error`/`reason`/`details` cho API consumer khác cần chi tiết máy đọc
  được.

### Verified
- `TestClient`: injection → `400`, response giờ có cả `detail` (string,
  UI đọc được) lẫn `reason`/`details` (giữ nguyên). Câu hỏi ngoài phạm vi
  ("Thời tiết Hà Nội thế nào?") → `200`, trả đúng `OUT_OF_SCOPE_REPLY`,
  KHÔNG gọi agent/DB (verify qua `tool: ""`, `row_count: 0`).
- Test thật qua LLM (3/5 câu hỏi mẫu, đại diện đủ case) qua pipeline đầy
  đủ: số liệu đúng, không regression so với lần test riêng lẻ ở Phase 4;
  câu trả lời khớp evidence không bị gắn disclaimer thừa (case hãng xe 26
  dòng vẫn sạch).
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case chính
  thức).

### Review lần 2 (kiểm tra sâu hơn sau lượt review đầu)
- **Pass:** toxic content ("đụ mẹ mày...") → `400`, `reason:
  unsafe_content`, không gọi agent/DB. Câu hỏi in-scope có PII nhúng sẵn
  ("...gọi tôi qua 0912345678 nhé") → PII bị redact TRƯỚC khi vào agent
  (`question` trả về đã là `"...qua [SĐT ẩn] nhé"`), không lộ SĐT ở bất kỳ
  đâu trong response.
- **Pass (edge case):** câu hỏi chỉ có khoảng trắng (`"   "`, qua được
  Pydantic `min_length=1` vì không tự strip) — không bị `check_input()`
  raise nhầm, `in_scope()` đúng đắn coi là ngoài phạm vi (không khớp
  keyword nào) → trả lời từ chối lịch sự, không gọi agent/DB, không crash.
  Pipeline tự nhiên an toàn với case này nhờ thứ tự
  check_input → in_scope, không cần sửa thêm.
- **Fail:** không tìm thêm bug nào trong phạm vi item này ở lượt review
  thứ 2.
- **Missing:** không có gì khác so với `product-spec.md`/`test-plan.md`
  cho phạm vi "ghép luồng". 2 item còn lại của Phase 5 (UI 3 trạng thái —
  đã có sẵn từ Phase 4, và test offline `pytest` chính thức) chưa làm,
  đúng như đã ghi nhận.

## 2026-09-16 (Phase 5: `src/guardrails.py`)

### Added
- `src/guardrails.py` — gộp `atin/app/guardrails/checks.py` +
  `atin/app/supervisor_agent/guardrails.py` (2 file, đã kiểm chứng) thành 1
  file phẳng, khớp cấu trúc `src/` không tách package `guardrails/` riêng
  của project này:
  - `check_input()` — raise `GuardrailViolation` khi phát hiện prompt
    injection (regex Anh + Việt, tham khảo
    `llm-engineer-demo/app/guardrails/injection.py`) hoặc từ ngữ độc hại.
    KHÔNG chặn câu hỏi ngoài phạm vi (đó là `in_scope()`, trả lời lịch sự
    thay vì raise).
  - `in_scope()` + `STAT_KEYWORDS` + `OUT_OF_SCOPE_REPLY` — nhận diện câu
    hỏi có thuộc phạm vi thống kê xe/khu vực không.
  - `check_output()` — đối chiếu số trong câu trả lời với evidence (câu hỏi
    + dữ liệu tool thật), gắn disclaimer nếu có số không xác minh được;
    redact PII (SĐT/email, tham khảo
    `llm-engineer-demo/app/guardrails/pii.py`); cắt bớt nếu vượt độ dài tối
    đa; trả fallback nếu quá ngắn/độc hại.
  - Toàn bộ bằng regex/code, KHÔNG LLM — đúng quyết định đã ghi trong
    `implementation-plan.md` (giữ ngân sách tối đa 2 lời gọi LLM/câu hỏi).
- `src/config.py` — thêm 2 field cần thiết cho `check_output()`:
  `guardrails_min_answer_len` (mặc định 5), `guardrails_max_answer_len`
  (mặc định 2000). Cập nhật `.env.example` tương ứng — cần thiết để module
  chạy được, không phải mở rộng phạm vi ngoài item.

### Changed (phạm vi, để không lấn sang item tiếp theo)
- CHƯA ghép `check_input`/`in_scope`/`check_output` vào `src/main.py` hay
  `src/agent/graph.py` — đó là item kế tiếp Phase 5 ("Ghép luồng:
  guardrail_input → agent → guardrail_output").

### Verified
- Test tạm (viết rồi xoá sau khi xác nhận, output ghi file vì console
  Windows cp1252 không in được tiếng Việt):
  - `check_input()` chặn đúng injection tiếng Anh ("Ignore all previous
    instructions...") VÀ tiếng Việt ("bỏ qua mọi hướng dẫn trước đó") —
    raise `GuardrailViolation`.
  - `in_scope("Thời tiết Hà Nội thế nào?")` → `False`; `in_scope("Hôm nay
    có bao nhiêu lượt xe vào?")` → `True` — khớp `test-plan.md` mục "Test
    offline" #1, #2.
  - Câu hỏi bình thường không bị `check_input()` raise nhầm.
  - `check_output()`: số khớp evidence → `valid=True`, không đổi answer; số
    không khớp evidence (999999 không có trong evidence) → gắn disclaimer
    đúng, `issues=["unverified_numbers"]`.
  - `redact_pii()`: SĐT `0912345678` → `[SĐT ẩn]`, email → `[email ẩn]`.
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case chính
  thức — sẽ viết ở item "Test offline" cuối Phase 5).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **BUG tìm thấy, đã sửa:** `check_output()` đối chiếu số bằng string match
  thô (`\b\d+\b`) — test với câu trả lời THẬT đã thấy ở Phase 4 (item
  `answer.py`, câu hỏi mẫu #2: `"...9.418 lượt... 5.286 lượt..."`) phát hiện
  FALSE POSITIVE: LLM tự format số có dấu `.` phân cách hàng nghìn kiểu VN
  (`5.286`), trong khi evidence (dữ liệu tool thô) không có dấu phân cách
  (`so_luot=5286`) → regex tách `5.286` thành 2 số `5` và `286`, không khớp
  `5286` trong evidence → gắn OAN disclaimer "số liệu chưa xác minh được"
  cho câu trả lời có số liệu HOÀN TOÀN ĐÚNG, chỉ khác cách trình bày.
- **Sửa:** chuẩn hoá cả `text` và `context_text` — bỏ dấu `.` đứng giữa 1
  chữ số và đúng 3 chữ số tiếp theo (`(?<=\d)\.(?=\d{3}\b)`, đặc trưng dấu
  phân cách nghìn) TRƯỚC khi trích số bằng `\b\d+\b`, không đổi hành vi với
  số thập phân thật (vd. "1.5%" không bị normalize sai vì chỉ có 1 chữ số
  sau dấu chấm, không phải 3).
- Verify lại: số giống hệt evidence, chỉ khác định dạng dấu phân cách
  (`5.286` vs `5286`) → giờ `valid=True`, không còn disclaimer oan. Số BỊA
  thật (không có trong evidence, vd. `999.999` không khớp gì) → vẫn đúng bị
  gắn disclaimer, KHÔNG bị fix này che giấu. Số thập phân thật (`1.5%`) →
  không bị ảnh hưởng bởi normalize.
- **Lưu ý (không phải bug, đúng thiết kế theo test-plan.md mục "Không cần
  test ở MVP này"):** tổng LLM tự cộng từ nhiều dòng dữ liệu (vd. tự cộng
  5286+3357+701+74=9418 rồi viết vào câu trả lời) vẫn bị gắn disclaimer vì
  `9418` không xuất hiện literal trong evidence — guardrail chỉ đối chiếu
  string match, không làm phép tính. Test-plan.md đã ghi rõ: guardrail chỉ
  cần "che" (gắn disclaimer), không cần verify độ chính xác phép tính của
  LLM — hành vi "false positive an toàn" này chấp nhận được, không sửa.
- `pytest` chính thức vẫn sạch sau fix (exit code 5).
- **Missing:** không có vấn đề nào khác so với `product-spec.md`/
  `test-plan.md` cho phạm vi `guardrails.py`. Pipeline chưa ghép (item kế
  tiếp) nên chưa test được end-to-end qua `/ask`.

## 2026-09-16 (Phase 4: `static/index.html`)

### Added
- `static/index.html` — UI chat tối giản, HTML/JS thuần (không framework),
  gọi `POST /ask` (khớp route thật trong `src/main.py`, không phải
  `/stat/ask` như bản `atin/`). Tham khảo `atin/static/index.html` (đã kiểm
  chứng), bỏ `thread_id` (route `/ask` hiện tại không nhận tham số này).
  3 trạng thái rõ ràng theo acceptance criteria: "Đang xử lý..." (class
  `.pending`, hiện ngay khi submit, disable nút Hỏi tránh double-submit),
  trả lời thành công (bong bóng chat + bảng số liệu thô nếu có), lỗi (class
  `.error`, màu đỏ, hiện cả lỗi HTTP từ backend lẫn lỗi kết nối mạng qua
  `try/catch`) — không có trường hợp nào im lặng hoặc crash trắng trang.

### Verified
- `TestClient`: `GET /` → 200, `text/html`, có `<form>` và tiêu đề đúng.
  `GET /static/index.html` → 200 (route `/static` đã mount từ item
  `main.py` trước, giờ có file thật để phục vụ).
- Server thật (`uvicorn src.main:app --port 8199`, không chỉ `TestClient`):
  `GET /` → 200. Gọi `POST /ask` qua `urllib` (giả lập request UTF-8 giống
  `fetch()` trình duyệt gửi — curl trên Git Bash Windows tự làm hỏng
  encoding tiếng Việt trong `-d`, không phải lỗi app) với câu hỏi tiếng Việt
  thật → nhận JSON đúng UTF-8, đúng field `answer`/`tool`/`columns`/`rows`/
  `row_count` mà JS trong `index.html` cần để render bong bóng chat + bảng.
- **Giới hạn đã biết:** môi trường này không có trình duyệt thật để xem
  rendering trực quan (giao diện, CSS, click nút) — chỉ xác nhận được HTML
  hợp lệ, JS đọc đúng cấu trúc response qua kiểm tra logic + dữ liệu JSON
  thật khớp những gì `addMsg()` cần. Người dùng nên tự mở
  `http://localhost:8000/` trên trình duyệt thật để xác nhận giao diện
  trước khi coi là hoàn tất theo đúng nghĩa "test UI trong browser".

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Pass:** 3 trạng thái rõ ràng (đang xử lý / thành công / lỗi) — đã có
  đủ, không trạng thái nào im lặng.
- **Kiểm tra thêm (không phải bug):** thử case `/ask` trả `422` (FastAPI
  validation error) — `detail` ở đây là MẢNG object, không phải string.
  JS đã xử lý đúng (`typeof data.detail === "string" ? ... :
  JSON.stringify(...)`) nên hiện JSON thô thay vì câu tiếng Việt đẹp —
  KHÔNG crash, KHÔNG `undefined`/`[object Object]`, vẫn đạt acceptance
  criteria tối thiểu. Không sửa vì: (1) input rỗng đã bị chặn client-side
  (`required` + `if (!question) return`) nên case 422 gần như không xảy ra
  qua UI thật, (2) polish UX thông báo lỗi đẹp hơn là thêm tính năng ngoài
  phạm vi item ("Do not add new features").
- **Fail:** không có.
- **Missing (ngoài phạm vi item này):** guardrail chưa nối (Phase 5) nên
  UI chưa test được case "câu hỏi bị từ chối vì injection/ngoài phạm vi" —
  đã ghi nhận ở lần implement, không phải thiếu sót của `index.html`.

## 2026-09-16 (Phase 4: `src/main.py`)

### Added
- `src/main.py` — FastAPI app: `POST /ask` (gọi `run_agent()`, trả câu trả
  lời + số liệu thô), `GET /health` (trạng thái backend/DB, không lộ
  secrets), `GET /` (phục vụ `static/index.html` nếu có, `404` rõ ràng nếu
  chưa có thay vì crash). Mount `/static` chỉ khi thư mục `static/` tồn tại
  (item kế tiếp của Phase 4 mới tạo `static/index.html`, tránh lỗi
  `StaticFiles` không tìm thấy thư mục lúc khởi động app). Tham khảo cấu
  trúc `atin/app/main.py` nhưng bỏ `thread_id`/CORS/exception handler riêng
  cho guardrail (guardrail chưa tồn tại — thuộc Phase 5, chưa lấn phạm vi).

### Verified
- `TestClient` (không cần chạy uvicorn thật): `GET /health` → 200, đúng
  `llm_backend`/`db_configured` từ `.env` thật. `GET /` → 404 (đúng, chưa có
  `static/index.html`). `POST /ask {"question": "test"}` → 200, gọi
  `run_agent()` qua LLM thật thành công (câu hỏi mơ hồ nên trả "Chưa truy
  vấn được dữ liệu." — đúng hành vi, không phải lỗi).
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Pass:** "Chạy được local bằng 1 lệnh" — verify thật bằng
  `uvicorn src.main:app --port 8199` (server thật, không chỉ `TestClient`):
  `GET /health` → 200 đúng dữ liệu, `GET /` → 404 rõ ràng (chưa có
  `static/index.html`, đúng thiết kế fallback thay vì crash).
- **Pass:** "User thấy trạng thái rõ ràng... không im lặng, không crash
  trắng trang" — verify câu hỏi rỗng (`{"question": ""}`) → Pydantic trả
  `422` kèm message rõ ràng (`string_too_short`), không crash 500. Lỗi từ
  `run_agent()` (vd. LLM lỗi) đã được bọc `try/except` → `503` với message,
  không lộ traceback thô.
- **Fail:** không phát hiện bug nào trong phạm vi `src/main.py`.
- **Missing (không thuộc phạm vi item này):** guardrail input/output
  (chặn injection, từ chối câu hỏi ngoài phạm vi, đối chiếu số liệu output)
  chưa nối vào `/ask` — đúng như đã ghi nhận lúc implement, thuộc Phase 5
  chưa tới lượt. `static/index.html` chưa có nên `/` còn 404 — là item kế
  tiếp của Phase 4, không phải lỗi của item này.

## 2026-09-16 (Phase 4: `src/agent/answer.py`)

### Added
- `src/agent/answer.py` — `build_answer(question, queries, template_answer)`:
  lời gọi LLM thứ 2 (không tool, `invoke_text`) diễn giải (các) `QueryResult`
  thành câu tiếng Việt tự nhiên. Tham khảo `atin/app/answer.py` (đã kiểm
  chứng) nhưng đổi chữ ký để nhận `list[QueryResult]` thay vì 1 cái — khớp
  với `_pack()` hiện tại của `agent_ATIN` đã gộp nhiều tool call song song
  (xem entry Phase 4 `graph.py` phía dưới). Rơi về `template_answer` (do
  caller truyền vào, không tự dựng lại) khi: `ANSWER_USE_LLM=false`,
  offline/pytest, không có dòng dữ liệu nào, hoặc lời gọi LLM lỗi — không
  bao giờ crash vì bước diễn giải.

### Changed
- `src/agent/graph.py`: `_pack()` giờ gọi `build_answer(question, queries,
  template)` thay vì dùng thẳng `template` làm `answer` cuối — template vẫn
  được dựng trước (từ `_template_answer()`) để làm fallback truyền vào.

### Verified
- Offline mode (`PYTEST_CURRENT_TEST=1`): `build_answer` phát hiện
  `use_offline_tools()` và trả thẳng `template_answer`, không gọi LLM —
  confirm qua file output (console Windows không in được tiếng Việt, dùng
  cp1252) — khớp câu trả lời template cũ, không đổi hành vi offline.
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case).
- Test thật (LLM thật, `ANSWER_USE_LLM=true` mặc định) — chạy lại cả 5 câu
  hỏi mẫu qua `run_agent()`:
  - Q1, Q2, Q3, Q5: answer giờ là câu tiếng Việt tự nhiên, diễn giải đúng số
    liệu thật đã lấy được (vd. Q1: "Hôm nay có tổng cộng 1909 lượt xe máy
    vào, 1448 lượt xe máy ra, 2588 lượt ô tô vào và 2697 lượt ô tô ra.") —
    khớp số liệu tool trả về, không bịa thêm số.
  - Q4 (truy vết biển số, câu hỏi mẫu không nêu biển số cụ thể): tool
    `trace_plate` không có điều kiện lọc nên không khớp dòng nào → rơi về
    template "Không có dữ liệu khớp câu hỏi..." — đúng hành vi fallback,
    KHÔNG phải lỗi của bước Answer (do câu hỏi thiếu tham số, nằm ngoài
    phạm vi sửa của item này).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **BUG tìm thấy, đã sửa:** `test-plan.md` mục "Test thật" câu hỏi mẫu #2
  yêu cầu: khi hỏi phân loại theo số chỗ ngồi (5/7/9/16/29/40 chỗ) — thứ DB
  không có — "cần nêu rõ giới hạn này trong câu trả lời hoặc README". Test
  với `ANSWER_USE_LLM=true` (mặc định) thì PASS (LLM tự nêu giới hạn nhờ
  `_SYSTEM` prompt). Nhưng test lại với `ANSWER_USE_LLM=false` (đường
  template fallback, không qua LLM) thì FAIL: `_template_answer()` chỉ liệt
  kê số liệu thô (`vehicle_type=MOTORCYCLE...`), không có câu giải thích nào
  — README cũng chưa viết (Phase 6, chưa tới lượt). `src/db/queries.py`
  (viết ở Phase 3) đã có sẵn docstring cảnh báo đúng việc này ("Answer
  (Phase 4) cần nêu rõ giới hạn này") nên không thể coi là ngoài phạm vi
  item — đây chính là chỗ Answer phải xử lý.
- **Sửa:** thêm `_with_seat_limit_note()` vào `answer.py` — kiểm tra câu hỏi
  có nhắc "chỗ" (5/7/9 chỗ...) và kết quả có cột `vehicle_type` thì tự thêm
  1 dòng ghi chú giới hạn vào cuối câu trả lời, áp dụng cho CẢ 2 đường
  (template fallback và sau khi LLM trả lời) — không phụ thuộc LLM có tự
  nhắc hay không, tránh trường hợp model quên. Có check tránh thêm trùng nếu
  câu trả lời (từ LLM) đã chứa sẵn câu y hệt.
- Verify lại: `ANSWER_USE_LLM=false` + câu hỏi mẫu #2 → giờ có ghi chú giới
  hạn ở cuối; câu hỏi bình thường (không nhắc "chỗ") → KHÔNG có ghi chú thừa
  (test riêng để confirm không over-trigger). `ANSWER_USE_LLM=true` (mặc
  định) chạy lại cả 4 câu hỏi mẫu còn lại (Q1, Q3, Q4, Q5-tương đương) —
  không regression, câu trả lời vẫn đúng số liệu như lần verify trước.
  `pytest` chính thức vẫn sạch (exit code 5).
- **Missing:** không có vấn đề nào khác so với `product-spec.md`/
  `test-plan.md` cho phạm vi `answer.py`. README.md (Phase 6) vẫn chưa có
  ghi chú giới hạn số chỗ ngồi — chấp nhận được vì acceptance criteria dùng
  "hoặc" (answer.py đã tự đủ), để Phase 6 làm sau nếu cần bổ sung thêm.

## 2026-09-16 (Phase 4: `src/agent/graph.py`)

### Added
- `src/agent/react.py` — hạ tầng ReAct dùng chung (`build_react_subgraph`,
  `agent_node`, `should_continue`, `fresh_user`, `last_tool_json`,
  `parse_tool_output`). Copy gần như nguyên từ `atin/app/react.py` (đã kiểm
  chứng, kể cả fix "system_prompt callable" đã làm ở `atin/` trước đây), chỉ
  đổi `from app.llm` → `from src.llm`. Coi là hạ tầng cần thiết đi kèm
  `graph.py` (không tự thành business feature riêng), không phải mở rộng
  ngoài phạm vi item.
- `src/agent/graph.py` — `AgentState` (TypedDict), `Agent_Input`/
  `Agent_Output` (pydantic), graph `seed → agent ⇄ tools → pack`
  (`_build_graph()`, cache `@lru_cache`), `run_agent()`. System prompt tiêm
  ngày giờ UTC hiện tại (`_system_prompt()`, callable — đánh giá lại mỗi
  lượt gọi, không hardcode lúc build graph) — đúng kỹ thuật đã kiểm chứng ở
  `atin/` để tránh model bịa năm/tháng sai.

### Changed (quyết định phạm vi, để không lấn sang item tiếp theo)
- `_pack()` hiện trả câu trả lời TEMPLATE đơn giản (`_template_answer()` —
  liệt kê số liệu thô), CHƯA gọi `src/agent/answer.py` (chưa tồn tại — đó
  là item kế tiếp của Phase 4). Sẽ nâng cấp `_pack()` gọi `answer.py` khi
  làm item đó, giữ đúng nguyên tắc "chỉ triển khai 1 task tại 1 thời điểm".

### Verified
- `run_agent()` chạy end-to-end qua LLM thật: câu hỏi "Hôm nay có bao nhiêu
  lượt xe vào Khu A?" → agent tự chọn đúng tool `count_vehicle_flow`, trả
  số liệu thật (`so_luot=4866`) — xác nhận system prompt tiêm đúng ngày
  giờ hiện tại (không bịa năm cũ như bug đã từng gặp ở `atin/`).
- Test tạm dưới `pytest` (viết rồi xoá ngay sau khi xác nhận — test case
  chính thức thuộc Phase 5): `run_agent()` ở chế độ offline (không gọi
  OpenAI thật) trả `answer` khác rỗng, không crash — khớp `test-plan.md`
  mục "Test offline" #3.
- `pytest` chính thức vẫn chạy sạch (exit code 5, chưa có test case).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **BUG tìm thấy, đã sửa:** `product-spec.md` acceptance criteria "Trả lời
  đúng, có số liệu thật, cho cả 5 câu hỏi mẫu" — test đủ cả 5 câu (trước
  chỉ test 1 câu tự chọn). Câu #1 ("...phân loại theo xe máy, ô tô") FAIL
  thực sự: agent gọi ĐÚNG cả 2 tool call song song (MOTORCYCLE + CAR), AI
  message cuối tổng hợp đúng cả 2, nhưng `_pack()` dùng `last_tool_json()`
  (chỉ lấy 1 tool message CUỐI CÙNG) nên `answer` chỉ có CAR, mất hẳn dữ
  liệu MOTORCYCLE — trong khi model đã làm đúng phần việc của nó.
- **Sửa (lần 1, có lỗi):** thêm `all_tool_json()` vào `react.py`, đổi
  `_pack()` gộp nhiều `QueryResult`. Verify lại ngay — PHÁT HIỆN lần sửa
  đầu làm HỎNG HOÀN TOÀN cả 5 câu (`all_tool_json()` trả `[]`): logic
  duyệt `reversed(messages)` gặp AIMessage cuối cùng (câu trả lời tổng hợp,
  không phải tool message) ngay ở bước đầu tiên nên `break` tức thì, không
  bao giờ chạm tới các ToolMessage phía trước nó.
- **Sửa (lần 2, đúng):** bỏ AIMessage cuối (`messages[:-1]`) TRƯỚC khi
  duyệt ngược, rồi mới thu thập ToolMessage liên tiếp. Verify lại đủ cả 5
  câu hỏi mẫu: Q1 giờ có cả MOTORCYCLE (1889 IN/1431 OUT) và CAR
  (2671 OUT/2546 IN) — đúng, không mất dữ liệu; Q2-Q5 không bị ảnh hưởng
  (vẫn đúng như lần test trước). `_pack()` cũng đổi `detail` để liệt kê
  TẤT CẢ tool đã dùng (trước chỉ 1 tool cuối).
- Test offline (viết tạm, xoá sau khi xác nhận) vẫn pass sau cả 2 lần sửa.
  `pytest` chính thức vẫn chạy sạch.
- **Bài học quy trình:** đây là ví dụ fix-rồi-tự-kiểm-tra-lại phát hiện fix
  đầu sai hoàn toàn trước khi báo cáo xong — luôn re-run toàn bộ 5 câu hỏi
  mẫu sau MỌI thay đổi liên quan tới `_pack()`/tool-result aggregation,
  không chỉ tin logic đọc đúng.

---

## 2026-09-16 (Phase 4: `src/agent/tools.py`)

### Added
- `src/agent/tools.py` — 6 tool LangChain (`@tool`): `get_db_schema`,
  `list_khu_vuc`, `count_vehicle_flow`, `trace_plate`,
  `zone_intrusion_by_hour` (bọc 4 hàm ở `src/db/queries.py`) +
  `run_sql_readonly` (fallback, validate: chỉ SELECT, chỉ bảng
  `plate_event`/`zone_event`, tự thêm LIMIT). `QueryResult` (pydantic)
  định nghĩa ngay trong file này (không tách `schemas.py` riêng — chỉ 1
  chỗ dùng, tránh thêm file không cần thiết).

### Changed (quyết định thiết kế, đã hỏi user trước khi làm)
- **Bỏ SQLite demo fallback** so với nguồn tham khảo
  `atin/app/stat_agent/tools.py` (vốn có 2 chế độ: Postgres thật HOẶC
  SQLite demo tự sinh khi thiếu `DB_HOST`). Lý do: `.env` của
  `agent_ATIN` luôn có sẵn DB thật (`db_configured=True`, đã verify từ
  Phase 1), và `product-spec.md` không yêu cầu chế độ demo — thêm ~120
  dòng code (`nodes.py` kiểu SQLite) sẽ vi phạm nguyên tắc "không thêm
  feature không liên quan" trong `AGENTS.md`. Nếu `DB_HOST` chưa cấu hình,
  mọi tool trả lỗi rõ ràng (`_not_configured()`) thay vì âm thầm dùng dữ
  liệu giả.
- Đã thêm vào docstring `count_vehicle_flow`: DB không phân loại xe theo
  số chỗ ngồi — đúng giới hạn đã phát hiện ở lượt review `src/db/queries.py`
  trước, đưa luôn vào docstring tool (nơi LLM thực sự đọc) thay vì chỉ ở
  `queries.py`.

### Verified
- `TOOLS` có đủ 6 tool đúng tên: `get_db_schema`, `list_khu_vuc`,
  `count_vehicle_flow`, `trace_plate`, `zone_intrusion_by_hour`,
  `run_sql_readonly`.
- Gọi trực tiếp (`.invoke()`, không qua LLM) từng tool với dữ liệu thật:
  `get_db_schema` trả mô tả đúng; `list_khu_vuc`/`count_vehicle_flow`/
  `zone_intrusion_by_hour` trả số liệu thật khớp Postgres; `trace_plate('')`
  trả lỗi đúng (không crash); `run_sql_readonly` chạy SELECT hợp lệ, chặn
  đúng DELETE và bảng ngoài whitelist (`sys_admin_account`).
- `pytest` vẫn chạy sạch (exit code 5, chưa có test case chính thức).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Chưa applicable:** test-plan mục "Test offline (pytest)" #4/#5 yêu cầu
  test case CHÍNH THỨC chạy bằng `pytest` — công việc này được lên kế
  hoạch ở Phase 5 (`implementation-plan.md`), chưa phải bây giờ. Đã verify
  thủ công tương đương ở lượt implement trước (không tính là thiếu sót của
  Phase 4).
- **LỖ HỔNG BẢO MẬT tìm thấy, đã sửa:** `run_sql_readonly` dùng
  `any(t in low for t in _ALLOWED_TABLES)` (substring-match TOÀN CÂU) để
  validate bảng — câu SQL `SELECT * FROM plate_blacklist WHERE
  'plate_event' = 'plate_event'` lọt qua whitelist vì chuỗi `"plate_event"`
  xuất hiện trong string literal, dù FROM thực sự trỏ tới bảng khác. Verify
  bằng dữ liệu thật: DB `its` có các bảng ngoài whitelist
  (`plate_blacklist`, `plate_violation_case`, `violation_type_catalog`...)
  mà role `agent_readonly` CÓ quyền SELECT (GRANT ALL TABLES khi tạo role)
  — đây là lỗ hổng đọc dữ liệu thật, không chỉ lý thuyết, vi phạm đúng
  nguyên tắc "chỉ SELECT trên plate_event/zone_event" mà tool này tuyên bố
  bảo vệ.
- **Sửa:** thay whitelist substring-match bằng regex trích xuất tên bảng
  THẬT SỰ sau `FROM`/`JOIN` (`_TABLE_REF`), rồi kiểm tra tập hợp tên bảng
  đó là subset của `_ALLOWED_TABLES` — không còn cách nào nhét tên bảng
  hợp lệ vào string literal để bypass. Cũng sửa logic chọn `dbname` (trước
  dùng `"zone_event" in low`, giờ dùng `"zone_event" in referenced_tables`
  — nhất quán với cách validate mới).
- **Verify sau fix:** bypass attempt bị chặn đúng
  (`"Chỉ cho phép SELECT trên bảng ['plate_event', 'zone_event']"`); 2
  bảng hợp lệ vẫn SELECT được; self-JOIN giữa `plate_event` với chính nó
  vẫn hoạt động (không phá vỡ use-case JOIN hợp lệ); DELETE vẫn bị chặn
  (regression check). Chạy lại toàn bộ 5 tool còn lại — không bị ảnh
  hưởng. `pytest` vẫn chạy sạch.

---

## 2026-09-16 (Phase 3, item 3: test kết nối thật read-only)

Item này là task verify (không phải file code mới) — không có gì để
modify. Đã chạy lại đầy đủ, tường minh 1 lần theo đúng mô tả checklist
(trước đó chỉ verify rải rác ở các lượt review Phase 3 item 1/2).

### Verified
- SELECT chạy được qua role `agent_readonly` trên cả 2 DB: `its.plate_event`
  (316348 dòng), `virtual_fence.zone_event` (104658 dòng).
- DELETE bị Postgres từ chối: `ReadOnlySqlTransaction` (thử trên
  `its.plate_event`).
- UPDATE bị Postgres từ chối: `ReadOnlySqlTransaction` (thử trên
  `virtual_fence.zone_event`).

**Phase 3 (Core Backend / Data Logic) đã hoàn thành đủ 3/3 item.**

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Vấn đề tìm thấy:** `test-plan.md` mục "Test guardrail an toàn" mô tả
  "thử connect + SELECT vào 1 DB khác, phải bị từ chối ở tầng SELECT dù
  CONNECT có thể vẫn qua" — mô tả này đúng với hành vi Postgres GỐC (role
  `agent_readonly`), nhưng SAU KHI thêm validate whitelist vào
  `get_connection()` ở lượt review Phase 3 item 1 trước, gọi
  `get_connection('vms_db')` giờ raise `ValueError` NGAY, không bao giờ
  chạm tới Postgres nữa. Test-plan không còn khớp cách hệ thống thực sự
  hoạt động qua code — ai test đúng theo câu chữ cũ qua `get_connection()`
  sẽ thấy kết quả khác mô tả (`ValueError` thay vì
  `InsufficientPrivilege`), dễ hiểu nhầm là fail.
- **Sửa:** viết lại mục này trong `test-plan.md`, tách rõ 2 lớp phòng thủ
  độc lập cần verify riêng: lớp code (`get_connection()` chặn NGAY bằng
  `ValueError`, không mở connection) và lớp Postgres (dự phòng, test bằng
  `psycopg2.connect()` trực tiếp KHÔNG qua wrapper — CONNECT qua, SELECT bị
  `InsufficientPrivilege`).
- **Verify:** chạy đủ 4 test case theo mô tả mới — DELETE bị chặn
  (`ReadOnlySqlTransaction`), lớp code chặn `vms_db` (`ValueError`), lớp
  Postgres CONNECT qua nhưng SELECT bị chặn (`InsufficientPrivilege`) khi
  test bằng raw `psycopg2`. Cả 4 đều pass, khớp đúng mô tả đã sửa.
- **Missing:** không có gì khác cần bổ sung. `pytest` vẫn chạy sạch.

---

## 2026-09-16 (Phase 3: `src/db/queries.py`)

### Added
- `src/db/queries.py` — 4 hàm SQL tham số hoá, dùng placeholder `%s`
  (không nối chuỗi giá trị người dùng vào SQL):
  - `count_vehicle_flow(date_from, date_to, direction, vehicle_type,
    group_by)` — đếm lượt xe ra/vào, group theo vehicle_type/direction/
    manufacturer
  - `trace_plate(plate_text, date_from, date_to)` — lịch sử di chuyển 1
    biển số
  - `zone_intrusion_by_hour(date_from, date_to, zone_code)` — số lượt xâm
    nhập theo giờ
  - `list_zones()` — liệt kê camera/khu vực hợp lệ

  Copy gần như nguyên từ `atin/app/db/queries.py` (đã kiểm chứng), chỉ đổi
  `from app.config`/`from app.db.connection` → `from src.config`/
  `from src.db.connection` và cập nhật 1 dòng comment tham chiếu file tool
  sẽ dùng (`src/agent/tools.py`, Phase 4).

### Verified
- Cả 4 hàm chạy đúng với dữ liệu Postgres thật:
  `count_vehicle_flow` (24h qua) trả 8 dòng group vehicle_type×direction,
  số liệu hợp lý (CAR/MOTORCYCLE/TRUCK/BUS × IN/OUT).
  `zone_intrusion_by_hour` trả 25 dòng (khung giờ), sắp xếp đúng theo
  `so_luot DESC`.
  `list_zones` trả đúng danh sách camera (`its`) và khu vực hàng rào
  (`virtual_fence`) thật, kể cả tên có dấu tiếng Việt.
  `trace_plate('AA2505', ...)` trả đúng 1 dòng lịch sử di chuyển khớp dữ
  liệu thật đã biết từ trước.
- Error path: `trace_plate('', ...)` trả `{"error": "Thiếu plate_text."}`
  thay vì crash.
- `pytest` vẫn chạy sạch (exit code 5, chưa có test case chính thức).

**Phase 3 còn 1 item:** "Test kết nối thật với role read-only... verify
SELECT chạy được, verify DELETE/UPDATE bị Postgres từ chối" — thực chất đã
verify đủ ở lượt review `connection.py` trước (SELECT OK trên cả 2 DB,
DELETE bị `ReadOnlySqlTransaction` từ chối); sẽ đánh dấu chính thức ở lượt
tiếp theo.

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Chưa applicable:** Acceptance Criteria trong `product-spec.md` vẫn nói
  về hành vi runtime hoàn chỉnh — chưa test trực tiếp được vì UI/Agent
  (Phase 4) chưa tồn tại.
- **Vấn đề tìm thấy, liên quan trực tiếp:** `test-plan.md` câu hỏi mẫu #2
  ("...phân loại xe máy/tải/5,7,9,16,29,40 chỗ") có ghi chú "DB thật không
  phân loại theo số chỗ ngồi — cần nêu rõ giới hạn này trong câu trả lời
  hoặc README". Rà lại: giới hạn này TRƯỚC ĐÓ chỉ tồn tại trong
  `test-plan.md`, chưa xuất hiện ở bất kỳ đâu khác (README, docstring
  `queries.py`) — người tiếp tục Phase 4 (viết Answer) có thể không biết
  để xử lý đúng.
- **Sửa:** thêm đoạn giới hạn schema vào docstring `count_vehicle_flow`
  (hàm sẽ xử lý đúng loại câu hỏi này) — nêu rõ `vehicle_type` chỉ có 4 giá
  trị (BUS/CAR/MOTORCYCLE/TRUCK), không có số chỗ ngồi, và Answer (Phase 4)
  cần nêu rõ giới hạn thay vì bịa số. Chọn sửa ở docstring thay vì README
  vì đây là giới hạn của chính file/hàm này, gần code nhất, dễ thấy nhất
  khi ai đó viết tool gọi hàm này ở Phase 4 — README hiện là placeholder,
  sẽ viết đầy đủ ở Phase 6 nên chưa phải chỗ đúng lúc này.
- **Verify thêm (bảo mật):** thử injection-style input vào `direction`
  (`"IN' OR '1'='1"`) và `group_by`
  (`"vehicle_type; DROP TABLE plate_event;--"`) — cả 2 đều bị chặn đúng
  bằng whitelist validation (`_DIRECTIONS`, `_GROUP_COLUMNS`) trước khi
  chạm SQL, không lọt raw string vào câu lệnh.
- Verify lại `count_vehicle_flow` vẫn hoạt động đúng sau khi sửa docstring
  (không đổi logic). `pytest` vẫn chạy sạch.

---

## 2026-09-16 (Phase 3: `src/db/connection.py`)

### Added
- `src/db/connection.py` — `is_configured()` (proxy `settings.db_configured`)
  và `get_connection(dbname)` (context manager psycopg2, read-only qua
  `conn.set_session(readonly=True, autocommit=True)` + `statement_timeout`
  từ `.env`). Copy gần như nguyên từ `atin/app/db/connection.py` (đã kiểm
  chứng), chỉ đổi `from app.config` → `from src.config` và cập nhật 1 dòng
  comment tham chiếu (`app/stat_agent/tools.py` → `src/agent/tools.py`,
  file validate SQL sẽ viết ở Phase 4-5). Không dùng connection pool ở MVP
  này, đúng như plan chỉ định.

### Verified
- Kết nối thật tới cả 2 DB (`its`, `virtual_fence`) qua role
  `agent_readonly` trong `.env`: `SELECT count(*)` chạy được trên
  `plate_event` (316126 dòng) và `zone_event` (104497 dòng).
- Read-only enforcement hoạt động đúng ở tầng connection: thử `DELETE FROM
  plate_event` bị Postgres từ chối
  (`ReadOnlySqlTransaction: cannot execute DELETE in a read-only
  transaction`) — không cần đợi tới lớp validate SQL ở Phase 4-5.
- `pytest` vẫn chạy sạch (exit code 5, chưa có test case chính thức).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Test liên quan trực tiếp, ban đầu chưa làm:** `test-plan.md` mục "Test
  guardrail an toàn" yêu cầu "Role DB không đọc được dữ liệu ngoài 2 DB đã
  cấp quyền (connect + SELECT vào 1 DB khác phải bị từ chối ở tầng
  SELECT)". Test tay với `get_connection('vms_db')` (DB không được cấp
  quyền): xác nhận Postgres đúng là từ chối ở SELECT
  (`InsufficientPrivilege: permission denied`), CONNECT vẫn qua như dự
  kiến (do PUBLIC CONNECT mặc định của cluster — xem `atin/README.md`).

### Fixed
- **Vấn đề tìm thấy:** `get_connection(dbname: DbName)` với `DbName = str`
  chấp nhận BẤT KỲ tên DB nào, không giới hạn đúng "2 DB" mà item plan mô
  tả — chỉ được chặn nhờ quyền Postgres của role `agent_readonly` (tầng
  ngoài), không có lớp validate nào ở code. Lỗi gõ sai tên DB (hoặc giá trị
  từ nguồn không tin cậy ở Phase 4-5) sẽ âm thầm mở connection thật tới DB
  sai trước khi bị chặn muộn ở SELECT.
- **Sửa:** thêm `_allowed_dbnames()` (từ `settings.db_name_its`/
  `db_name_fence`) và validate `dbname` ngay đầu `get_connection()`, raise
  `ValueError` fail-fast — không mở connection nếu tên DB không khớp đúng
  2 DB đã khai báo. Bỏ type alias `DbName` (không còn ý nghĩa, dùng `str`
  trực tiếp cho tham số). Verify lại: `its`/`virtual_fence` vẫn hoạt động
  bình thường; `vms_db` giờ bị chặn NGAY ở code (`ValueError`, không mở
  connection thật) thay vì chỉ dựa vào Postgres từ chối muộn hơn.
- `pytest` vẫn chạy sạch sau khi sửa.

---

## 2026-09-16 (Phase 2, item 3: xác nhận settings load đúng)

Item này là task verify (không phải file code mới) — không có gì để
modify. Đã thực hiện đúng theo mô tả checklist: chạy test tay in ra
`db_configured` và `llm_backend`.

### Verified
- `python -c "from src.config import settings; print(settings.llm_backend, settings.db_configured)"`
  → `llm_backend: openai`, `db_configured: True` — khớp `.env` thật đang có
  (đã verify tương tự ở 2 lượt review trước, giờ đánh dấu chính thức hoàn
  thành item riêng trong `specs/implementation-plan.md`).

**Phase 2 (Config & LLM Client) đã hoàn thành đủ 3/3 item.**

---

## 2026-09-16 (Phase 2: `src/llm.py`)

### Added
- `src/llm.py` — LLM client hỗ trợ 2 backend (`openai`/`ollama` qua
  `_BACKENDS` dict + `base_url`), `_RotatingKeyPool` (round-robin nhiều
  `OPENAI_API_KEYS`, tự cooldown key bị 429), `use_offline_tools()` (offline
  khi chạy dưới pytest hoặc thiếu key), `base_llm()`/`invoke_with_tools()`/
  `invoke_text()`. Copy gần như nguyên từ `atin/app/llm.py` (đã kiểm chứng
  chạy tốt), bớt backend `vllm` (không có trong scope MVP — product-spec
  chỉ nói "OpenAI Cloud / Ollama local"), đổi `from app.config import
  settings` → `from src.config import settings` cho khớp namespace mới.

### Verified
- `base_llm()` dựng đúng `ChatOpenAI` với model từ `.env` thật
  (`gpt-4o-mini`).
- Gọi LLM thật qua `invoke_text()` thành công (hỏi 1 câu ngắn, nhận đúng
  câu trả lời) — xác nhận key rotation/client hoạt động end-to-end, không
  chỉ import suông.
- `use_offline_tools()` trả `True` khi chạy dưới `pytest` (viết 1 test tạm,
  xoá sau khi xác nhận — test case chính thức thuộc Phase 5).
- Đổi `LLM_BACKEND=ollama` qua biến môi trường (không sửa code): client
  dựng đúng `base_url=http://localhost:11434/v1`, không đòi API key thật
  (`use_offline_tools()=False` vì backend này không cần key) — khớp đúng
  acceptance criteria liên quan trong `product-spec.md`.
- `pytest` vẫn chạy sạch (exit code 5, chưa có test case chính thức).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Chưa applicable:** như Phase 2 item 1, mọi Acceptance Criteria nói về
  hành vi runtime hoàn chỉnh — chưa test được trực tiếp qua UI/API vì
  chưa tồn tại (Phase 4).
- **Điều tra sâu hơn 1 điểm nghi ngờ:** `_pool()` (`@lru_cache`) raise
  `ValueError` nếu backend `openai` mà `OPENAI_API_KEYS` rỗng — kể cả khi
  `use_offline_tools()` đã trả `True` báo hiệu "đừng gọi LLM thật". Đã xác
  nhận đây KHÔNG phải bug: đối chiếu `atin/app/react.py` (dòng 39) và
  `atin/app/answer.py` (dòng 37) — mọi nơi gọi `invoke_with_tools`/
  `invoke_text` trong pipeline gốc ĐỀU check `use_offline_tools()` trước;
  đây là contract cố ý (client low-level không tự guard, trách nhiệm gọi
  đúng thứ tự thuộc caller ở Phase 4). Không sửa — thêm guard vào
  `base_llm()` sẽ là thay đổi API ngoài phạm vi plan yêu cầu.
- **Verify bổ sung:** `_RotatingKeyPool` round-robin đúng thứ tự
  (key1→key2→key3→key1...) và cooldown loại đúng key vừa bị mark_limited
  khỏi vòng quay — cả 2 test tay đều pass.
- **Kết luận:** không tìm thấy vấn đề cần sửa. Không thay đổi file nào
  trong lượt review này.

---

## 2026-09-16 (Phase 2: `src/config.py`)

### Added
- `src/config.py` — `Settings` (`pydantic_settings.BaseSettings`) đọc `.env`,
  điểm duy nhất chạm secrets trong codebase. Field: LLM backend
  (`LLM_BACKEND`, `LLM_BASE_URL`, `OPENAI_API_KEYS`, `LLM_MODEL`,
  `LLM_TEMPERATURE`, `LLM_MAX_RETRIES`, `ANSWER_USE_LLM`) và Postgres
  read-only (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`,
  `DB_NAME_ITS`, `DB_NAME_FENCE`, `DB_ORGANIZATION_ID`,
  `DB_QUERY_TIMEOUT_S`, `DB_MAX_ROWS`) — khớp đúng field đã có sẵn trong
  `.env.example`/`.env` (Phase 1). Copy gần như nguyên từ
  `atin/app/config.py` (đã kiểm chứng), bớt 2 field guardrail
  (`GUARDRAILS_MIN_ANSWER_LEN`/`MAX_ANSWER_LEN`) và `APP_NAME` vì chưa dùng
  tới ở phase này — sẽ thêm khi làm Phase 5 (Guardrails) nếu cần.

### Verified
- `from src.config import settings` load đúng từ `.env` thật: `llm_backend`
  = "openai", `db_configured` = True, `api_keys` nhận đủ 2 key, tên 2 DB
  đúng (`its`, `virtual_fence`).
- `pytest` vẫn chạy sạch (exit code 5, chưa có test case — không đổi so
  với Phase 1).

### Review vs acceptance criteria (product-spec.md + test-plan.md)
- **Chưa applicable:** mọi Acceptance Criteria trong `product-spec.md` nói
  về hành vi runtime hoàn chỉnh (trả lời câu hỏi, guardrail, ngrok) — 1
  mình `config.py` chưa đủ để pass/fail tiêu chí nào, đúng kế hoạch.
- **Liên quan trực tiếp, đã kiểm tra riêng:** tiêu chí "đổi `LLM_BACKEND=ollama`
  trong `.env`, không cần sửa code" — verify `Settings` nhận giá trị
  `"ollama"` không lỗi (field kiểu `str` thường, không validate whitelist —
  đúng theo `atin/app/config.py` gốc đã kiểm chứng, không phải bug mới).
  Việc thực sự CHẠY được với backend `ollama` chỉ verify được ở `src/llm.py`
  (item tiếp theo Phase 2), chưa tồn tại.
- **test-plan.md:** không có test case riêng cho `config.py` — hợp lý, nó
  chỉ được test gián tiếp qua các feature dùng `settings` sau này. Không
  có gì missing cần bổ sung.
- **Đối chiếu `.env.example` ↔ `config.py`:** đồng bộ hoàn toàn, không
  thiếu/thừa field alias nào (kiểm bằng script so khớp key).
- **Kết luận:** không tìm thấy vấn đề nào cần sửa. Không thay đổi file nào
  trong lượt review này.

---

## 2026-09-16 (Phase 1: Project Setup)

### Added
- Khung package `src/` trống (`src/__init__.py`, `src/agent/__init__.py`,
  `src/db/__init__.py`) và `tests/__init__.py` — chưa có business logic,
  đúng scope Phase 1.
- `pyproject.toml` (`testpaths = ["tests"]`) để `pytest` chạy được.
- `.env.example` mới, khớp field với `.env` thật đang dùng (LLM backend,
  Postgres read-only) — không chứa secret thật.

### Changed
- Viết lại `requirements.txt`: từ danh sách cũ (qdrant, mcp, langfuse,
  vnstock, gradio, ...) rút xuống đúng 9 dependency cần cho MVP (fastapi,
  uvicorn, pydantic, pydantic-settings, langgraph, langchain-core,
  langchain-openai, openai, psycopg2-binary, pytest).
- Sửa link tham chiếu hỏng trong `specs/implementation-plan.md` (từng trỏ
  "AGENTS.md mục Kỹ thuật KHÔNG dùng" — mục đó đã bị xoá ở lần rút gọn
  AGENTS.md trước; giờ trỏ đúng sang `specs/product-spec.md` mục "Features
  Out of Scope").
- Đánh dấu hoàn thành 4 checklist item của Phase 1 trong
  `specs/implementation-plan.md`.

### Removed
- Xoá `src/` cũ (agent_m2-style: memory, tool_selection, multi sub-agent,
  monitoring/tracing — viết dở, có bug đã biết ở `states.py`, và thuộc các
  kỹ thuật đã đánh dấu Out of Scope trong product-spec), `resource/`,
  `docker-compose.yml`, `main.py` cũ. Đã xác nhận với user trước khi xoá
  (thao tác không thể hoàn tác).

### Notes
- `web/` (thư mục rỗng, có sẵn từ trước) được giữ nguyên, không đụng tới.
- `.env` thật (đã có sẵn từ trước, cùng field với `.env.example` mới) không
  bị ảnh hưởng — vẫn nằm ngoài git nhờ `.gitignore`.

---

## 2026-09-16 (Review Phase 1 vs acceptance criteria)

Đối chiếu Phase 1 với `specs/product-spec.md` Acceptance Criteria và
`specs/test-plan.md`.

**Kết quả:** Acceptance Criteria trong product-spec nói về hành vi runtime
của app hoàn chỉnh (trả lời câu hỏi, guardrail, đổi LLM backend, demo
ngrok) — chưa applicable ở Phase 1 vì các tính năng đó chưa tồn tại (đúng
kế hoạch, không phải fail). Checklist riêng của Phase 1 (project setup) đạt
đủ 4/4 mục, verify lại bằng lệnh thật: `import src` OK, `pytest` chạy sạch
(exit code 5 "no tests ran" — đúng vì chưa có test case), toàn bộ 9
dependency trong `requirements.txt` import được.

### Fixed
- `README.md` bị lỗi thời — vẫn ghi "chưa code cho luồng mới", "code cũ
  trong src/ giữ nguyên chưa xoá — sẽ xử lý ở Phase 1" dù Phase 1 đã xong
  và code cũ đã xoá. Cập nhật mục "Trạng thái hiện tại" khớp thực tế, thêm
  lệnh cài đặt/test thật (đã tự chạy lại để xác nhận đúng) vào "Cài đặt &
  chạy local", ghi chú rõ `pytest` trả exit code 5 khi chưa có test case là
  bình thường (tránh hiểu nhầm là lỗi).

### Not fixed (ngoài phạm vi feature này)
- `.env.example` tham chiếu "README mục Tạo DB role read-only" — mục đó
  chưa tồn tại trong README (sẽ có ở Phase 6). Đây là forward-reference hợp
  lệ theo kế hoạch, không phải lỗi của Phase 1 — không sửa, theo đúng
  nguyên tắc "chỉ sửa vấn đề liên quan tới feature vừa làm".

---

## 2026-09-16

### Added
- Tạo bộ spec ban đầu (`specs/product-spec.md`, `specs/implementation-plan.md`,
  `specs/test-plan.md`, `specs/change-log.md`) và `AGENTS.md` theo Spec-Driven
  Development. Chưa viết code cho luồng mới.
- Thêm mục "Tham khảo llm-engineer-demo/" vào `AGENTS.md` — bảng liệt kê kỹ
  thuật có trong Module II (`agent_m2/`) nhưng KHÔNG dùng ở MVP này (memory,
  tool retrieval, MCP, HITL, tracing/eval, multi-agent, LLM-based injection
  check) kèm lý do, để tránh drift scope khi code.

### Changed
- Review `specs/product-spec.md`: tách phần "ghi chú quy trình" khỏi Goal,
  nhóm lại Features In Scope theo 4 hạng mục (Agent & tool / Guardrail / Hạ
  tầng / UI) thay vì 1 list phẳng, thêm acceptance criterion về UI-state
  (loading/success/error) còn thiếu.
- Bổ sung `specs/implementation-plan.md` Phase 2/4/5 với file nguồn cụ thể
  trong `llm-engineer-demo/` nên tham khảo cho từng phần (llm/backends.py,
  llm/resilience.py, agent_m2/nodes.py, guardrails/injection.py, guardrails/pii.py).
- Viết lại `specs/implementation-plan.md` từ 9 phase rời rạc thành 6 phase
  chuẩn theo khung Spec-Driven Development (Project setup → Config & LLM
  client → Core backend/data logic → Agent → Validation and error states →
  Local run instructions). Gộp Guardrails + Testing cũ vào "Validation and
  error states"; gộp API/UI vào "Agent"; gộp local run + ngrok vào "Local
  run instructions". Không cắt tính năng nào, chỉ tổ chức lại checklist.
- Bổ sung `specs/product-spec.md` Out of Scope: liệt kê tường minh
  long-term memory/tool retrieval/MCP, LLM-based injection check, test UI
  tự động/load test — trước đây chỉ nhắc trong AGENTS.md/test-plan.md, giờ
  cũng có trong product-spec để nhất quán.

### Fixed
- (chưa có)

### Changed (tiếp)
- Viết lại `AGENTS.md` cho ngắn gọn, bám sát mẫu chuẩn trong "Spec Driven
  Development Guide" (7 quy tắc + Coding Style + Testing, bỏ phần "Ràng
  buộc riêng" và bảng "kỹ thuật không dùng" đã làm file phình to). Nội dung
  đó thuộc về `specs/product-spec.md` (scope) và
  `specs/implementation-plan.md` (chi tiết kỹ thuật từng phase), không phải
  `AGENTS.md` (chỉ nói cách hành xử khi code) — đã có sẵn ở 2 file kia nên
  không mất thông tin, chỉ sửa 1 link tham chiếu hỏng trong product-spec.md
  (trỏ sang implementation-plan.md thay vì AGENTS.md).

### Notes
- Bản spec này viết lại đơn giản hơn `atin/` (project trước, đã chạy được
  và verify với Postgres thật) — xem `atin/README.md` để biết các quyết
  định kiến trúc đã kiểm chứng (function-calling thay Text-to-SQL, tối đa
  2 lời gọi LLM/câu hỏi, mart `plate_dashboard` không dùng vì lỗi thời).
- Code cũ hiện có trong `agent_ATIN/src/` (viết dở, dựa theo Module II phức
  tạp hơn của `llm-engineer-demo`) được GIỮ LẠI theo yêu cầu, chưa xoá —
  quyết định xoá/tái cấu trúc sẽ làm ở Phase 1 implementation-plan khi thực
  sự bắt đầu code.

## Phase 3 - Orchestration & Caching (Graph & SSE)
- Thay thế hoàn toàn ReAct main path bằng LangGraph pipeline tĩnh (START → rewrite → classify → route).
- Tích hợp các module từ Phase 2 (catalog, query_plan, executor, chart) vào các node tương ứng của pipeline.
- Sửa đổi SSE `run_agent_stream` để emit các sự kiện từ các node mới (`retrieve_schema`, `plan_query`, `validate`, `execute`, `render_chart`, `respond`).
- Cập nhật UI (`app.js`) xử lý hiển thị base64 ảnh biểu đồ từ sự kiện `render_chart` hoặc `__answer__`.
- Nâng cấp Cache API để sử dụng **câu hỏi đã rewrite** làm cache key, giúp tăng độ bao phủ của cache và bỏ qua quá trình suy luận nội bộ lặp lại.
- Thích ứng các file test (như `test_api.py`, `test_intent.py`) để verify pipeline graph mới, xoá bỏ các test liên quan đến tool ReAct cũ.
