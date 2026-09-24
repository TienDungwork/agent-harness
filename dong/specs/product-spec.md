# Product Spec — agent dong v8

**Trạng thái:** Spec Approved — Sẵn sàng triển khai theo kế hoạch.  
**Baseline:** v7 đang chạy ổn định (Docker, Text-to-SQL Postgres read-only, Fast Classify, Chart.js & PNG).  
**v8 Focus:** Chuẩn hóa dữ liệu 10 camera từ AIOC Master Registry, hệ thống Human Feedback (đánh giá tốt/xấu kèm lý do & đính kèm ảnh lưu vào JSON có trace), và phản hồi câu trả lời dạng stream (token/chunk).

---

## 1. App Goal

Xây dựng trợ lý ảo tiếng Việt chuyên sâu cho công tác giám sát và vận hành Camera AI tại KCN Hưng Phú, tập trung vào 3 mục tiêu cốt lõi:
1. **Dữ liệu thiết bị chính xác**: Khắc phục lỗi đếm thiếu camera (chỉ lấy 6 camera giao thông trong bảng `plate_event`), đảm bảo phản ánh đầy đủ **10 camera đang hoạt động (ONLINE)** thuộc cả 3 phân hệ giám sát trên AIOC (`https://aioc.atin.vn/devices`).
2. **Thu thập phản hồi người dùng (Human Feedback)**: Cung cấp cơ chế đánh giá câu trả lời (Tốt 👍 / Xấu 👎) ngay trên giao diện chat. Khi đánh giá xấu, người dùng có thể nhập lý do và đính kèm ảnh chụp màn hình. Dữ liệu được lưu trữ có cấu trúc vào file JSON kèm toàn bộ vết thực thi của agent (`agent_trace`) để phục vụ gỡ lỗi và cải tiến chất lượng trả lời.
3. **Trải nghiệm hội thoại thời gian thực (Token Streaming)**: Chuyển đổi phản hồi ở bước cuối cùng từ hiển thị một khối sau khi chờ sang dạng stream từng từ (gõ chữ thời gian thực) qua Server-Sent Events (SSE).

---

## 2. Target Users

| Đối tượng người dùng | Hành vi & Nhu cầu chính | Giá trị mang lại |
|----------------------|-------------------------|-------------------|
| **Nhân viên vận hành KCN / Giám sát viên** | - Đặt câu hỏi tiếng Việt về số lượng camera, lưu lượng xe, cảnh báo an ninh.<br>- Xem câu trả lời xuất hiện dần dần theo luồng stream mượt mà.<br>- Đánh giá Like (👍) khi câu trả lời đúng, Dislike (👎) khi sai và cung cấp lý do + ảnh minh họa trực tiếp. | - Nhận thông tin chính xác, nhanh chóng.<br>- Dễ dàng báo cáo câu trả lời sai lệch mà không cần rời màn hình chat. |
| **Kỹ sư AI / Reviewer / Nhà phát triển** | - Mở file `data/feedback.json` để kiểm tra các trường hợp người dùng đánh giá xấu.<br>- Đọc hiểu nhanh câu hỏi, câu trả lời, lý do phản hồi, ảnh đính kèm và toàn bộ luồng xử lý (`agent_trace`). | - Nhanh chóng tái hiện lỗi, tinh chỉnh prompt, cải thiện schema catalog hoặc bổ sung vào dataset đánh giá (golden-30). |

---

## 3. Core User Flow

1. **Khởi tạo & Nhập câu hỏi**:
   - Người dùng truy cập giao diện web (`http://localhost:8080` hoặc `http://localhost:3001`).
   - Nhập câu hỏi (ví dụ: *"Hiện có bao nhiêu camera đang hoạt động?"* hoặc *"Hôm nay có bao nhiêu lượt xe ra vào?"*).
