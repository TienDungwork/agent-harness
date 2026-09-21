# Implementation Plan (agent_stat_v3 FE & AI_Backend)

Kế hoạch triển khai từng bước theo chuẩn Spec-Driven Development: chia tách 2 tầng **Frontend (FE)** và **AI_Backend**, **giữ nguyên kiến trúc ReAct Agent hiện tại** để dễ so sánh đối chứng, điều phối trọn gói bằng **Docker Compose**, tích hợp **Langfuse Observability** (đầy đủ output + token tracking), hỗ trợ **Model tự host Qwen3-4B** và giao diện **Claude-inspired UI**.

---

## Phase 1: Project Setup

Thiết lập cấu trúc thư mục phân tách, cấu hình môi trường và quản lý secrets.

### Checklist
- [x] Thiết lập cấu trúc thư mục phân tách rõ ràng:
  - `frontend/`: Chứa mã nguồn giao diện Claude UI (`index.html`, `style.css`, `app.js`).
  - `ai_backend/` (hoặc `backend/` & `src/`): Chứa FastAPI REST API gateway, ReAct Agent, tools, prompt registry, LLM clients, tracing.
- [x] Cập nhật tệp `.env.example` chuẩn (chỉ chứa placeholder rỗng, không chứa secret thật):
  - Nhóm OpenAI: `OPENAI_API_KEYS`, `LLM_MODEL=gpt-4o-mini`.
  - Nhóm Self-hosted Model: `MODEL_BASE_URL=http://192.168.1.196:18083/v1`, `MODEL_NAME=qwen3-4b`, `MODEL_API_KEY=lgw_ef6984db8f59_...`.
  - Nhóm Database Postgres (5 DBs: `its`, `virtual_fence`, `smart_face`, `firesmoke`, `anomaly`).
  - Nhóm Observability: `MONITORING_ENABLED`, `LANGFUSE_HOST=http://localhost:3000`.
- [x] Cấu hình mật khẩu đăng nhập Langfuse mặc định thành `Atin@123#` trong `langfuse/.env` (User: `admin@agent-atin.local`).
- [x] Tối ưu hóa `requirements.txt` với các dependencies cần thiết (FastAPI, uvicorn, pydantic-settings, langgraph, langchain-core, langchain-openai, openai==2.45.0, psycopg2-binary, pyyaml, pytest).
- [x] Xác nhận `pytest` chạy được, import thông suốt.

---

## Phase 2: Core UI (Claude-Inspired Frontend)

Xây dựng giao diện web chat hiện đại, tinh tế phong cách Claude với bảng màu ấm và bố cục trực quan.

