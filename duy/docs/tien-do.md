# Local AI Agent — Tiến độ & Lịch sử thực hiện

Tài liệu này ghi nhận **đang làm tới đâu**, **đã xong gì**, và **lịch sử chỉnh sửa**.

Mục tiêu, kiến trúc và các phase nằm ở [`muc-tieu.md`](./muc-tieu.md). Kết nối PostgreSQL: [`ket-noi-db.md`](./ket-noi-db.md). Tổ chức code: [`base_code.md`](./base_code.md). Khi hoàn thành một việc hoặc đổi hướng, cập nhật bảng trạng thái rồi thêm một dòng vào phần Lịch sử.

---

## 1. Trạng thái hiện tại

| Mục | Giá trị |
|-----|---------|
| Runtime đã chốt | **LangGraph** + Local LLM (**Ollama**) |
| LLM đã chốt | **Qwen 8B** — tag Ollama `qwen3-16k-nothink` (không dùng `qwen3:8b` / `qwen3-16k` bản thinking) |
| PostgreSQL đã chốt | `192.168.1.200:18644` user `vinhdq` (read-only), nhiều DB — xem [`ket-noi-db.md`](./ket-noi-db.md) |
| Phase đang làm | 6 — Hỏi đáp DB (đang chỉnh SQL cho khớp giá trị thật) |
| Tổ chức code | Pipeline đã có trong `src/agent/` — [`base_code.md`](./base_code.md) |
| Phase gần nhất đã xong | 1–5; GRANT SELECT đã cấp; schema lấy `sample_values` |
| Kết quả kiểm chứng gần nhất | Chart: `Vẽ biểu đồ số lượng xe theo loại` → bar PNG từ plate_event. |
| Ghi chú | matplotlib render PNG base64; UI hiện ảnh. Restart API nếu cần. |

**Việc tiếp theo**

- Restart `agent-serve` nếu UI vẫn dùng process cũ.
- Chạy thêm bộ câu hỏi MVP (event tháng 8, top camera, violation).
- Không commit `.env`

---

## 2. Checklist phase

Trạng thái dùng: `chưa làm` · `đang làm` · `xong` · `tạm hoãn` · `không dùng`

### MVP

| Phase | Tên | Trạng thái | Ghi chú |
|-------|-----|------------|---------|
| 1 | Dựng Local LLM | xong | Ollama + `qwen3-16k-nothink`; ping 5.5s |
| 2 | Dựng LangGraph Agent | xong | Pipeline cố định trong `src/agent/graph/` |
| 3 | PostgreSQL Connection | xong | `SELECT 1` `.200:18644` user `vinhdq` |
| 4 | PostgreSQL Tool | xong (chưa MCP) | `schema` / `query` / `validator`; MCP để sau |
| 5 | SQL Safety | xong | Unit test PASS/REJECT |
| 6 | LangGraph + PostgreSQL | đang làm | SELECT được; đang chỉnh retrieval/SQL cho đúng bảng-cột |

### Sau MVP

| Phase | Tên | Trạng thái | Ghi chú |
|-------|-----|------------|---------|
| 7 | Data Analysis | chưa làm | SQL → DataFrame → Pandas |
| 8 | Chart Agent | chưa làm | Bar / line / time-series → PNG |
| 9 | Schema Retrieval | chưa làm | Chỉ gửi bảng liên quan cho LLM |
| 10 | Context & Memory | chưa làm | Hội thoại nhiều lượt, schema cache |
| 11 | Evaluation | chưa làm | `tests/questions.json` |

### Cuối cùng

| Phase | Tên | Trạng thái | Ghi chú |
|-------|-----|------------|---------|
| 12 | AI Operations Agent | chưa làm | Camera / VMS / Internal API MCP |
| 13 | Report Agent | chưa làm | PDF / Excel / Markdown |
| — | File MCP | chưa làm | Sau Operations/Report |
| — | Production hardening | chưa làm | Sau khi các MCP nền tảng ổn |

### Quyết định kiến trúc (đã chốt 2026-09-14)

