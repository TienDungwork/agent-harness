# Test Plan (agent_stat_v3 FE & AI_Backend)

Kế hoạch kiểm thử toàn diện cho hệ thống: Phân tách Frontend & AI_Backend, giữ nguyên kiến trúc ReAct Agent hiện tại, điều phối bằng Docker Compose, nâng cấp Langfuse output + token metrics, hỗ trợ Model tự host Qwen3-4B và giao diện Claude UI.

---

## 1. Nguyên Tắc Kiểm Thử
- **Test Offline (`pytest`)**: Không cần kết nối Postgres hay LLM API thật; có thể chạy độc lập ở môi trường local/CI, kiểm tra cấu trúc ReAct graph, guardrails và mock client.
- **Test Thật (Live E2E)**: Cần kết nối tới Postgres VMS và LLM backend (OpenAI hoặc Self-hosted Qwen3-4B), kiểm tra luồng hỏi-đáp thực tế và độ chính xác số liệu trên cả 8 domain.
- **Test Observability**: Kiểm tra việc ghi nhận trace trên Langfuse (đủ output, token usage, độ trễ) và đăng nhập với mật khẩu `Atin@123#`.
- **Test Container hóa**: Kiểm tra khả năng khởi động đồng bộ và liên lạc giữa các service qua `docker compose up -d`.

---

## 2. Test Offline (Pytest)

| # | Test Case | Kỳ vọng |
|---|---|---|
| 1 | **Guardrail Input — Prompt Injection** | Câu hỏi độc hại ("Ignore instructions...") bị chặn ngay tại backend, trả lỗi HTTP 400 rõ ràng, không gọi agent |
| 2 | **Guardrail Input — Ngoài phạm vi** | Câu hỏi thời tiết, nấu ăn... bị từ chối lịch sự, không gọi DB |
| 3 | **Agent ReAct Offline** | Câu hỏi hợp lệ chạy offline không crash, trả về kết quả hợp lệ |
| 4 | **Tool Whitelist & Read-only** | Tool SQL chặn tuyệt đối câu lệnh ghi (`DELETE`, `UPDATE`, `DROP`); tham số ngoài whitelist bị từ chối |
| 5 | **Prompt Registry Integration** | `PromptRegistry` đọc đúng file YAML, render đúng biến và báo lỗi `ValueError` nếu thiếu biến |
| 6 | **Tracing No-op Offline** | Khi `MONITORING_ENABLED=false`, các hàm tracing hoạt động bình thường như no-op, không phát sinh lỗi |
| 7 | **Backend Endpoints** | `/api/health` và `/api/models` trả về `200 OK` với danh sách model chính xác |

---

## 3. Test Thật: LLM Tự Host (`qwen3-4b`) vs OpenAI

Kiểm thử khả năng tương thích và phản hồi trên cả 2 backend LLM:

| # | Backend | Endpoint / Model | Tiêu chí Đạt (Acceptance) |
|---|---|---|---|
| 1 | **Self-hosted LLM** | `http://192.168.1.196:18083/v1`<br>Model: `qwen3-4b` | Khởi tạo client thành công qua `MODEL_API_KEY`, gọi `chat/completions` sinh câu trả lời tiếng Việt chính xác theo số liệu thật |
| 2 | **OpenAI Cloud** | `https://api.openai.com/v1`<br>Model: `gpt-4o-mini` | Hoạt động bình thường với key rotation khi gặp rate-limit |
| 3 | **Chuyển đổi Backend** | Thay đổi qua biến `.env` hoặc UI | Hệ thống chuyển đổi ngay lập tức mà không cần sửa code logic |

---

## 4. Test Langfuse Observability & Token Usage

Kiểm tra trực tiếp trên hạ tầng Langfuse self-hosted:

