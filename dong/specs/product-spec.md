# Product Spec — agent dong v9: Unified Memory & Context Engineering System (Postgres-backed)

**Trạng thái:** Spec Approved — Sẵn sàng triển khai tuần tự.  
**Baseline:** v8 đang chạy ổn định (Text-to-SQL Postgres read-only, 10 Camera Registry, Human Feedback, Chunk Streaming SSE).  
**Triết lý:** Đơn giản, tinh gọn, tập trung tối đa vào MVP theo chuẩn Spec-Driven Development.

---

## 1. App Goal

Xây dựng và chuẩn hóa hệ thống **Memory & Context Engineering** tinh gọn, bền vững cho multi-agent VMS KCN Hưng Phú dựa trên kiến trúc của `llm-engineer-demo`:

1. **Bền vững hóa dữ liệu (PostgreSQL Persistence)**: Lưu trữ các sự thật (facts) dài hạn của người dùng vào bảng `user_memories` trong PostgreSQL, khắc phục tình trạng mất dữ liệu khi restart container.
2. **Tối ưu hóa ngữ cảnh (Context Engineering)**: Áp dụng kỹ thuật Sliding Window, ước lượng token theo nguyên tắc 40-60% (chủ động tóm tắt trước khi suy giảm chất lượng), nén kết quả tool dài, và tái chèn chỉ dẫn cốt lõi ở cuối prompt chống trôi quy tắc.
3. **Bộ đệm phản hồi tức thì (TTL Cache)**: Lưu tạm câu trả lời theo mã băm SHA-256 trong 300s, phản hồi tức thì (< 5ms) khi câu hỏi trùng lặp mà không cần gọi lại LLM/SQL.
4. **An toàn vận hành (Graceful Degradation)**: Tự động chuyển đổi sang in-memory fallback nếu database ngắt kết nối, đảm bảo 100% không phát sinh lỗi làm gián đoạn trải nghiệm người dùng.

---

## 2. Target Users

| Đối tượng | Nhu cầu chính | Giá trị nhận được |
|-----------|---------------|-------------------|
| **Giám sát viên KCN** | - Chat nhiều lượt liên tục về camera, xe cộ, an ninh.<br>- Trợ lý ghi nhớ tên, phòng ban, ca trực và khu vực phụ trách.<br>- Nhận kết quả tức thì với các câu hỏi lặp lại trong ca trực. | Trải nghiệm thông minh, nhất quán, không bị mất ngữ cảnh khi F5 hoặc bảo trì server. |
| **Kỹ sư AI / Developer** | - Mã nguồn Memory & Context sạch sẽ, dễ bảo trì, tuân thủ Clean Architecture.<br>- Viết test độc lập không phụ thuộc cứng vào hạ tầng ngoài.<br>- Dễ dàng cấu hình bật/tắt từng lớp memory qua file `.env`. | Hệ thống chuẩn Enterprise, dữ liệu an toàn trên PostgreSQL, dễ mở rộng. |

---

## 3. Core User Flow

```text
[Người dùng gửi câu hỏi] (question, user_id, session_id)
        │
        ▼
[1. Kiểm tra TTL Cache] ──(Hit: <5ms)──► [Trả ngay câu trả lời]
        │ (Miss)
        ▼
[2. Recall Long-Term Memory] ──► Truy vấn facts của user_id từ PostgreSQL
        │
        ▼
[3. Context Engineering Engine]
   ├─ Kiểm tra Context Usage (ngưỡng 40%) ──► Tự động tóm tắt hội thoại cũ nếu vượt ngưỡng
   ├─ Cắt tỉa Sliding Window ──► Giữ N tin nhắn gần nhất + system prompt gốc
   ├─ Nạp facts người dùng ──► Chèn vào system context ("Thông tin đã biết về user: ...")
   └─ Re-inject Core Instructions ──► Chèn chỉ dẫn cốt lõi ở cuối prompt
        │
        ▼
[4. Agent Graph Execution]
   └─ Thực thi Tool (Text-to-SQL / Docs) ──► Nén kết quả tool nếu quá dài (Tool Compression)
        │
        ▼
[5. Extract & Store Fact] ──► Trích xuất fact mới đáng nhớ và ghi vào PostgreSQL
        │
        ▼
[6. Lưu TTL Cache & Stream Response] ──► Ghi cache 300s và stream câu trả lời về người dùng
```

---

## 4. Features in Scope

1. **PostgreSQL Memory Persistence (`src/memory/db.py`)**:
   - Tự động tạo bảng `user_memories` (`id`, `user_id`, `fact`, `category`, `created_at`, `updated_at`) và index `(user_id)`.
   - Kết nối qua connection pool sẵn có; an toàn tuyệt đối, không crash ứng dụng nếu DB tạm thời offline.

2. **Clean Long-Term Memory (`src/memory/longterm.py`)**:
   - `save_to_long_term(user_id, fact, category)`: Ghi fact vào PostgreSQL.
   - `recall_long_term(user_id, query, k=3)`: Lấy top-k fact liên quan nhất của `user_id` từ PostgreSQL (xếp hạng theo mức độ trùng khớp từ khóa).
   - `clear_long_term(user_id)`: Xóa memory phục vụ kiểm thử.
   - Tự động fallback sang RAM list khi không có DB.

