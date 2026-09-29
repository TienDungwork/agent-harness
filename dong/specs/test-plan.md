# Test Plan — agent dong v9: Unified Memory & Context Engineering System (Postgres-backed)

**Trạng thái:** Spec only — Chuẩn bị thực hiện.  
**Mục tiêu:** Kiểm thử toàn diện hệ thống Memory 3 tầng (Short-Term, Long-Term, TTL Cache) lưu trữ trên PostgreSQL và Context Engineering Engine (`context.py`), đảm bảo tính bền vững, cách ly dữ liệu, quản lý cửa sổ ngữ cảnh tối ưu và không làm đứt gãy các luồng nghiệp vụ hiện tại.

---

## 1. Phạm vi kiểm thử

| Nhóm tính năng | Mục tiêu kiểm thử | Phương thức |
|----------------|-------------------|-------------|
| **PostgreSQL Long-Term Storage** | Lưu trữ và truy vấn facts người dùng vào bảng `user_memories` trong PostgreSQL. Dữ liệu không bị mất khi restart server. | Unit test + DB check |
| **User Data Isolation** | Tuyệt đối không rò rỉ facts giữa các `user_id` khác nhau. | Unit test tự động |
| **In-Memory Fallback** | Khi ngắt kết nối PostgreSQL hoặc cấu hình DB rỗng, hệ thống tự động fallback in-memory, không crash. | Unit test tự động |
| **Context Engineering Engine** | Kiểm thử 5 kỹ thuật: Sliding Window, 40-60% Compaction rule, Summarization hội thoại cũ, Tool output compression, và Re-injecting instructions. | Unit test tự động |
| **Short-Term Checkpointer** | Khởi tạo checkpointer bền vững trên PostgreSQL (fallback `MemorySaver` khi chạy local/test). | Unit test tự động |
| **TTL Response Cache** | Cache Hit phản hồi nhanh < 10ms; hết hạn TTL tự động miss; thread-safe khi nhiều request đồng thời. | Unit test tự động |
| **Smart Fact Extraction** | Nhận diện chính xác tên, vai trò, sở thích; lọc bỏ không lưu số liệu giao thông/realtime tạm bợ. | Unit test tự động |
| **End-to-End Regression** | Đảm bảo 100% các tính năng cũ (Text-to-SQL, 10 camera, Human Feedback, Streaming) tiếp tục hoạt động trơn tru. | Chạy toàn bộ pytest suite |

---

## 2. Kế hoạch kiểm thử tự động (Unit Tests)