| Thành phần | Chọn | Không chọn | Lý do |
|------------|------|------------|--------|
| Điều phối Agent | **LangGraph** | Hermes, LocalHarness | Cần ép luồng `schema → SQL → validator → query`; validator không được bypass |
| Inference | **Ollama** + **Qwen 8B** (`qwen3-16k-nothink`) | Cloud LLM; `qwen3:4b`; `qwen3:8b` thinking | 8B vừa đủ NL→SQL trên 16GB; bản nothink tránh thinking làm chậm/rối |
| PostgreSQL | **`192.168.1.200:18644`** user `vinhdq` | `127.0.0.1:5429` (VMS local) | Cùng DB production với `vinhqd/agent`; account đã read-only |
| Tool | Python tool / MCP gắn vào graph | Agent tự chạy shell / `psql` | Permission và SQL safety nằm trong code, không nhờ model tự hạn chế |

Hermes và LocalHarness là **harness generic** (ReAct + tool). Hợp assistant đa năng, không hợp Data/Ops Agent theo spec riêng.

### Không dùng cho runtime

| Hạng mục | Trạng thái | Ghi chú |
|----------|------------|---------|
| Hermes Agent | không dùng | Đã cài v0.21.1; product harness, không ép được SQL pipeline |
| LocalHarness | không dùng | Agent layer YAML trên Ollama/vLLM; cùng nhóm harness generic, pre-1.0 |
| Cloud LLM (OpenAI / Anthropic / OpenRouter) | không dùng | Inference chỉ local |
| Postgres VMS local `127.0.0.1:5429` | không dùng | DB khác; Agent này dùng `.200:18644` |

---

## 3. Checklist chi tiết (cập nhật khi làm)

### Phase 1 — Dựng Local LLM

- [x] Inference server: Ollama Docker `127.0.0.1:11434` (đã có trên máy)
- [x] Model đã pull: `qwen3-16k-nothink` (Qwen 8B, ctx 16k, tắt thinking)
- [x] Test inference từ project `duy` (`uv run agent llm-ping`)
- [x] Test hỏi đáp tiếng Việt (`1 + 1 bằng 2.`)
- [x] Kiểm tra GPU memory và tốc độ (~5.5s / câu ngắn)
- [x] Test OpenAI-compatible API `/v1/chat/completions`

### Phase 2 — Dựng LangGraph Agent

- [x] LangGraph state (`graph/state.py`)
- [x] Pipeline nodes: retrieve_schema → generate_sql → validate_sql → execute_sql → respond
- [x] Basic agent loop (graph.compile)
- [x] Tool postgres (schema/query/validator) gọi từ node
- [x] Error handling (REJECT → repair; permission denied → answer)

### Phase 3 — PostgreSQL Connection

Nguồn: [`ket-noi-db.md`](./ket-noi-db.md) — `192.168.1.200:18644`, user `vinhdq`.

- [x] Tạo project / cấu trúc thư mục
- [x] Tạo `.env` (`DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD`, không commit password)
- [x] Cài PostgreSQL Python driver (`psycopg`)
- [x] Connection pool
- [x] Connection timeout
- [x] Test `SELECT 1` tới `.200:18644`
- [ ] User `vinhdq` CONNECT được nhưng **chưa có GRANT SELECT** trên bảng nghiệp vụ — cần DBA

### Phase 4 — PostgreSQL Tool / MCP

- [x] `get_schema()` / `list_tables()` — qua `pg_catalog` (information_schema trống với user này)
- [x] `describe_table()`
- [x] `query()` — chỉ đọc, đi qua validator
- [ ] MCP server — sau MVP

### Phase 5 — SQL Safety

- [x] Chỉ cho phép `SELECT` / `WITH`
- [x] Block `INSERT` / `UPDATE` / `DELETE`
- [x] Block `DROP` / `ALTER` / `TRUNCATE`
- [x] Block `CREATE` / `GRANT` / `REVOKE` (token `GRANT`/`REVOKE`)
- [x] Không cho multi-statement
- [x] Query timeout
- [x] Connection timeout
- [x] Row limit
- [x] Result-size limit
- [x] Không cho Agent truy cập shell / `psql`

### Phase 6 — LangGraph + PostgreSQL (MVP)

- [x] Nối postgres tools vào LangGraph pipeline
- [ ] Test: Có bao nhiêu camera? — chờ GRANT SELECT
- [ ] Test: Có bao nhiêu camera đang hoạt động?
- [ ] Test: Top 10 camera có nhiều event nhất?
- [ ] Test: Có bao nhiêu event trong tháng 8?
- [ ] Test: Camera nào có nhiều event nhất?
- [ ] Test: Có bao nhiêu vehicle event theo từng ngày?
- [ ] Test: Camera nào có nhiều violation nhất?
- [ ] Test: Camera nào có nhiều event nhất?
- [ ] Test: Có bao nhiêu vehicle event theo từng ngày?
- [ ] Test: Camera nào có nhiều violation nhất?

