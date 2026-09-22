# Checklist Smoke Test Thủ Công (Manual UI) & API — Production Live

Tài liệu này cung cấp danh mục kiểm thử thủ công (manual checklist) trên giao diện Web UI (`http://localhost:8080`) kết hợp kiểm tra API tự động thông qua script [scripts/smoke-production.sh](../scripts/smoke-production.sh) trên môi trường Docker Production live (LLM `self_hosted` gateway `192.168.1.196:18083` và database PostgreSQL read-only).

---

## 1. Điều kiện tiên quyết (Preconditions)

Trước khi thực hiện kiểm thử:
1. **Khởi động Docker stack**:
   ```bash
   cd agent-harness/dong
   docker compose up --build -d
   ```
2. **Kiểm tra kết nối gateway & health**:
   ```bash
   ./scripts/verify-docker-self-hosted.sh
   ```
   *Yêu cầu:* Phải trả về `OK` cho cả `/api/health` (`llm_backend=self_hosted`) và `/api/llm/ping` (`status=ok`, model `qwen3-4b`).
3. **Mở trình duyệt Web UI**:
   - Truy cập: `http://localhost:8080` (hoặc port của frontend container).

---

## 2. Danh mục kiểm thử thủ công trên Giao diện Web UI

| # | Hạng mục kiểm thử | Thao tác thực hiện | Kết quả kỳ vọng (Pass Criteria) | Trạng thái |
|---|-------------------|--------------------|---------------------------------|:----------:|
| **1** | **Sidebar — Quản lý Session** | 1. Nhấp nút **"+ Tạo phiên mới"** trên sidebar bên trái.<br>2. Gửi 1 câu hỏi bất kỳ (vd: "Xin chào").<br>3. Tạo tiếp phiên mới thứ hai và gửi câu hỏi khác.<br>4. Nhấp chuyển đổi giữa 2 phiên trên sidebar. | - Session mới xuất hiện trong danh sách kèm tiêu đề tự động.<br>- Chuyển đổi giữa các phiên: Lịch sử tin nhắn của từng phiên được tải lại đầy đủ (preview tin nhắn chính xác, không bị lẫn lộn giữa các phiên).<br>- Nút xóa phiên hoạt động đúng khi cần xóa. | `[ ]` |
| **2** | **Short-term Memory (Ngữ cảnh)** | Tại cùng một session đang mở, thực hiện 2 lượt liên tiếp:<br>- Turn 1: Gửi *"Tên tôi là An."*<br>- Turn 2: Gửi *"Tên tôi là gì?"* | - Cả 2 lượt phản hồi thành công (HTTP 200, hiển thị bong bóng chat).<br>- Tại Turn 2: Trợ lý ghi nhớ tên người dùng từ Turn 1 và trả lời có chứa tên *"An"* (hoặc diễn đạt nhận biết danh xưng người hỏi). | `[ ]` |
| **3** | **TTL Response Cache (300s)** | 1. Gửi câu hỏi thống kê: *"Hôm nay có bao nhiêu lượt xe vào?"*<br>2. Chờ nhận câu trả lời hoàn tất.<br>3. Ngay sau đó (trong vòng 5 phút), gửi lại **chính xác** câu hỏi trên. | - Lần 1: Live graph kích hoạt các node `recall_memory` → `rewrite` → `classify` → `query_data` → `respond`.<br>- Lần 2: Cột Live Graph kích hoạt node **`cache`** (màu xanh lá) ngay lập tức; câu trả lời xuất hiện với độ trễ cực thấp (không cần gọi lại LLM hay truy vấn DB). | `[ ]` |
| **4** | **Bar Chart (Biểu đồ cột)** | Gửi câu hỏi: *"Vẽ biểu đồ cột lượt xe theo loại hôm nay"* | - Phía trên tin nhắn trả lời xuất hiện thẻ biểu đồ với canvas **Chart.js** dạng cột (`bar`).<br>- Các cột thể hiện số lượng theo từng loại xe (CAR, TRUCK, MOTORBIKE,...).<br>- Rê chuột (hover) vào từng cột hiển thị tooltip dữ liệu chi tiết.<br>- Có thể phóng to hoặc xem hình ảnh PNG dự phòng khi nhấp vào tab xem trước. | `[ ]` |
| **5** | **Pie Chart (Biểu đồ tròn)** | Gửi câu hỏi: *"Vẽ biểu đồ tròn tỷ lệ loại xe"* | - Phía trên tin nhắn trả lời xuất hiện canvas **Chart.js** dạng hình tròn / bánh (`pie` hoặc `doughnut`).<br>- Phân bổ tỷ lệ phần trăm theo loại xe rõ ràng, có legend chú thích màu cho từng loại xe.<br>- Hover vào từng lát cắt hiển thị phần trăm / số lượng tương ứng. | `[ ]` |
| **6** | **Cảnh báo Cháy / Khói (Fire #010)** | Gửi câu hỏi: *"Hôm nay có cảnh báo cháy hoặc khói không?"* | - Trợ lý tiếp nhận và xử lý (đồ thị điều hướng qua chuyên gia sự kiện an ninh/cháy nổ hoặc SQL).<br>- Trả lời 200, nội dung rõ ràng, nêu rõ hiện trạng cảnh báo trong ngày (không bị rỗng, không crash). | `[ ]` |
| **7** | **Hướng dẫn AIOC Camera (AIOC #014/015)** | Gửi câu hỏi: *"Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?"* | - Trợ lý tra cứu tài liệu nghiệp vụ AIOC.<br>- Phản hồi đầy đủ các bước thao tác trên màn hình Quản lý Camera của AIOC, chứa các từ khóa chuyên môn như: `AIOC`, `camera`, `thiết bị`. | `[ ]` |
| **8** | **Live Graph Hover & Trace JSON** | Trong hoặc sau khi nhận phản hồi từ bất kỳ câu hỏi nào, rê chuột (hover) vào các node trên sơ đồ Live Graph bên phải (như `classify`, `docs`, `query_data`, `respond`). | - Hiển thị popup tooltip chứa chi tiết JSON của node:<br>  + `node_id`<br>  + `status` (`done` / `running`)<br>  + `input` và `output`<br>  + Thời gian thực thi.<br>- Định dạng JSON chuẩn đẹp, không bị tràn màn hình. | `[ ]` |

---

## 3. Kiểm tra tự động hóa qua Script (API Companion)

Bên cạnh thao tác tay trên trình duyệt, toàn bộ 7 ca kiểm thử cốt lõi trên API (Session, Short-term memory, TTL cache, Bar chart, Pie chart, Fire warning, AIOC docs) được tự động hóa thông qua script:

```bash
# Chạy toàn bộ 7 case với cấu hình mặc định (port 8000)
./scripts/smoke-production.sh
```

### Các biến môi trường tùy chọn:
- `BACKEND_PORT`: Cổng backend FastAPI (mặc định: `8000`).
- `BASE_URL`: Địa chỉ gốc của backend (mặc định: `http://localhost:${BACKEND_PORT}`).
- `SMOKE_USER_ID`: ID người dùng tạo ra cho phiên test (mặc định: `smoke-user-<timestamp>`).
- `TIMEOUT_SECONDS`: Thời gian chờ tối đa cho mỗi lượt stream SSE (mặc định: `120`).
- `SKIP_PRECHECK`: Đặt bằng `1` nếu muốn bỏ qua bước chạy `verify-docker-self-hosted.sh`.

Ví dụ chạy tùy biến:
```bash
BACKEND_PORT=8000 TIMEOUT_SECONDS=90 ./scripts/smoke-production.sh
```

### Tiêu chí nghiệm thu:
- Script trả về mã thoát `0` (`exit 0`).
- Đạt kết quả `7/7 CASES PASSED (100%)`.
