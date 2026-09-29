# Implementation Plan — agent dong v9: Unified Memory & Context Engineering System (Postgres-backed)

**Trạng thái:** 100% Hoàn thành — Toàn bộ 7 Phase của agent dong v9 đã được triển khai, kiểm thử và nghiệm thu thành công.  
**Nguồn:** `specs/product-spec.md`  
**Quy tắc:** Thực hiện tuần tự từng dòng `[ ]` một, kiểm tra kỹ lưỡng, sau đó đổi thành `[x]` và cập nhật `specs/change-log.md`. Không implement hàng loạt nhiều bước cùng lúc. Không viết code khi chưa có yêu cầu.

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