2. **Điều phối xử lý (Agent Execution Flow)**:
   - Câu hỏi đi qua Guardrail an toàn → `rewrite` → `classify`.
   - **Nhánh Camera Master Data**: Nếu câu hỏi hỏi về số lượng/danh sách camera trong hệ thống, agent tra cứu nhanh từ AIOC Master Registry (`camera_registry.yaml`) để trả lời chuẩn xác **10 camera ONLINE**.
   - **Nhánh Thống kê số liệu**: Chuyển sang pipeline Text-to-SQL (`retrieve_schema` → `generate_sql` → `validate_sql` → `execute_sql` → `respond`).
3. **Phản hồi dạng Stream (Token / Chunk Streaming)**:
   - Server phát SSE event mang delta ký tự (`status: "chunk"`).
   - Frontend hiển thị hiệu ứng gõ chữ liên tục, mượt mà vào khung chat.
   - Kết thúc lượt phản hồi bằng event `status: "done"`.
4. **Đánh giá Human Feedback**:
   - Dưới bubble câu trả lời của AI xuất hiện 2 nút đánh giá: 👍 (Tốt) và 👎 (Xấu).
   - **Kịch bản A (Tốt 👍)**: Người dùng click 👍 → Gửi request ghi nhận feedback tích cực kèm context và trace vào `data/feedback.json` → Hiển thị toast cảm ơn ngắn gọn.
   - **Kịch bản B (Xấu 👎)**: Người dùng click 👎 → Mở modal phản hồi:
     - Người dùng nhập lý do (textarea).
     - Người dùng tải lên hoặc dán (paste) ảnh chụp màn hình minh họa (nếu có).
     - Người dùng bấm nút **"Xác nhận lưu phản hồi"** (Accept).
     - Hệ thống lưu toàn bộ dữ liệu gồm: câu hỏi, câu trả lời, lý do, đường dẫn ảnh và `agent_trace` chi tiết vào `data/feedback.json`.

```text
                     [ Người dùng nhập câu hỏi ]
                                  │
                                  ▼
                     [ Guardrail & Phân loại ]
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
      [ Hỏi về Camera hệ thống ]        [ Hỏi sự kiện & số liệu ]
                 │                                 │
     Tra cứu Master Registry 10 Cam         Pipeline Text-to-SQL
                 │                                 │
                 └────────────────┬────────────────┘
                                  │
                                  ▼
             [ Phản hồi Token Stream qua SSE (gõ chữ) ]
                                  │
                                  ▼
                     [ Đánh giá Human Feedback ]
                       ┌──────────┴──────────┐
                       ▼                     ▼
                  Like (👍)              Dislike (👎)
                       │                     │
                       │              Mở Modal nhập:
                       │              - Lý do đánh giá sai
                       │              - Đính kèm ảnh minh họa
                       │              - Bấm Xác nhận (Accept)
                       └──────────┬──────────┘
                                  ▼
              Lưu vào data/feedback.json (kèm Agent Trace)
```

---

## 4. Features in Scope

### Feature 1: Chuẩn hóa đếm và tra cứu camera toàn hệ thống (10 Camera AIOC)
- **Vấn đề cần khắc phục**: Trợ lý đang chỉ đếm 6 camera trong bảng `plate_event` (phân hệ giao thông/biển số) khi người dùng hỏi tổng số camera.
- **Giải pháp**:
  - Tích hợp Master Data Registry (`resource/db/camera_registry.yaml` đồng bộ từ AIOC Cloud Cam).
  - Ghi nhận và phản hồi đầy đủ thông tin **10 camera đang hoạt động (ONLINE)**:
    - 6 camera Giám sát phương tiện: `congchinh1`, `congchinh2`, `congvanle1`, `congvanle2`, `congvanle3`, `congvanle4`.
    - 2 camera Giám sát vùng cấm: `Cổng Ra Vào BOH` (`CVN_CONG_BOH`), `CVNTT`.
    - 2 camera Cảnh báo cháy khói: `CVN_KHO_TANG2_BOH`, `CVN_P_CAP_PHAT_DONG_PHUC`.
  - Cập nhật quy tắc text-to-SQL và fast-path để khi hỏi số lượng hoặc danh sách camera của hệ thống, agent trả lời chính xác số 10 và phân loại chức năng rõ ràng.