3. **Context Engineering Engine (`src/memory/context.py`)**:
   - `sliding_window(messages, max_messages=20)`: Giữ N message gần nhất, luôn giữ system message khởi tạo.
   - `estimate_tokens(messages)` & `context_usage(messages, window_tokens)`: Đo lường tải context (hỗ trợ tiktoken / 4 ký tự/token).
   - `should_compact(messages, window_tokens, threshold=0.40)`: Kích hoạt tóm tắt chủ động khi vượt 40% window (nguyên tắc 40-60%).
   - `should_compact_route(messages, window_tokens, threshold=0.40)`: Conditional edge cho LangGraph (`"compact"` hoặc `"continue"`).
   - `summarize_old_messages(messages, keep_recent=6)`: Tóm tắt tin nhắn cũ thành 3-5 câu mang tiền tố `[Tóm tắt hội thoại trước]: ...`.
   - `create_compaction_diff(messages, keep_recent=6)`: Tạo diff `RemoveMessage(id)` và `SystemMessage` tóm tắt để mutate/persist trực tiếp vào LangGraph state (`add_messages` reducer).
   - `compress_tool_result(raw_result, query, max_tokens=300)`: Nén kết quả tool dài trước khi đưa vào prompt.
   - `reinject_instructions(messages, instructions)`: Chèn lại quy tắc cốt lõi ở cuối context chống instruction fade-out (`[Nhắc lại chỉ dẫn]: ...`).
   - `latest_human_query(messages)` (`_latest_human_query`): Quét ngược tìm câu hỏi user/human gần nhất phục vụ tool retrieval & memory recall.
   - `detect_repetition(messages, window=4)` (`_detect_repetition`): Circuit breaker phát hiện agent lặp lại hành động/tool call liên tiếp để ngắt vòng lặp vô tận.

4. **Short-Term Checkpointer (`src/memory/shortterm.py`)**:
   - `get_checkpointer()`: Cung cấp checkpointer cho LangGraph phiên chat, hỗ trợ lưu trữ bền vững khi có DB và fallback `MemorySaver` trong RAM.

5. **TTL Response Cache (`src/memory/ttl_cache.py`)**:
   - Khóa băm SHA-256 chuẩn hóa câu hỏi.
   - `get_ttl_cached(key)` & `set_ttl_cached(key, data, ttl=300)`: Thread-safe, tự động xóa entry hết hạn.

6. **Fact Extraction (`src/memory/extract.py`)**:
   - Heuristic regex tiếng Việt (tên, vai trò, camera phụ trách, lưu ý).
   - Tích hợp prompt trích xuất ngắn gọn cuối lượt hội thoại. Bỏ qua các số liệu thống kê tạm thời.

7. **Graph Integration & Config (`src/agent/graph.py` & `src/config.py`)**:
   - Gắn `recall_node` ở đầu luồng và `extract_node` ở cuối luồng graph.
   - Cấu hình qua `.env`: `MEMORY_ENABLED`, `MEMORY_SHORT_TERM_ENABLED`, `MEMORY_LONG_TERM_ENABLED`, `MEMORY_TTL_SECONDS`.

---

## 5. Features out of Scope

- **Không dùng Vector Database rời**: Không kéo thêm Qdrant Cloud, Milvus, Pinecone hay Chroma. Tận dụng tối đa PostgreSQL native và token/keyword overlap đơn giản, hiệu quả.
- **Không làm GUI quản trị Memory**: Không dựng trang web riêng để xem/sửa memory; dữ liệu được quản lý tự động qua API và bảng PostgreSQL.
- **Không áp dụng thuật toán nén phức tạp ngoài MVP**: Giữ cơ chế Sliding Window + Summarization đơn giản, không nhúng các thư viện tóm tắt phân cấp cồng kềnh.
- **Không yêu cầu Embeddings bên ngoài**: Mọi hàm trích xuất và tìm kiếm hoạt động tốt cả khi offline hoặc không có API key OpenAI.

---

## 6. Acceptance Criteria

- **AC-1 (PostgreSQL Durability)**: Fact lưu qua `save_to_long_term` phải nằm trong bảng `user_memories`. Sau khi restart server, `recall_long_term` vẫn đọc lại đúng dữ liệu của `user_id`.
- **AC-2 (User Isolation)**: Mọi thao tác bộ nhớ phải cô lập theo `user_id`. Không bao giờ để rò rỉ fact của user này sang context của user khác.
- **AC-3 (Graceful Fallback)**: Khi `DB_HOST` rỗng hoặc DB ngắt kết nối, 100% các hàm memory tự động fallback sang in-memory, tuyệt đối không văng exception ra ngoài.
- **AC-4 (TTL Cache Speed & Expiry)**:
  - Cache Hit phản hồi câu trả lời với latency < 5ms.
  - Sau thời gian TTL (300s), cache tự động hết hạn và kích hoạt lại luồng xử lý thông thường.
- **AC-5 (Sliding Window & Instruction Retention)**: Hội thoại dài trên 10 lượt không bị tràn token; chỉ dẫn an toàn luôn hiện diện ở cuối prompt nhờ `reinject_instructions`.
- **AC-6 (Active Compaction 40%)**: Khi dung lượng ngữ cảnh vượt ngưỡng 40% window, hệ thống tự động gom tin nhắn cũ thành 1 đoạn tóm tắt `[Tóm tắt hội thoại trước]: ...`, giữ nguyên các tin nhắn gần nhất.
- **AC-7 (Tool Output Compression)**: Kết quả SQL table hoặc Docs dài hơn `max_tokens` được nén gọn gàng trước khi nạp vào context.
- **AC-8 (Zero Regression & Clean Code)**: Không còn code rác `vector=[0.0]`; toàn bộ test suite cũ và mới (≥620 tests) đạt kết quả PASS 100%.