### Checklist
- [x] Thiết kế layout giao diện chat (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`):
  - Sidebar: Lịch sử hội thoại, nút "Tạo đoạn chat mới", nút mở "Cài đặt".
  - Main Chat Area: Khung hiển thị tin nhắn (User & Assistant), avatar tối giản, typography rõ nét, bảng màu ấm (warm neutral palette).
  - Input Box: Ô nhập câu hỏi tự co giãn, nút gửi tin nhắn, gợi ý câu hỏi mẫu theo 8 domain sự kiện VMS.
- [x] Xây dựng component hiển thị chi tiết công cụ đã gọi (**Tool Execution Accordion**):
  - Khối accordion có thể thu gọn/mở rộng hiển thị: Công cụ đã chạy, số dòng dữ liệu truy vấn từ DB, thời gian xử lý.
- [x] Xây dựng Modal / Drawer **Cài đặt Model (Settings)**:
  - Cho phép người dùng chuyển đổi giữa `OpenAI Cloud (gpt-4o-mini)` và `Model tự host (qwen3-4b)`.
  - Cho phép cấu hình tùy chỉnh API Base URL (hỗ trợ chạy local, docker hoặc ngrok).
- [x] Tích hợp trình render Markdown (hỗ trợ hiển thị bảng số liệu thống kê, danh sách gạch đầu dòng ngay ngắn).

---

## Phase 3: Core AI_Backend & Data Logic (Giữ nguyên Kiến trúc ReAct Agent)

Duy trì nguyên vẹn cấu trúc ReAct Agent LangGraph hiện tại để đảm bảo độ chính xác và dễ so sánh đối chứng, đồng thời bổ sung hỗ trợ Model tự host Qwen3-4B.

### Checklist
- [x] Cập nhật module kết nối LLM (`ai_backend/llm.py` hoặc `src/llm.py`):
  - Hỗ trợ khởi tạo client tương thích chuẩn OpenAI ChatCompletions trỏ tới cả OpenAI Cloud và Self-hosted endpoint `http://192.168.1.196:18083/v1` (Model: `qwen3-4b`, API Key: `lgw_ef6984db8f59_...`).
  - Duy trì cơ chế quay vòng key khi gặp rate-limit đối với OpenAI.
- [x] Giữ nguyên tập Tool tham số hóa cho cả 8 domain sự kiện VMS (`count_vehicle_flow`, `vehicle_by_manufacturer`, `trace_vehicle`, `count_face_events`, `zone_intrusion_by_hour`, `count_anomaly_events`, `count_fire_smoke_events`).
- [x] Giữ nguyên kiến trúc đồ thị ReAct LangGraph (`build_react_subgraph`: `seed` $\rightarrow$ `agent` $\leftrightarrow$ `tools` $\rightarrow$ `pack`).
- [x] Duy trì Git-based Prompt Registry (`prompts/`) nạp template động qua `production.txt`.
- [x] Duy trì hàm xuất sơ đồ đồ thị ReAct Graph `save_graph_visualization(...)` hỗ trợ xuất Mermaid, HTML và PNG.

---

## Phase 4: Connect UI to AI_Backend Data

Xây dựng REST API Gateway với FastAPI và kết nối giao diện Frontend với AI_Backend.

### Checklist
- [x] Hoàn thiện ứng dụng FastAPI (`ai_backend/main.py` hoặc `backend/main.py`):
  - Router `/api/health`: Kiểm tra trạng thái kết nối tới 5 Database Postgres và endpoint LLM.
  - Router `/api/models`: Trả về danh sách model hỗ trợ (OpenAI Cloud `gpt-4o-mini`, Self-hosted `qwen3-4b`) và model đang kích hoạt.
  - Router `/api/config`: Cung cấp thông tin cấu hình an toàn cho Frontend (không lộ secret).
  - Router `/api/chat` (hoặc `/ask`): Nhận câu hỏi từ Frontend `{"question": "...", "model_override": "..."}`, điều phối qua ReAct Agent và trả về `{"answer": "...", "detail": {...}}`.
- [x] Kết nối Frontend với Backend API:
  - Tích hợp hàm `fetch('/api/chat')` từ `frontend/app.js` gửi request và nhận phản hồi.
  - Hiển thị hiệu ứng loading / thinking state mượt mà trong khi chờ backend phản hồi.
  - Render câu trả lời và đổ dữ liệu vào accordion "Tool Execution Detail".

---

## Phase 5: Observability & Token Metrics (Langfuse)

Nâng cấp module giám sát để thu thập đầy đủ chi tiết mọi cuộc gọi LLM và liên kết với hạ tầng Langfuse.

### Checklist
- [x] Cải tiến `tracing.py` (`ai_backend/monitoring/tracing.py` hoặc `src/monitoring/tracing.py`):
  - Đảm bảo mọi trace cha (`ask`/`chat`) và span con (`chon_tool`, `chay_tool`, `dien_giai`) luôn lưu trữ đầy đủ trường `output`.
  - Trích xuất và ghi nhận thông số token: `prompt_tokens`, `completion_tokens`, `total_tokens` từ metadata phản hồi của LLM.
  - Ghi nhận thông số cấu hình: `model_name`, `temperature`, `latency_s`.
- [x] Đảm bảo cơ chế Fail-safe & No-op:
  - Khi `MONITORING_ENABLED=false` hoặc khi Langfuse server tạm thời down, hệ thống bắt lỗi an toàn và tiếp tục trả lời bình thường, không làm crash API.
- [x] Viết unit test offline xác nhận hàm tracing hoạt động trơn tru.

---

## Phase 6: Validation, Guardrails and Error States

Bảo vệ hệ thống bằng các lớp kiểm soát an toàn và xử lý ngoại lệ chu đáo.

### Checklist
- [x] Củng cố Input Guardrails:
  - Chặn triệt để prompt injection độc hại bằng regex (không qua LLM để tối ưu tốc độ).
  - Từ chối lịch sự các câu hỏi ngoài phạm vi thống kê VMS KCN Hưng Phú (thời tiết, giải trí...).
- [x] Củng cố Output Guardrails:
  - Đối chiếu số liệu trong câu trả lời với kết quả thực tế từ Tool (chống hallucination).
  - Che giấu thông tin cá nhân nhạy cảm (PII redaction) và giới hạn độ dài câu trả lời.
- [x] Xử lý trạng thái lỗi trên Backend và Frontend:
  - Thông báo thân thiện khi mất kết nối Database hoặc timeout khi gọi model tự host.
  - Frontend hiển thị cảnh báo lỗi rõ ràng, không để xảy ra hiện tượng "im lặng" hoặc treo trang.
- [x] Chạy bộ kiểm thử `pytest -v` đảm bảo toàn bộ guardrail test cases đều passed.

---

## Phase 7: Docker Compose Orchestration

Đóng gói các thành phần thành container Docker và điều phối bằng một cấu hình thống nhất.

### Checklist
- [x] Viết `frontend/Dockerfile`:
  - Sử dụng Nginx Alpine nhẹ phục vụ file tĩnh và reverse proxy các request `/api` sang backend.
- [x] Viết `ai_backend/Dockerfile` (hoặc `backend/Dockerfile`):
  - Sử dụng Python 3.11 slim, cài đặt dependencies và khởi chạy FastAPI app với Uvicorn.
- [x] Viết tệp điều phối chính `docker-compose.yml` tại thư mục gốc:
  - Service `frontend`: Expose cổng `8080` (hoặc `3001`).
  - Service `ai_backend`: Expose cổng `8000`.
  - Service `langfuse` stack: Expose cổng `3000` (đăng nhập: `admin@agent-atin.local` / `Atin@123#`).
  - Cấu hình bridge network nội bộ liên thông giữa FE, AI_Backend, Langfuse và kết nối host Postgres.
- [x] Xác nhận lệnh `docker compose up -d` và `docker compose down` hoạt động hoàn hảo.

---

## Phase 8: Local Run Instructions & Demo Setup

Cập nhật tài liệu hướng dẫn vận hành cục bộ và thiết lập demo công khai.

### Checklist
- [x] Cập nhật `README.md` với đầy đủ hướng dẫn:
  - Hướng dẫn 1 lệnh khởi chạy trọn gói qua Docker Compose (`docker compose up -d`).
  - Hướng dẫn khởi chạy local standalone cho từng thành phần (Frontend, AI_Backend, Langfuse).
  - Bảng tổng hợp cổng và URL truy cập (`:8080`, `:8000`, `:3000`).
  - Hướng dẫn đăng nhập Langfuse Dashboard với mật khẩu `Atin@123#`.
- [x] Hướng dẫn demo qua `ngrok`:
  - Lệnh expose cổng Frontend: `ngrok http 8080`.
  - Hướng dẫn cấu hình API Base URL trên giao diện Frontend để demo từ xa.

---

## Phase 9: Golden Dataset Evaluation & E2E Verification

Đánh giá toàn diện chất lượng câu trả lời trên cả 8 domain sự kiện VMS và xuất sơ đồ đồ thị ReAct Graph.

### Checklist
- [x] Chạy bộ 30 câu hỏi mẫu (`eval/run.py`):
  - Đảm bảo 100% (30/30) câu hỏi mẫu đạt chuẩn (pass) trên cả 8 domain sự kiện.
  - Đảm bảo 3 case injection và 3 case out_of_scope vẫn hoạt động chính xác.
- [x] Kiểm thử Live E2E với Model tự host `qwen3-4b` tại `http://192.168.1.196:18083/v1`:
  - Xác nhận câu trả lời có số liệu thật chính xác và thời gian phản hồi nhanh.
- [x] Mở Langfuse UI (`http://localhost:3000` mật khẩu `Atin@123#`):
  - Xác nhận trace hiển thị đủ cây span, đầy đủ `output` và thống kê token metrics (`prompt_tokens`, `completion_tokens`, `total_tokens`).
- [x] Chạy lệnh xuất lại toàn bộ sơ đồ đồ thị ReAct Graph (`graph.png`, `graph_diagram.html`):
  ```bash
  python3 -m src.agent.graph
  ```
- [x] Cập nhật nhật ký hoàn thành vào `specs/change-log.md`.