### Phase 7 — Data Analysis

- [ ] Group by
- [ ] Aggregation
- [ ] Filter
- [ ] Sort
- [ ] Statistics
- [ ] Comparison
- [ ] Time-series
- [ ] Top-N

### Phase 8 — Chart Agent

- [ ] `create_bar_chart()`
- [ ] `create_line_chart()`
- [ ] `create_time_series_chart()`

### Phase 9–13

- [ ] Schema retrieval theo câu hỏi
- [ ] Conversation history + context + memory
- [ ] Bộ câu hỏi evaluation + đo % đúng
- [ ] MCP Camera / VMS / Internal API
- [ ] File MCP
- [ ] Report Agent (PDF / Excel / Markdown)

---

## 4. Cách ghi nhận

Mỗi lần có thay đổi đáng kể, thêm một mục vào **Lịch sử** theo mẫu:

```md
### YYYY-MM-DD — tiêu đề ngắn

- Phase: N
- Loại: khởi tạo | triển khai | sửa | đổi hướng | hoàn thành
- Đã làm: ...
- Kết quả / kiểm chứng: ...
- Việc tiếp theo: ...
```

Quy ước:

- Đổi trạng thái phase trong bảng mục 2 ngay khi bắt đầu hoặc kết thúc.
- Tick checklist mục 3 khi việc đó đã kiểm chứng được, không chỉ mới viết code.
- Nếu đổi quyết định so với [`muc-tieu.md`](./muc-tieu.md), ghi rõ lý do trong lịch sử và cập nhật luôn file mục tiêu.

---

## 5. Lịch sử thực hiện

### 2026-09-16 — Hỏi đáp hướng dẫn VMS từ VMS_doc

- Phase: 6+
- Loại: triển khai
- Đã làm: loader `index.yaml` + retrieve card; intent `how_to`/`troubleshoot`/`concept`; node `retrieve_docs` → `answer_from_docs`; UI hiện nguồn card.
- Kết quả / kiểm chứng: unit retrieve `devices.add_camera`, `troubleshooting.live_stream_unavailable`.
- Việc tiếp theo: restart API; eval thêm câu hướng dẫn.

### 2026-09-16 — Giảm latency (gộp intent, skip tóm tắt, SSE)

- Phase: 6
- Loại: tối ưu
- Đã làm: classify trả `answer` luôn khi không query; bỏ LLM tóm tắt cho COUNT đơn giản; `max_tokens`; SSE `POST /ask/stream` + UI hiển thị status/answer sớm.
- Kết quả / kiểm chứng: pytest 43 passed; camera COUNT format thẳng không gọi respond LLM.
- Việc tiếp theo: giữ Ollama warm (`keep_alive`).

### 2026-09-16 — Intent LLM trước khi SQL

- Phase: 6
- Loại: triển khai
- Đã làm: node `classify_intent` (LLM) → `query_db` mới vào pipeline SQL; `chat`/`clarify`/`out_of_scope` trả lời không query. UI hiện intent, loading không mặc định “đang SQL”.
- Kết quả / kiểm chứng: `xin chào` → intent=chat, sql rỗng; pytest intent parser.
- Việc tiếp theo: restart `agent-serve` để UI nhận code mới.

### 2026-09-16 — Routing domain xe + cảnh báo kết quả rỗng

- Phase: 6
- Loại: sửa
- Đã làm: rule ép `its.plate_events` cho ô tô/xe máy; tokenizer cụm VN; bỏ alias `ra vào` trần của face; prompt `vehicle_type` CAR/MOTORCYCLE; respond cảnh báo khi 0; eval routing pack.
- Kết quả / kiểm chứng: pytest **37 passed**; hỏi ngày 13/09 ô tô/xe máy không còn vào `smf_face_events`.
- Việc tiếp theo: restart API UI nếu cần.

### 2026-09-16 — Giao diện React hỏi đáp

- Phase: 6 (UI phụ)
- Loại: triển khai
- Đã làm: FastAPI `src/agent/api.py` + `agent-serve`; Vite React `web/` (nền sáng, brand DUY, form hỏi, hiện answer/SQL).
- Kết quả / kiểm chứng: build TypeScript OK; proxy `/api` → `:8000`.
- Việc tiếp theo: bộ câu hỏi MVP còn lại.