### Test Suite 1: Context Engineering Engine (`tests/test_product_memory_context.py`)
- **Các ca kiểm thử**:
  1. `test_sliding_window_preserves_system_and_recent`:
     - Tạo danh sách 25 message (gồm 1 system message ở đầu và 24 turn qua lại).
     - Gọi `sliding_window(messages, max_messages=10)`.
     - Kỳ vọng: Trả về danh sách gồm 11 message (1 system message gốc + 10 message gần nhất), không bị lặp system message.
  2. `test_estimate_tokens_and_context_usage`:
     - Gọi `estimate_tokens` trên danh sách message mẫu.
     - Kiểm tra `context_usage` với `window_tokens=4000`.
     - Kỳ vọng: Giá trị trả về nằm trong khoảng [0.0, 1.0].
  3. `test_should_compact_activates_at_40_percent`:
     - Giả lập danh sách message chiếm 20% dung lượng window -> `should_compact` trả về `False`.
     - Giả lập danh sách message chiếm 45% dung lượng window (vượt ngưỡng 40%) -> `should_compact` trả về `True`.
  4. `test_summarize_old_messages_creates_summary_message`:
     - Tạo danh sách 15 message.
     - Gọi `summarize_old_messages(messages, keep_recent=4)`.
     - Kỳ vọng: Kết quả trả về 5 message gồm 1 system message mang tiền tố `[Tóm tắt hội thoại trước]: ...` và 4 message mới nhất.
  5. `test_compress_tool_result_skips_short_output`:
     - Kết quả tool ngắn (< 300 token * 4 ký tự): hàm `compress_tool_result` trả về nguyên bản chuỗi gốc mà không gọi LLM nén.
  6. `test_compress_tool_result_compresses_long_output`:
     - Kết quả tool dài (chuỗi bảng số liệu > 2000 ký tự): hàm `compress_tool_result` kích hoạt LLM nén và trả về đoạn trích xuất cô đọng.
  7. `test_reinject_instructions_appends_to_end`:
     - Gọi `reinject_instructions(messages, "Quy tắc an toàn VMS KCN")`.
     - Kỳ vọng: Tin nhắn cuối cùng trong danh sách trả về là system message mang tiền tố `[Nhắc lại chỉ dẫn]: ...`.
  8. `test_latest_human_query_scans_backwards`:
     - Quét ngược qua chuỗi tin nhắn có xen kẽ tool call và tool result.
     - Kỳ vọng: Trả về chính xác nội dung câu hỏi gần nhất của người dùng (`role in ('human', 'user')`).
  9. `test_detect_repetition_detects_infinite_loop`:
     - Giả lập 4 tool call liên tiếp giống hệt nhau (`window=4`).
     - Kỳ vọng: Trả về `True` kích hoạt cảnh báo `REPETITION_WARNING` ngắt vòng lặp vô tận.
  10. `test_create_compaction_diff_persists_to_state`:
      - Gọi `create_compaction_diff(messages, keep_recent=4)`.
      - Kỳ vọng: Trả về diff gồm danh sách `RemoveMessage(id)` cho các message cũ và 1 `SystemMessage` mang tiền tố `[Tóm tắt hội thoại trước]: ...` để mutate trực tiếp vào LangGraph state.
  11. `test_should_compact_route_conditional_edge`:
      - Kiểm tra routing của conditional edge: vượt 40% window trả về `"compact"`, ngược lại trả về `"continue"`.

### Test Suite 2: Long-Term Memory & PostgreSQL Persistence (`tests/test_product_memory_postgres.py`)
- **Các ca kiểm thử**:
  1. `test_init_memory_db_creates_table_safely`:
     - Chạy hàm `init_memory_db()`.
     - Xác nhận bảng `user_memories` và index được tạo thành công nếu có DB, hoặc log warning an toàn nếu không có DB.
  2. `test_save_and_recall_long_term_postgres`:
     - Gọi `save_to_long_term("user_123", "Tôi thích giám sát camera cổng số 1")`.
     - Gọi `recall_long_term("user_123", "hôm nay xem camera cổng 1 nhé")`.
     - Kỳ vọng: Kết quả trả về danh sách chứa fact đã lưu.
  3. `test_user_isolation_strictly_enforced`:
     - Lưu fact cho `user_A`: *"Tôi tên là Nguyễn Văn An"*.
     - Lưu fact cho `user_B`: *"Tôi tên là Trần Thị Bình"*.
     - Gọi `recall_long_term("user_A", "tôi tên là gì")` -> Chỉ thấy fact của `user_A`, tuyệt đối không có `user_B`.
  4. `test_fallback_to_in_memory_when_db_down`:
     - Giả lập lỗi kết nối PostgreSQL (mock exception).
     - Gọi `save_to_long_term` và `recall_long_term`.
     - Kỳ vọng: Không ném ngoại lệ; dữ liệu được lưu tạm và đọc ra từ in-memory fallback store.
  5. `test_clear_long_term_by_user`:
     - Gọi `clear_long_term("user_123")`.
     - Xác nhận fact của `user_123` bị xóa, facts của user khác vẫn giữ nguyên.

