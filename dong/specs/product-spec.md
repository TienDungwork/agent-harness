# Product Spec (agent_stat_v3)

## App Goal
Tái cấu trúc và phát triển hệ thống hỏi-đáp AI phục vụ giám sát, thống kê toàn bộ 8 loại sự kiện camera AI trên nền tảng VMS tại Khu công nghiệp Hưng Phú. Hệ thống được xây dựng tinh gọn, dễ đọc, dễ bảo trì (tham khảo phong cách `llm-engineer-demo`), chia tách độc lập giữa **Frontend (FE)** và **AI_Backend**, điều phối trọn gói bằng **Docker Compose**, **giữ nguyên kiến trúc ReAct Agent hiện tại** để dễ so sánh đối chứng hiệu năng, nâng cấp giám sát **Langfuse** (đầy đủ output và token metrics) và hỗ trợ **Model LLM tự host (Qwen3-4B)**.

Hệ thống bao quát đầy đủ 8 nhóm sự kiện camera AI:
1. **Nhận diện khuôn mặt** (`smart_face.smf_face_events`)
2. **Giám sát phương tiện** (`its.plate_event`)
3. **Giám sát vùng cấm / hàng rào ảo** (`virtual_fence.zone_event`)
4. **Phát hiện ẩu đả** (`anomaly.anomaly_event` — `FIGHT_DETECTION`)
5. **Phát hiện đám đông** (`anomaly.anomaly_event` — `CROWD_DETECTION`)
6. **Phát hiện leo trèo** (`anomaly.anomaly_event` — `INTRUSION_DETECTION`)
7. **Phát hiện cháy khói** (`firesmoke.fire_smoke_event`)
8. **Giám sát mực nước** (`anomaly.anomaly_event` — `WATER_LEVEL_DETECTION`)

---

## Target Users
- **Ban Quản lý & Đội ngũ Vận hành an ninh, hạ tầng KCN Hưng Phú**: Cần tra cứu số liệu thống kê nhanh chóng bằng tiếng Việt tự nhiên, không cần viết câu lệnh SQL.
- **Kỹ sư AI / Vận hành Hệ thống (LLMOps)**: Theo dõi trực quan vết suy luận của agent, số lượng token tiêu thụ, độ trễ và quản lý phiên bản prompt qua Langfuse.

---

## Core User Flow
1. **Truy cập Giao diện**: Người dùng mở trình duyệt truy cập Frontend UI (phong cách Claude UI tinh tế, hiện đại).
2. **Cấu hình Model**: Người dùng có thể kiểm tra hoặc chuyển đổi giữa OpenAI Cloud (`gpt-4o-mini`) và Model LLM tự host (`qwen3-4b`).
3. **Đặt Câu hỏi**: Nhập câu hỏi tự nhiên bằng tiếng Việt (ví dụ: *"Hôm nay có bao nhiêu lượt xe vào?"* hoặc *"Có cảnh báo cháy hay ẩu đả nào hôm nay không?"*).
4. **Xử lý tại AI_Backend**:
   - Kiểm tra Guardrails đầu vào (chặn prompt injection, lọc câu hỏi ngoài phạm vi).
   - Chạy **ReAct Agent hiện tại** (`build_react_subgraph`: `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`) để chọn tool và truy vấn số liệu thật từ Postgres (read-only role `agent_readonly`).
   - Diễn giải kết quả qua LLM Answer node (hoặc template nhanh) kết hợp với Git-based Prompt Registry (`prompts/`).
   - Kiểm tra Guardrails đầu ra (chống hallucination, che giấu PII).
5. **Phản hồi Trực quan**: FE hiển thị câu trả lời rõ ràng kèm chi tiết công cụ đã thực thi (collapsible execution accordion).
6. **Langfuse Observability**: Ghi nhận toàn bộ trace (đầy đủ `input`, `output`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `model_name`, `latency_s`).

---

## Features In Scope

### 1. Phân Tách Độc Lập Frontend & AI_Backend
- **Frontend (`frontend/`)**: Giao diện Claude-inspired trực quan, nhẹ, dễ chỉnh sửa; hỗ trợ cấu hình API endpoint và chuyển đổi Model Provider.
- **AI_Backend (`backend/` / `src/`)**: FastAPI service chứa toàn bộ API Gateway, Agent ReAct, Database Tools, Guardrails và Observability.
- **Giữ nguyên Kiến trúc Agent ReAct**: Duy trì nguyên vẹn mô hình ReAct LangGraph (`seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`) với 8 domain sự kiện VMS để bảo đảm tính tương thích và dễ so sánh đối chứng.