### Feature 2: Hệ thống Human Feedback (Đánh giá Tốt / Xấu & Lưu vết chi tiết)
- **Giao diện người dùng (UI)**:
  - Cụm nút icon 👍 và 👎 hiển thị kín đáo, chuyên nghiệp dưới mỗi câu trả lời của trợ lý.
  - Modal Dislike hỗ trợ:
    - Textarea nhập nội dung giải thích lý do không hài lòng.
    - Input upload file ảnh (.png, .jpg, .jpeg) và hỗ trợ dán ảnh từ clipboard (paste).
    - Thumbnail preview ảnh trước khi bấm gửi.
    - Nút "Hủy bỏ" và nút "Xác nhận lưu phản hồi" (Accept).
- **Backend & Cơ chế lưu trữ SQLite (`data/feedback.db`)**:
  - Endpoint API: `POST /api/feedback` và `GET /api/feedback`.
  - Cơ sở dữ liệu lưu trữ: `data/feedback.db` (SQLite chuẩn ACID, tự động khởi tạo thư mục và bảng `feedback`). Đồng thời hỗ trợ đồng bộ xuất `data/feedback.json` để tương thích ngược.
  - File đính kèm lưu tại: `data/feedback/attachments/{feedback_id}_{filename}`.
  - Bảng SQLite `feedback`:
    ```sql
    CREATE TABLE IF NOT EXISTS feedback (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        session_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        rating TEXT NOT NULL,
        feedback_reason TEXT,
        attachment_path TEXT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        agent_trace TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```
  - Cấu trúc bản ghi đầy đủ ngữ cảnh để AI/Developer tái hiện và hiểu rõ luồng:
    ```json
    {
      "id": "fb_20260924_093000_a1b2",
      "timestamp": "2026-09-24T09:30:00+07:00",
      "session_id": "session_default",
      "user_id": "default",
      "rating": "negative",
      "feedback_reason": "Hệ thống trả lời 6 camera là thiếu 4 camera vùng cấm và cháy khói",
      "attachment_path": "data/feedback/attachments/fb_20260924_093000_a1b2.png",
      "question": "Hiện có bao nhiêu camera đang hoạt động?",
      "answer": "6 camera đang hoạt động...",
      "agent_trace": {
        "nodes": [
          {"node_id": "recall", "input": {...}, "output": {...}, "duration_ms": 0.8},
          {"node_id": "classify", "input": {...}, "output": {"intent": "query_data"}, "duration_ms": 544},
          {"node_id": "generate_sql", "output": {"sql": "SELECT DISTINCT camera_name FROM plate_event..."}, "duration_ms": 690},
          {"node_id": "execute_sql", "output": {"row_count": 6}, "duration_ms": 37}
        ],
        "sql": "SELECT DISTINCT camera_name FROM plate_event WHERE ...",
        "detail": "query_data"
      }
    }
    ```

### Feature 3: Phản hồi dạng Stream (Token / Chunk Response Streaming)
- **Backend SSE**:
  - Tại bước phản hồi cuối (`respond`, `respond_inline`, `answer_from_docs`), kích hoạt stream từ model (hoặc chia chunk tự nhiên khi dùng fast template).
  - Gửi các sự kiện SSE: `{"node_id": "__answer__", "status": "chunk", "delta": "từng từ"}`.
  - Kết thúc với sự kiện: `{"node_id": "__answer__", "status": "done", "output": "toàn bộ câu trả lời", "detail": {...}}`.
- **Frontend Live Rendering**:
  - Frontend nhận `delta` và nối trực tiếp vào tin nhắn hiện tại theo thời gian thực (hiệu ứng gõ chữ mượt mà).
  - Không gây giật lag hay vỡ bố cục khi có biểu đồ Chart.js đi kèm.

### Kế thừa từ v7 (Giữ nguyên không thay đổi)
- Môi trường chạy chính thức bằng Docker Compose (không đóng cứng mã nguồn vào image).
- Bảo vệ an toàn đầu vào qua Regex Guardrails.
- Truy vấn PostgreSQL read-only với cơ chế validate SQL chống DDL/DML và chặn truy vấn chéo database.
- Hiển thị biểu đồ trực quan (Canvas Chart.js & PNG).