| # | Mục Kiểm Tra | Thao Tác & Dữ Liệu | Tiêu chí Đạt |
|---|---|---|---|
| 1 | **Đăng nhập Quản trị** | Truy cập `http://localhost:3000`<br>User: `admin@agent-atin.local`<br>Password: `Atin@123#` | Đăng nhập thành công vào Dashboard dự án `agent_ATIN` |
| 2 | **Lưu trữ Đầy đủ Output** | Gửi 1 câu hỏi qua API → Mở trace trên Langfuse | Cả trace cha (`ask`/`chat`) và các span con (`chon_tool`, `chay_tool`, `dien_giai`) đều hiển thị trường `output` đầy đủ |
| 3 | **Token Usage Metrics** | Kiểm tra chi tiết observation thế hệ LLM | Có đầy đủ thông số: `prompt_tokens > 0`, `completion_tokens > 0`, `total_tokens = prompt + completion` |
| 4 | **Model & Latency Info** | Kiểm tra trường metadata của trace | Hiển thị chính xác tên model (`gpt-4o-mini` hoặc `qwen3-4b`), `latency_s` đo thời gian thực thi |
| 5 | **Bảo mật Secret** | Rà soát toàn bộ payload của trace | Tuyệt đối **không xuất hiện** API keys thật (`sk-proj-...`, `lgw_...`) hay mật khẩu DB |
| 6 | **Khả năng Chịu lỗi (Resilience)** | Tắt tạm thời container Langfuse rồi gửi câu hỏi | API vẫn trả lời câu hỏi bình thường, không crash hệ thống (lỗi tracing được tự động bắt và log) |

---

## 5. Test Giao Diện Frontend (Claude-Inspired UI)

| # | Tính Năng UI | Thao Tác | Tiêu chí Đạt |
|---|---|---|---|
| 1 | **Thẩm mỹ & Bố cục** | Mở trình duyệt tại `http://localhost:8080` (hoặc cổng FE) | Giao diện hiện đại phong cách Claude, tone màu ấm, typography rõ nét, responsive |
| 2 | **Cấu hình Model** | Mở menu cấu hình model | Hiển thị danh sách model khả dụng, cho phép chuyển đổi giữa OpenAI và Self-hosted Qwen3-4B |
| 3 | **Tool Execution Accordion** | Gửi câu hỏi thống kê | Hiển thị khối "Chi tiết công cụ đã thực thi" dạng accordion, cho phép thu gọn/mở rộng xem tool nào đã chạy |
| 4 | **Markdown Rendering** | Câu trả lời có bảng số liệu và danh sách | Bảng biểu HTML/Markdown render ngay ngắn, dễ nhìn |
| 5 | **Trạng thái Trực quan** | Khi hệ thống đang truy vấn | Hiển thị indicator đang xử lý / loading animation mượt mà |

---

## 6. Test Điều Phối Docker Compose

| # | Lệnh / Kịch Bản | Tiêu chí Đạt |
|---|---|---|
| 1 | `docker compose up -d` | Cả 3 nhóm service (`frontend`, `ai_backend`, `langfuse` stack) khởi động `Up (healthy)` mà không có lỗi |
| 2 | Kết nối nội bộ FE → AI_Backend | Nginx proxy hoặc fetch từ FE gọi thành công `http://ai_backend:8000/api/...` |
| 3 | Kết nối AI_Backend → DB / LLM | Backend truy vấn được Postgres VMS và gọi được endpoint LLM (`http://192.168.1.196:18083/v1`) |
| 4 | `docker compose down` | Dừng an toàn toàn bộ container, dữ liệu Langfuse Postgres / ClickHouse được giữ nguyên trong docker volume |

---

## 7. Đánh Giá Golden Dataset (30 Case) trên 8 Domain VMS

Chạy bộ đánh giá chuẩn:
```bash
python3 eval/run.py
```
- **Kỳ vọng**: Đạt **30/30 passed (100%)** bao gồm cả 8 domain sự kiện VMS, 3 case prompt injection, và 3 case out_of_scope.

---

## 8. Xuất & Kiểm Tra Sơ Đồ Đồ Thị ReAct Graph

Chạy lệnh xuất sơ đồ sau khi hoàn tất toàn bộ code:
```bash
python3 -m src.agent.graph
```
- **Kỳ vọng**:
  - Tạo/cập nhật thành công tệp ảnh `graph.png` và tệp HTML trực quan `graph_diagram.html`.
  - Sơ đồ phản ánh chính xác cấu trúc ReAct Graph: `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`.