### 2026-09-16 — SQL camera phương tiện không trộn cột `camera_code`

- Phase: 6
- Loại: sửa
- Đã làm:
  - Retrieval: khớp cụm từ alias; chỉ giữ bảng cùng DB và điểm gần hit cao nhất (không JOIN cross-DB).
  - Validator: từ chối bảng ngoài schema và cột lấy từ bảng khác (`camera_code` trên `FROM camera`).
  - Graph: lỗi execute cũng vào `repair_sql`.
  - Catalog/prompt: đếm camera phương tiện = `plate_event.camera_code`; bảng `camera` dùng cột `code`.
- Kết quả / kiểm chứng: `ask "Có bao nhiêu camera phương tiện?"` → **3** camera (`CAM_01/02/03`). `ask "Có bao nhiêu camera đang hoạt động?"` vẫn **6**. pytest **29 passed**.
- Việc tiếp theo: bộ câu hỏi MVP còn lại.

### 2026-09-16 — SQL camera dùng status thật từ DB (`ONLINE`)

- Phase: 6
- Loại: sửa
- Đã làm:
  - `describe_table` lấy `sample_values` cho cột phân loại (`status`, …).
  - Prompt: không bịa `active` nếu không có trong sample_values; "đang hoạt động" → `ONLINE`.
- Kết quả / kiểm chứng: DB 6/6 camera `ONLINE`. `ask "Có bao nhiêu camera đang hoạt động?"` → `WHERE status = 'ONLINE'` → **6**. pytest 26 passed.
- Việc tiếp theo: chạy thêm câu hỏi MVP (event, violation).

### 2026-09-14 — Scaffold + test LLM/DB; bị chặn GRANT SELECT

- Phase: 1–6
- Loại: triển khai
- Đã làm:
  - Tạo project `src/agent/`, `pyproject.toml`, `.env` / `.env.example`, pytest.
  - `uv run agent llm-ping`: `qwen3-16k-nothink`, ~5.5s, trả lời tiếng Việt đúng.
  - `uv run agent db-ping`: `SELECT 1`, user `vinhdq`, database `postgres`.
  - SQL validator + LangGraph pipeline; `ask` sinh `SELECT COUNT(*) FROM anomaly_event ...` (PASS validator).
  - Schema đọc qua `pg_catalog` (information_schema trống với user này). Ẩn cột password/stream khỏi schema excerpt.
- Kết quả / kiểm chứng: pytest **22 passed**. Execute bảng nghiệp vụ: `permission denied for table anomaly_event` / `camera`. `has_table_privilege(..., SELECT) = false`.
- Việc tiếp theo: GRANT SELECT cho `vinhdq` trên từng DB, rồi chạy lại bộ câu hỏi MVP.

### 2026-09-14 — Chốt LLM Qwen 8B (`qwen3-16k-nothink`)

- Phase: 1 (chốt model, chưa test từ `duy`)
- Loại: đổi hướng
- Đã làm:
  - Chọn **Qwen 8B** — vừa đủ cho NL→SQL trên RTX 4060 Ti 16GB.
  - Tag Ollama: `qwen3-16k-nothink` (đã có trên máy). Không dùng `qwen3:4b`. Không dùng `qwen3:8b` / `qwen3-16k` (thinking).
  - Inference: **Ollama** có sẵn, không cần vLLM lúc này.
  - Cập nhật [`tien-do.md`](./tien-do.md), [`base_code.md`](./base_code.md), [`muc-tieu.md`](./muc-tieu.md).
- Kết quả / kiểm chứng: Quyết định đã chốt. Chưa gọi model từ project `duy`.
- Việc tiếp theo: Scaffold `.env` + test `/v1/chat/completions` với `qwen3-16k-nothink`.

### 2026-09-14 — Chỉnh tổ chức code (pipeline, không ReAct)

- Phase: — (docs only)
- Loại: sửa
- Đã làm:
  - Viết lại [`base_code.md`](./base_code.md): graph MVP là pipeline `retrieve_schema → generate_sql → validate_sql → execute_sql → respond` (+ `repair_sql`), không dùng node ReAct `agent/tool/response`.
  - Thêm `catalog/` và `services/connection.py` cho multi-DB `.200:18644`.
  - Env đổi sang `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` — bỏ `POSTGRES_DB` cố định.
  - Validator hai lớp (node graph + `query.py`). `query_service` không execute SQL chưa validate.
  - MCP / analytics / chart / camera không nằm trong cây MVP.
  - Dependency: `langgraph` + `langchain-core` + `langchain-openai`, không `langchain` full.