### 2. Quản Lý Điều Phối Trọn Gói (Docker Compose)
- Tệp `docker-compose.yml` tại thư mục gốc quản lý khởi chạy đồng bộ:
  - Service `frontend`: Web server phục vụ Claude UI.
  - Service `ai_backend`: FastAPI server kết nối Agent, Tools và Postgres.
  - Service `langfuse` stack: Langfuse Web, Worker, ClickHouse, Postgres nội bộ, Redis, MinIO.

### 3. Nâng Cấp Langfuse Observability Toàn Diện
- **Lưu trữ Đầy đủ Output**: Bắt buộc ghi nhận trường `output` trên toàn bộ trace và child span.
- **Token Usage & Call Metrics**: Thu thập chi tiết thông số mỗi lượt gọi LLM: `prompt_tokens`, `completion_tokens`, `total_tokens`, `model_name`, `temperature`, `latency_s`.
- **Mật khẩu Quản trị Mặc định**: Tài khoản `admin@agent-atin.local` đăng nhập với mật khẩu: **`Atin@123#`**.

### 4. Hỗ Trợ Dual Model (OpenAI Cloud & Model Tự Host)
- Chuyển đổi linh hoạt giữa:
  - **OpenAI Cloud**: `gpt-4o-mini` (hỗ trợ quay vòng key khi gặp rate-limit).
  - **Model tự host (Local/Self-hosted)**:
    - Base URL: `http://192.168.1.196:18083/v1`
    - Model: `qwen3-4b`
    - API Key: `lgw_ef6984db8f59_zSvqDWXxYzeaU-4U0pLqS7LBiD5gvOm9wI7R-L4Lpqw`
    - Endpoint: `http://192.168.1.196:18083/v1/chat/completions`

### 5. Git-based Prompt Registry
- Tiếp tục duy trì quản lý prompt qua file YAML và con trỏ `production.txt` trong `prompts/`.

---

## Features Out of Scope (Bản v3 MVP)
- Thay đổi cấu trúc Agent sang Multi-agent swarm (giữ nguyên cấu trúc ReAct hiện tại để đối chứng).
- Text-to-SQL tự do (duy trì function calling an toàn trên bộ tool cố định).
- Vector DB / RAG cho dữ liệu phi cấu trúc.
- Cảnh báo đẩy chủ động thời gian thực qua WebSocket/Telegram.
- Kubernetes clustering hoặc hạ tầng cloud phức tạp.

---

## Acceptance Criteria
1. **Khởi chạy 1 lệnh**: `docker compose up -d` khởi động đồng bộ và thành công cả 3 cụm: Frontend, AI_Backend, và Langfuse.
2. **Giao diện Claude-inspired**: UI thẩm mỹ cao, hiển thị lịch sử chat, có accordion xem chi tiết công cụ thực thi, cho phép chuyển đổi model.
3. **Phân tách Rõ ràng**: Cấu trúc thư mục `frontend/` và `backend/` tách bạch, có thể chạy và kiểm thử độc lập.
4. **Giữ nguyên Kiến trúc Agent ReAct**: Graph ReAct hiện tại hoạt động ổn định, trả lời chính xác số liệu cho cả 8 domain sự kiện VMS.
5. **Langfuse Observability Đầy đủ**:
   - Đăng nhập được vào Langfuse UI (`http://localhost:3000`) với email `admin@agent-atin.local` và mật khẩu `Atin@123#`.
   - Mọi lượt gọi `/api/chat` (hoặc `/ask`) đều tạo trace có đầy đủ `output` và token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`).
6. **Hoạt động với Model Tự Host**: Agent phản hồi chính xác khi cấu hình sử dụng model tự host `qwen3-4b` tại `http://192.168.1.196:18083/v1`.
7. **Đạt chuẩn Kiểm thử**: Đạt 100% pass trên bộ 24 unit tests offline và 30 câu hỏi mẫu golden dataset (`eval/run.py`).
