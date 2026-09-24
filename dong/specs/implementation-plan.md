# Implementation Plan — agent dong v8

**Trạng thái:** Spec Approved — Sẵn sàng triển khai tuần tự.  
**Nguồn:** `specs/product-spec.md`  
**Quy tắc:** Thực hiện tuần tự từng dòng `[ ]` một, kiểm tra kỹ lưỡng, sau đó đổi thành `[x]` và cập nhật `specs/change-log.md`. Không implement hàng loạt nhiều bước cùng lúc. Không viết code khi chưa có yêu cầu.

---

## Tổng quan các Phase

| Phase | Tên Phase | Mục tiêu chính |
|:-----:|-----------|----------------|
| **Phase 1** | Project setup | Xác nhận baseline test xanh 100%, cấu hình thư mục lưu trữ feedback |
| **Phase 2** | Core UI | Cụm nút Like/Dislike, modal góp ý kèm upload ảnh, chuẩn bị khung stream |
| **Phase 3** | Core backend or data logic | Sửa lỗi 10 camera Master Registry, API `POST /api/feedback`, SSE chunk generator |
| **Phase 4** | Connect UI to data | Ghép nút feedback với API, ghép SSE delta stream vào bubble chat thời gian thực |
| **Phase 5** | Validation and error states | Validate payload feedback (size ảnh, định dạng), xử lý lỗi stream & kết nối |
| **Phase 6** | Local run instructions | Hướng dẫn chạy Docker, kiểm tra file feedback JSON và ảnh đính kèm |
| **Phase 7** | Demo & Verification | Kiểm thử toàn diện 7 kịch bản thực tế trên browser và chạy full test suite |

---

## Phase 1 — Project setup

- [x] Chạy và xác nhận toàn bộ test suite `pytest -q` hiện tại đạt 100% pass (≥613 tests).
- [x] Tạo cấu trúc thư mục lưu trữ phản hồi: `data/feedback/attachments/`.
- [x] Khởi tạo file `data/feedback.json` với mảng rỗng `[]` (nếu chưa tồn tại).
- [x] Cập nhật `.gitignore` để bỏ qua các file ảnh người dùng tải lên trong `data/feedback/attachments/`.
- [x] Cập nhật `docker-compose.yml` để mount thư mục `data/` từ host vào container (`- ./data:/app/data`), đảm bảo feedback không bị mất khi restart container.

**Done khi:** Baseline test xanh, hạ tầng thư mục lưu trữ `data/feedback` đã sẵn sàng trên cả máy host và Docker container.

---

## Phase 2 — Core UI

- [x] **Thanh hành động đánh giá (Message Action Bar)**:
  - Thêm cụm nút icon 👍 (Hài lòng) và 👎 (Chưa hài lòng) bên dưới mỗi bubble câu trả lời của trợ lý AI trong `frontend/index.html` và `frontend/style.css`.
  - Thiết kế hover effect mượt mà, hỗ trợ trạng thái đã chọn (active state).
- [x] **Hộp thoại góp ý (Feedback Modal)**:
  - Xây dựng modal HTML/CSS cho trường hợp Dislike (👎):
    - Tiêu đề modal: "Góp ý câu trả lời của trợ lý AI".
    - Textarea nhập lý do đánh giá sai / chưa hài lòng (placeholder: *"Hãy mô tả chi tiết điểm chưa đúng..."*).
    - Khu vực đính kèm ảnh: Nút chọn file ảnh (`.png`, `.jpg`, `.jpeg`) và vùng hỗ trợ paste trực tiếp từ clipboard.
    - Khung preview ảnh thu nhỏ kèm nút xóa ảnh (X) trước khi gửi.
    - Hai nút thao tác: "Hủy bỏ" và "Xác nhận gửi phản hồi".
- [x] **Khung hiển thị tin nhắn dạng Stream**:
  - Chuẩn bị cơ chế DOM trong `frontend/app.js` để bubble chat có thể nhận và nối từng ký tự/từ ngữ liên tục mà không gây giật lag hoặc render lại các thành phần khác.
- [x] **Toast thông báo**:
  - Bổ sung toast thông báo trạng thái: "Cảm ơn bạn đã gửi phản hồi!" và "Gửi phản hồi thất bại, vui lòng thử lại!".

**Done khi:** Giao diện hoàn chỉnh nút Like/Dislike, Modal góp ý có khung upload/paste ảnh xem trước và khung chat sẵn sàng nhận stream.

---

## Phase 3 — Core backend or data logic

