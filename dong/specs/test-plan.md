# Test Plan — agent dong v8

**Trạng thái:** Spec only — chuẩn bị thực hiện.  
**Mục tiêu:** Kiểm thử toàn diện 3 tính năng mới: Chuẩn hóa 10 camera từ Master Registry, Hệ thống Human Feedback (Like/Dislike + Lý do + Ảnh) và Chunk Streaming câu trả lời.

---

## 1. Phạm vi kiểm thử

| Nhóm tính năng | Mục tiêu kiểm thử | Phương thức |
|----------------|-------------------|-------------|
| **Camera Count (10 Cams)** | Đảm bảo hệ thống trả lời đủ 10 camera (không bị nhầm sang 6 camera giao thông). | Unit test pytest + Live test |
| **Human Feedback API** | API `POST /api/feedback` xử lý đúng payload, lưu file JSON và file ảnh an toàn. | Unit test pytest |
| **Human Feedback UI** | Giao diện nút 👍/👎, modal dislike nhập lý do, upload ảnh và gửi phản hồi. | Manual Browser test |
| **Response Streaming** | SSE stream token/chunk mượt mà, bubble chat hiển thị gõ chữ trực tiếp. | Manual Browser test |
| **Hồi quy hệ thống** | Không làm ảnh hưởng các luồng v7: Text-to-SQL, Chart.js, Guardrails, Memory. | Pytest toàn bộ suite |

---

## 2. Kế hoạch kiểm thử tự động (Unit Tests)

### Test Suite 1: Camera Registry & Multi-domain Count
- **File**: `tests/test_product_sql_agent.py`
- **Các ca kiểm thử**:
  1. `test_query_total_camera_count_returns_10_cams`:
     - Input: *"Hiện có bao nhiêu camera đang hoạt động?"*
     - Kỳ vọng: Câu trả lời chứa số "10", không chứa "6", liệt kê hoặc phân loại theo 3 phân hệ.
  2. `test_query_camera_list_contains_all_10_cameras`:
     - Input: *"Kể tên các camera trong hệ thống"*
     - Kỳ vọng: Kết quả chứa cả các camera ngoài ITS như `CVN_CONG_BOH`, `CVNTT`, `CVN_KHO_TANG2_BOH`, `CVN_P_CAP_PHAT_DONG_PHUC`.

### Test Suite 2: Human Feedback Endpoint
- **File**: `tests/test_product_observability_errors.py` (hoặc test file mới `tests/test_product_feedback.py`)
- **Các ca kiểm thử**:
  1. `test_feedback_positive_saved_successfully`:
     - Gửi request `POST /api/feedback` với `rating="positive"`, `session_id`, `question`, `answer`, `agent_trace`.
     - Kiểm tra status code `200`.
     - Đọc database SQLite `data/feedback.db` (và file `data/feedback.json`), xác nhận bản ghi tồn tại với đầy đủ các trường.
  2. `test_feedback_negative_with_reason_and_image`:
     - Gửi request `POST /api/feedback` với `rating="negative"`, `feedback_reason="Sai số lượng camera"`, ảnh base64 mẫu.
     - Kiểm tra status code `200`.
     - Xác nhận file ảnh được lưu vào `data/feedback/attachments/` và SQLite/JSON ghi nhận đúng đường dẫn ảnh cùng lý do.
  3. `test_feedback_validation_error`:
     - Gửi request thiếu `rating` hoặc `question`.
     - Kiểm tra API trả về status `422 Unprocessable Entity` hoặc `400 Bad Request`.

---

## 3. Kịch bản kiểm thử thủ công (Manual / Smoke Checklist)

| STT | Thao tác trên giao diện | Kỳ vọng đạt được |
|:---:|-------------------------|------------------|
| 1 | Nhập câu hỏi: *"Hiện có bao nhiêu camera đang hoạt động?"* | Trợ lý trả lời chính xác: **10 camera đang hoạt động** (phân loại 6 xe, 2 vùng cấm, 2 cháy khói). Không trả lời 6 camera. |
| 2 | Nhập câu hỏi: *"Kể tên các camera"* | Trợ lý liệt kê đủ danh sách 10 camera (bao gồm cả camera vùng cấm và cháy khói). |
| 3 | Quan sát quá trình hiển thị câu trả lời | Chữ xuất hiện dần dần theo luồng stream (hiệu ứng gõ chữ), không bị khựng lại rồi hiện một khối. |
| 4 | Bấm vào nút Like (👍) dưới câu trả lời | Nút Like sáng lên / đổi màu, hiển thị toast ngắn: "Cảm ơn bạn đã đánh giá!". Kiểm tra SQLite `data/feedback.db` (và file `data/feedback.json`) có bản ghi mới. |
| 5 | Bấm vào nút Dislike (👎) dưới câu trả lời | Hiển thị modal/hộp thoại góp ý: có ô nhập lý do, nút tải ảnh và nút xác nhận. |
| 6 | Nhập lý do: *"Dữ liệu chưa cập nhật đủ"* + đính kèm 1 ảnh chụp màn hình → Bấm "Lưu phản hồi" | Modal đóng lại, hiện thông báo thành công. Mở SQLite `data/feedback.db` / file `data/feedback.json` kiểm tra: có trường `rating: "negative"`, trường `feedback_reason`, đường dẫn file ảnh đính kèm, và `agent_trace` chi tiết. |
| 7 | Mở file `data/feedback.db` (bằng sqlite3) hoặc `data/feedback.json` | Đảm bảo định dạng chuẩn UTF-8, các trường thông tin rõ ràng để AI / Kỹ sư đọc hiểu ngay ngữ cảnh để sửa lỗi. |

---

## 4. Tiêu chí Pass / Fail

- **PASS**:
  - `pytest -q` pass 100% không có lỗi.
  - Cả 7 bước kiểm thử thủ công trên trình duyệt đều hoạt động chính xác như mô tả.
  - SQLite `data/feedback.db` và file `data/feedback.json` lưu trữ đầy đủ, an toàn, không bị ghi đè hay mất dữ liệu khi lưu nhiều lần.
- **FAIL**:
  - Trợ lý vẫn trả lời 6 camera khi hỏi tổng số camera.
  - Bấm Like/Dislike không lưu được vào SQLite/JSON hoặc thiếu `agent_trace`.
  - Câu trả lời vẫn hiển thị kiểu giật cục một lần thay vì stream.