---

## 5. Features Out of Scope

Để giữ vững tinh thần MVP và tránh phân tán phạm vi phát triển:
- **Không xây dựng trang Web Admin quản lý Feedback riêng biệt**: Toàn bộ phản hồi được lưu trữ dạng file `.json` chuẩn có cấu trúc rõ ràng để kỹ sư/AI đọc trực tiếp.
- **Không thay đổi lược đồ cơ sở dữ liệu vật lý**: Không thêm bảng hay cột mới vào các cơ sở dữ liệu PostgreSQL của VMS.
- **Không tự động kích hoạt tiến trình Fine-tuning mô hình**: Dữ liệu feedback được lưu làm tài nguyên phân tích, chưa tự động hóa pipeline training lại model.
- **Không tích hợp dịch vụ lưu trữ đám mây ngoài (S3, Cloudinary)**: Toàn bộ ảnh đính kèm được lưu cục bộ trong thư mục `data/feedback/attachments/`.

---

## 6. Acceptance Criteria

| STT | Tiêu chí nghiệm thu (Acceptance Criteria) | Kết quả kỳ vọng |
|:---:|-------------------------------------------|-----------------|
| **AC-1** | **Đếm camera chuẩn xác (10 Cams)** | - Hỏi *"Hiện có bao nhiêu camera đang hoạt động?"* → Trả lời đúng **10 camera** đang hoạt động (không trả lời 6).<br>- Câu trả lời có phân loại rõ 3 phân hệ: 6 phương tiện, 2 vùng cấm, 2 cháy khói. |
| **AC-2** | **Liệt kê camera đầy đủ** | - Hỏi *"Kể tên các camera trong hệ thống"* → Liệt kê đủ 10 camera (chứa cả các mã: `CVN_CONG_BOH`, `CVNTT`, `CVN_KHO_TANG2_BOH`, `CVN_P_CAP_PHAT_DONG_PHUC` bên cạnh các camera `congchinh`, `congvanle`). |
| **AC-3** | **Đánh giá Like (👍)** | - Bấm Like dưới tin nhắn trợ lý → Gửi `POST /api/feedback` thành công.<br>- File `data/feedback.json` có bản ghi mới với `rating: "positive"` kèm `question`, `answer`, `agent_trace`. |
| **AC-4** | **Đánh giá Dislike (👎) kèm Modal & Ảnh** | - Bấm Dislike → Mở Modal phản hồi.<br>- Cho phép nhập lý do và đính kèm file ảnh (hoặc paste ảnh screenshot).<br>- Bấm "Xác nhận lưu phản hồi" → File ảnh được lưu vào `data/feedback/attachments/` và bản ghi trong `data/feedback.json` có `rating: "negative"`, `feedback_reason`, `attachment_path` và toàn bộ `agent_trace`. |
| **AC-5** | **Tính toàn vẹn dữ liệu Feedback SQLite & JSON** | - Dữ liệu được lưu trữ chuẩn xác vào SQLite `data/feedback.db` (bảng `feedback`) và đồng bộ `data/feedback.json`, mã hóa UTF-8 tiếng Việt chuẩn, hỗ trợ ghi đồng thời nhiều request an toàn. |
| **AC-6** | **Trải nghiệm Stream câu trả lời** | - Khi trợ lý phản hồi, câu trả lời xuất hiện dần dần từng chữ/từ trên giao diện người dùng thay vì chờ 2-3 giây rồi xuất hiện cả khối. |
| **AC-7** | **Kiểm thử tự động (Unit Tests)** | - Toàn bộ bộ test `pytest -q` đạt 100% xanh (≥613 tests hiện tại + các test mới cho camera count và feedback API). |
| **AC-8** | **Không gây lỗi hồi quy** | - Các câu hỏi số liệu khác (lưu lượng xe, xâm nhập hàng rào ảo, vẽ biểu đồ Chart.js, chào hỏi nhanh) tiếp tục hoạt động chính xác. |