- [x] **Chuẩn hóa dữ liệu 10 Camera (Master Registry)**:
  - Cập nhật prompt Text-to-SQL `resource/prompts/sql_agent/v1.yaml`: Bổ sung quy tắc khi người dùng hỏi tổng số camera hoặc danh sách camera của hệ thống thì không được chỉ đếm bảng `plate_event` (vì plate_event chỉ có 6 camera giao thông).
  - Hoàn thiện logic fast-path trong `src/agent/graph.py` (hoặc `src/agent/pre_sql.py`) tra cứu từ `resource/db/camera_registry.yaml` để trả về chính xác **10 camera ONLINE** thuộc cả 3 phân hệ (6 phương tiện, 2 vùng cấm, 2 cháy khói).
- [x] **Schema & API Human Feedback**:
  - Định nghĩa Pydantic model `FeedbackRequest` trong `src/llm/schemas.py`:
    - `session_id`: str, `user_id`: str, `question`: str, `answer`: str
    - `rating`: Literal["positive", "negative"]
    - `feedback_reason`: Optional[str]
    - `image_base64`: Optional[str]
    - `agent_trace`: Optional[dict[str, Any]]
  - Xây dựng helper lưu trữ `save_feedback_record(...)` trong backend:
    - Lưu file ảnh đính kèm (decode base64) vào `data/feedback/attachments/{id}.png`.
    - Lưu bản ghi vào cơ sở dữ liệu SQLite `data/feedback.db` (bảng `feedback`), tự động migrate từ `data/feedback.json` cũ và đồng bộ xuất JSON để tương thích ngược.
  - Xây dựng endpoint `POST /api/feedback` trong `src/main.py`.
- [x] **Cơ chế Token / Chunk Response Streaming**:
  - Cập nhật luồng `run_agent_stream` trong `src/agent/graph.py` và generator trong `src/main.py`:
    - Cho phép node phản hồi (`respond`, `respond_inline`, `answer_from_docs`) phát các SSE events dạng `{"node_id": "__answer__", "status": "chunk", "delta": "..."}`.
    - Phát event kết thúc `{"node_id": "__answer__", "status": "done", "output": "...", "detail": {...}}`.

**Done khi:** Backend có thể tra cứu đủ 10 camera, API feedback lưu thành công dữ liệu + ảnh, và SSE phát được delta chunks.

---

## Phase 4 — Connect UI to data

- [x] **Kết nối sự kiện Like (👍)**:
  - Khi click 👍 dưới bubble chat: Lấy `question`, `answer`, `session_id`, `user_id`, `agent_trace` của lượt chat tương ứng → Gửi request `POST /api/feedback` với `rating: "positive"`.
  - Cập nhật giao diện: Đổi màu nút 👍 sang trạng thái đã like, hiển thị toast cảm ơn ngắn.
- [x] **Kết nối sự kiện Dislike (👎) & Modal Góp ý**:
  - Khi click 👎: Mở Feedback Modal, gán ngữ cảnh của tin nhắn tương ứng vào modal state.
  - Khi người dùng chọn file hoặc dán ảnh: Đọc file sang chuỗi base64 và hiển thị ảnh thumbnail preview.
  - Khi người dùng nhấn "Xác nhận gửi phản hồi": Gửi `POST /api/feedback` với `rating: "negative"`, kèm `feedback_reason`, `image_base64`, `question`, `answer` và `agent_trace`.
  - Đóng modal, đổi màu nút 👎 và hiển thị thông báo đã ghi nhận phản hồi.
- [x] **Kết nối SSE Chunk Stream vào Bubble Chat**:
  - Trong `frontend/app.js`, lắng nghe event SSE có `node_id: "__answer__"` và `status: "chunk"`:
    - Nối trực tiếp chuỗi `delta` vào bubble tin nhắn hiện tại theo thời gian thực (hiệu ứng gõ chữ mượt mà).
  - Khi nhận `status: "done"`: Kết thúc hiệu ứng stream, hiển thị biểu đồ Chart.js (nếu có) và kích hoạt cụm nút Like/Dislike.

**Done khi:** Người dùng trải nghiệm được câu trả lời gõ chữ dần dần trên UI và bấm Like/Dislike lưu thành công vào file JSON của hệ thống.

---

## Phase 5 — Validation and error states

- [x] **Validate đầu vào Feedback API (`POST /api/feedback`)**:
  - Kiểm tra `rating` bắt buộc phải là `"positive"` hoặc `"negative"`.
  - Kiểm tra giới hạn kích thước ảnh đính kèm (tối đa 5MB) và kiểm tra tính hợp lệ của chuỗi base64.
  - Xử lý các trường hợp gửi dữ liệu rỗng hoặc sai kiểu, trả về HTTP status code phù hợp (400 / 422).