### Test Suite 3: TTL Cache & Expiration (`tests/test_product_memory_cache.py`)
- **Các ca kiểm thử**:
  1. `test_ttl_cache_hit_and_miss`:
     - Set cache cho key `q_hash`.
     - Lấy lại khi chưa hết hạn -> Cache Hit (trả về data nguyên vẹn).
     - Query key khác -> Cache Miss (trả về `None`).
  2. `test_ttl_cache_expires_after_ttl`:
     - Set cache với `ttl=1` giây.
     - Đợi 1.1 giây.
     - Gọi `get_ttl_cached` -> Kỳ vọng trả về `None` và tự xóa key hết hạn khỏi bộ nhớ.
  3. `test_make_cache_key_normalization`:
     - Hai chuỗi khác hoa thường hoặc khoảng trắng đầu cuối (ví dụ: `"  Lưu lượng xe? "` và `"lưu lượng xe?"`) phải sinh ra cùng một `make_cache_key`.

### Test Suite 4: Smart Extraction & Realtime Filtering
- **File**: `tests/test_product_memory_cache.py`
- **Các ca kiểm thử**:
  1. `test_heuristic_extract_name_and_role`:
     - Input: *"Chào bạn, tôi tên là Hùng, tôi phụ trách an ninh KCN Hưng Phú"*.
     - Kỳ vọng: Trích xuất được fact tên và vai trò.
  2. `test_extraction_ignores_realtime_traffic_stats`:
     - Input: *"Hôm nay có 150 lượt xe tải vào cổng"* và câu trả lời thống kê.
     - Với `detail="query_data"`, hàm `extract_memories` không được lưu số liệu thống kê realtime vào long-term memory.

---

## 3. Kịch bản kiểm thử thủ công (Manual / Smoke Checklist)

| STT | Thao tác trên giao diện Web | Kỳ vọng quan sát được |
|:---:|------------------------------|------------------------|
| 1 | Mở web chat (`http://localhost:8080`), gửi: *"Chào bạn, tôi tên là Tuấn, tôi phụ trách giám sát an ninh ca đêm"* | Trợ lý phản hồi chào lịch sự, ghi nhận danh tính. Server trích xuất và lưu fact vào PostgreSQL (`user_memories`). |
| 2 | Gửi câu hỏi tiếp theo trong cùng phiên: *"Khu vực tôi phụ trách là gì?"* | Trợ lý nhớ và trả lời: *"Bạn phụ trách giám sát an ninh ca đêm"*. (Kiểm tra Short-Term & Long-Term memory hoạt động). |
| 3 | Mở tab ẩn danh mới hoặc bấm tạo phiên mới với cùng `user_id`: *"Tôi là ai?"* | Trợ lý vẫn trả lời đúng: *"Bạn là Tuấn, phụ trách an ninh ca đêm"* (chứng minh Long-Term memory đã được lưu bền vững vào PostgreSQL và nạp lại thành công). |
| 4 | Trò chuyện liên tục qua hơn 10 câu hỏi nghiệp vụ | Trợ lý phản hồi nhanh, không bị lag hoặc đơ do tràn context; các chỉ dẫn quy tắc an toàn VMS vẫn được tuân thủ nghiêm ngặt (chứng minh Sliding Window & Instruction Re-injection hoạt động tốt). |
| 5 | Gửi câu hỏi thống kê: *"Hôm nay có bao nhiêu lượt xe vào KCN?"* | Trợ lý truy vấn SQL và trả về số liệu chính xác kèm biểu đồ. Nếu bảng dữ liệu dài, kết quả được nén súc tích trước khi tổng hợp câu trả lời. |
| 6 | Gửi lại ngay lập tức câu hỏi y hệt: *"Hôm nay có bao nhiêu lượt xe vào KCN?"* | Trợ lý trả về kết quả gần như ngay lập tức (< 50ms) do TTL Cache Hit, không thấy log query SQL hay gọi lại LLM trên console. |
| 7 | Tạm dừng database PostgreSQL hoặc đổi cấu hình `DB_HOST=invalid` rồi gửi câu hỏi chat | Ứng dụng vẫn hoạt động bình thường, ghi nhận log warning nhẹ và tự động chuyển sang in-memory fallback mà không báo lỗi 500 ra giao diện. |