- Kết quả / kiểm chứng: Tài liệu khớp `muc-tieu.md` và `ket-noi-db.md`. Chưa scaffold source.
- Việc tiếp theo: Phase 1 Local LLM, hoặc scaffold cây MVP trong `src/agent/`.

### 2026-09-14 — Chốt PostgreSQL `192.168.1.200:18644`

- Phase: 3 (mới chốt nguồn, chưa test connection từ `duy`)
- Loại: đổi hướng
- Đã làm:
  - Chọn cùng Postgres với `vinhqd/agent`: host `192.168.1.200`, port `18644`, user `vinhdq` (read-only).
  - Không cố định 1 database — query theo DB nghiệp vụ (`anomaly`, `smart_face`, `its`, `vms_db`, …).
  - Tạo [`ket-noi-db.md`](./ket-noi-db.md). Cập nhật [`muc-tieu.md`](./muc-tieu.md) Phase 3.
  - Password không ghi vào markdown; copy từ `~/vinhqd/agent/.env` khi tạo `.env` project.
  - Không dùng Postgres local VMS `127.0.0.1:5429`.
- Kết quả / kiểm chứng: Đã chốt trên giấy. Chưa chạy `SELECT 1` từ `~/duy`.
- Việc tiếp theo: Phase 1 Local LLM; Phase 3 khi nối DB thì tạo `.env` và test kết nối.

### 2026-09-14 — Chốt runtime LangGraph (không dùng harness)

- Phase: — (chưa implementation)
- Loại: đổi hướng
- Đã làm:
  - So sánh LangGraph vs Hermes vs LocalHarness cho agent theo yêu cầu riêng.
  - Xác nhận giữ hướng [`muc-tieu.md`](./muc-tieu.md): LangGraph điều phối, Local LLM suy luận, Tool/MCP hành động.
  - Ghi nhận Hermes / LocalHarness là harness generic — không dùng làm runtime Data/Ops Agent.
  - Cập nhật trạng thái hiện tại, bảng quyết định kiến trúc, và danh sách “không dùng”.
- Kết quả / kiểm chứng: Quyết định đã chốt trên giấy. Chưa clone LocalHarness (lệnh `uv run localharness` trong `~/duy` thất bại vì chưa có project). Không cần cài harness để làm MVP.
- Việc tiếp theo: Phase 1 — Dựng Local LLM.

### 2026-09-14 — Đổi hướng: LangGraph + Local LLM

- Phase: — (vẫn chưa implementation theo roadmap mới)
- Loại: đổi hướng
- Đã làm:
  - Cập nhật `docs/muc-tieu.md`: runtime **LangGraph**, inference **local (vLLM/Ollama)**, nguyên tắc privacy/self-hosted.
  - Bỏ Hermes / OpenAI / Anthropic / OpenRouter khỏi kiến trúc mục tiêu.
  - Tái cấu trúc 13 phase; MVP bắt đầu từ Local LLM → LangGraph → PostgreSQL.
  - SQL Safety bổ sung block `CREATE` / `GRANT` / `REVOKE`, cấm multi-statement.
  - Bộ test MVP thêm vehicle event theo ngày và camera có nhiều violation nhất.
  - Đồng bộ checklist trong file này với roadmap mới.
- Kết quả / kiểm chứng: Tài liệu đã khớp hướng mới. Hermes vẫn còn trên máy (v0.21.1) nhưng không dùng cho runtime. Ollama/GPU đã có sẵn, chưa chọn model chính thức cho Agent.
- Việc tiếp theo: Phase 1 — Dựng Local LLM (chọn vLLM hoặc Ollama, load model, test tiếng Việt).

### 2026-09-11 — Tạo tài liệu mục tiêu và tiến độ

- Phase: — (chưa vào implementation)
- Loại: khởi tạo
- Đã làm:
  - Tạo `docs/muc-tieu.md` bản đầu: Hermes Agent + MCP, 12 phase.
  - Tạo `docs/tien-do.md`.
- Kết quả / kiểm chứng: Tài liệu sẵn sàng. Sau đó Hermes được cài local (v0.21.1), nhưng hướng này đã bị thay.
- Việc tiếp theo (lúc đó): Phase 1 — Dựng Hermes. **Đã hủy** ngày 2026-09-14.