- [x] **Xử lý lỗi trên giao diện (Frontend Error Handling)**:
  - Nếu gửi feedback thất bại (mất mạng / server lỗi): Hiển thị thông báo lỗi rõ ràng trên modal, không làm mất nội dung lý do người dùng vừa nhập.
  - Chống bấm gửi nhiều lần liên tiếp (disable nút bấm, hiển thị loading spinner khi đang gửi).
  - Nếu người dùng bấm Dislike nhưng để trống lý do: Vẫn cho phép gửi hoặc hiển thị nhắc nhở nhẹ nhàng.
- [x] **Xử lý ngắt kết nối Stream SSE**:
  - Nếu kết nối SSE bị gián đoạn giữa chừng: Hiển thị icon cảnh báo và cho phép người dùng bấm "Thử lại".
- [x] **Fallback khi thiếu file Master Registry**:
  - Nếu file `camera_registry.yaml` gặp lỗi cú pháp hoặc bị thiếu: Hệ thống tự động fallback truy vấn SQL union an toàn mà không làm crash server.

**Done khi:** Toàn bộ các trường hợp dữ liệu xấu, file ảnh quá dung lượng, mất kết nối mạng hoặc lỗi server đều được kiểm soát và thông báo thân thiện.

---

## Phase 6 — Local run instructions

- [x] Cập nhật tài liệu hướng dẫn chạy trong `README.md`:
  - Khởi động hệ thống bằng Docker Compose:
    ```bash
    docker compose up -d
    ```
  - Hướng dẫn xem dữ liệu feedback được lưu trữ:
    ```bash
    # Xem danh sách các phản hồi người dùng đã ghi lại
    cat data/feedback.json | jq .
    
    # Xem danh sách ảnh chụp màn hình đính kèm
    ls -la data/feedback/attachments/
    ```
  - Hướng dẫn kiểm tra trạng thái camera registry:
    ```bash
    cat resource/db/camera_registry.yaml
    ```
- [x] Hướng dẫn chạy bộ kiểm thử tự động cho tính năng mới:
  ```bash
  PYTHONPATH=. pytest tests/ -k "camera or feedback"
  ```

**Done khi:** Tài liệu README rõ ràng, dễ dàng thao tác kiểm tra dữ liệu feedback và chạy container cục bộ.

---

## Phase 7 — Demo & Verification

- [x] **Chạy toàn bộ test suite tự động**:
  - Chạy `pytest -q` đảm bảo 100% test pass.
- [x] **Kịch bản Demo 1: Kiểm tra số lượng camera (10 Cams)**:
  - Hỏi: *"Hiện có bao nhiêu camera đang hoạt động?"*
  - Xác nhận câu trả lời: Báo đủ **10 camera đang hoạt động**, liệt kê theo 3 phân hệ (6 phương tiện, 2 vùng cấm, 2 cháy khói).
- [x] **Kịch bản Demo 2: Kiểm tra danh sách camera**:
  - Hỏi: *"Kể tên các camera trong hệ thống"*
  - Xác nhận danh sách có đủ các camera: `CVN_CONG_BOH`, `CVNTT`, `CVN_KHO_TANG2_BOH`, `CVN_P_CAP_PHAT_DONG_PHUC`, `congchinh1`, `congchinh2`, `congvanle1-4`.
- [x] **Kịch bản Demo 3: Kiểm tra Stream phản hồi**:
  - Gửi câu hỏi bất kỳ, quan sát câu trả lời xuất hiện dần dần từng chữ (hiệu ứng typewriter) trên bubble chat.
- [x] **Kịch bản Demo 4: Đánh giá Tốt (Like 👍)**:
  - Bấm nút 👍 dưới câu trả lời đúng → Nút đổi màu, hiện toast cảm ơn → Mở file `data/feedback.json` kiểm tra bản ghi có `rating: "positive"`.
- [x] **Kịch bản Demo 5: Đánh giá Xấu (Dislike 👎) kèm lý do và ảnh**:
  - Bấm nút 👎 → Modal mở ra → Nhập lý do: *"Số liệu cần chi tiết hơn"* → Chọn 1 file ảnh chụp màn hình → Bấm "Xác nhận gửi phản hồi".
  - Kiểm tra file ảnh được lưu vào `data/feedback/attachments/`.
  - Mở `data/feedback.json`: Xác nhận bản ghi có `rating: "negative"`, có `feedback_reason`, `attachment_path` và đầy đủ `agent_trace` (I/O, SQL, latencies).
- [x] Cập nhật kết quả nghiệm thu cuối cùng vào `specs/change-log.md`.

**Done khi:** Toàn bộ 5 kịch bản demo và unit test đều pass hoàn hảo trên môi trường Docker.
