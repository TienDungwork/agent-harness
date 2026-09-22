# agent dong — VMS Analytics Agent (v6)

Trợ lý tiếng Việt cho VMS KCN Hưng Phú: số liệu read-only, hướng dẫn VMS/AIOC, biểu đồ trực quan, multi-agent orchestrator, bộ nhớ đa tầng (short-term / long-term / TTL cache), live trace graph.

**Trạng thái hiện tại:** v6 — Hoàn thành toàn bộ Phase 1 → 7 (MVP v6 sẵn sàng cho production demo & eval).

---

## 📚 Specs & Tài liệu kỹ thuật

| File | Nội dung chính |
|------|----------------|
| [specs/product-spec.md](specs/product-spec.md) | Mục tiêu app, user flow, bộ nhớ, session UI, 11 acceptance criteria |
| [specs/implementation-plan.md](specs/implementation-plan.md) | Kế hoạch chi tiết triển khai qua từng task |
| [specs/test-plan.md](specs/test-plan.md) | Kế hoạch kiểm thử offline (pytest), live (Docker + 196) và golden-30 |
| [specs/smoke-manual-checklist.md](specs/smoke-manual-checklist.md) | Checklist kiểm thử thủ công Web UI & hướng dẫn smoke test |
| [specs/change-log.md](specs/change-log.md) | Nhật ký chi tiết các thay đổi qua từng phase |
| [AGENTS.md](AGENTS.md) | Hướng dẫn và quy tắc phát triển cho AI agent / Antigravity |

---

## 🏛️ Kiến trúc hệ thống

```text
User Question → [recall_memory] → [rewrite] → [classify]
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
   [query_data]     [docs]     [orchestrator] (multi-agent)
        │             │              │
        └─────────────┼──────────────┘
                      ▼
       [respond] → [extract_memory] → SSE Stream + Chart + Full I/O Live Graph
```

- **Backend:** FastAPI, LangGraph, Uvicorn, PostgreSQL (read-only), Keypool rotation / Self-hosted gateway.
- **Frontend:** Vanilla HTML5, CSS3, JavaScript (SSE stream client, Chart.js, Mermaid / SVG live graph).
- **Resource tĩnh:** Prompts YAML (`resource/prompts/`), Docs YAML (`resource/docs/`), DB Catalog (`resource/db/`).
- **Observability:** Langfuse integration (trace full node I/O).

---

## 📋 Yêu cầu tiên quyết (Prerequisites)

- **Hệ điều hành:** Linux (Ubuntu 20.04/22.04 khuyến nghị), macOS hoặc Windows (WSL2).
- **Docker & Docker Compose:** Docker Engine 24.0+ và Docker Compose v2 (cho đường chạy production).
- **Python:** Python 3.11+ (nếu chạy local development ngoài container).
- **Mạng nội bộ / Gateway:** Kết nối được tới gateway LLM self-hosted `http://192.168.1.196:18083` hoặc có `OPENAI_API_KEYS` cho smoke test.

---

## ⚙️ Cấu hình môi trường (Environment Variables)

Khởi tạo file cấu hình môi trường từ mẫu:

```bash
cd agent-harness/dong
cp .env.example .env
```

Các biến môi trường chính trong `.env`:

| Biến môi trường | Giá trị mặc định / Khuyến nghị | Ý nghĩa & Mục đích |
|-----------------|-------------------------------|-------------------|
| `LLM_BACKEND` | `self_hosted` (hoặc `openai`) | Lựa chọn backend LLM (`self_hosted` cho production, `openai` cho smoke test). |
| `MODEL_BASE_URL` | `http://192.168.1.196:18083/v1` | URL của self-hosted LLM gateway (vLLM / LiteLLM). |
| `MODEL_NAME` | `qwen3-4b` | Tên model phục vụ trên self-hosted gateway. |
| `MODEL_API_KEY` | `""` (hoặc key được cấp) | API key truy cập gateway nội bộ. |
| `OPENAI_API_KEYS` | `sk-...,sk-...` | Danh sách OpenAI API keys (phân tách bởi dấu phẩy, dùng khi `LLM_BACKEND=openai`). |
| `DB_HOST` / `DB_PORT` | `localhost` / `5432` | Địa chỉ máy chủ PostgreSQL. |
| `DB_NAME` / `DB_USER` | `vms_db` / `agent_readonly` | Tên cơ sở dữ liệu và user quyền read-only. |
| `DB_PASSWORD` | `...` | Mật khẩu database. |
| `MEMORY_TTL_SECONDS` | `300` | Thời gian sống (TTL) của bộ nhớ đệm cache kết quả (5 phút). |
| `FRONTEND_PORT` | `8080` | Port truy cập giao diện Web UI frontend. |
| `BACKEND_PORT` | `8000` | Port máy chủ API backend. |
| `MONITORING_ENABLED` | `false` (hoặc `true`) | Bật/tắt gửi telemetry và trace tới Langfuse. |
| `LANGFUSE_HOST` | `http://localhost:3000` | Địa chỉ server Langfuse. |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` | Public API Key của dự án Langfuse. |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` | Secret API Key của dự án Langfuse. |

---

## 🚀 Hướng dẫn chạy Docker (Production Deployment)

Đây là đường chạy chính chuẩn hóa cho toàn bộ hệ thống.

### 1. Khởi động toàn bộ dịch vụ

```bash
docker compose up --build -d
```

Lệnh trên sẽ tự động:
- Build container backend FastAPI (`kcn_hungphu_backend`) trên port 8000.
- Build container frontend Nginx (`kcn_hungphu_frontend`) trên port 8080.
- Thiết lập network `kcn_hungphu_network` và healthcheck tự động.

### 2. Xem logs thời gian thực

```bash
docker compose logs -f
# Hoặc xem riêng backend:
docker compose logs -f ai_backend
```

### 3. Dừng hệ thống

```bash
docker compose down
```

---

## 💻 Hướng dẫn chạy Local Development (Không dùng Docker)

Dành cho nhà phát triển muốn chạy và sửa đổi mã nguồn trực tiếp trên máy host.

### 1. Cài đặt môi trường Backend

```bash
cd agent-harness/dong

# Tạo và kích hoạt virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Trên Windows: .venv\Scripts\activate

# Cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Khởi chạy Backend FastAPI

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

> **Ghi chú:** Backend FastAPI tự động phục vụ giao diện tĩnh Frontend tại đường dẫn gốc `http://localhost:8000/`.

### 3. Khởi chạy Frontend riêng biệt (Tuỳ chọn)

Nếu bạn muốn chạy Frontend qua server tĩnh riêng biệt (ví dụ port 8080):

```bash
# Cách 1: Sử dụng Python HTTP Server
python3 -m http.server 8080 --directory frontend

# Cách 2: Sử dụng container frontend độc lập
docker compose up -d frontend
```

---

## 🔗 Danh sách URL cục bộ (Local URLs)

| Dịch vụ | URL truy cập | Mô tả |
|---------|--------------|-------|
| **Web UI (Nginx)** | `http://localhost:8080` | Giao diện chính người dùng (Chat, Sessions, Live Graph, Chart). |
| **Web UI (FastAPI Direct)** | `http://localhost:8000` | Giao diện phục vụ trực tiếp từ backend khi chạy dev. |
| **Swagger API Docs** | `http://localhost:8000/docs` | Tài liệu API tương tác OpenAPI/Swagger. |
| **ReDoc API Docs** | `http://localhost:8000/redoc` | Tài liệu API định dạng ReDoc. |
| **API Healthcheck** | `http://localhost:8000/api/health` | Kiểm tra trạng thái backend và cấu hình LLM hiện tại. |
| **LLM Connection Ping** | `http://localhost:8000/api/llm/ping` | Kiểm tra kết nối tới LLM gateway / OpenAI. |
| **Langfuse Dashboard** | `http://localhost:3000` | Bảng điều khiển giám sát LLM trace (nếu bật Langfuse). |

---

## 🧪 Kiểm thử & Benchmark (Testing & Eval)

### 1. Chạy Unit & Integration Tests (Offline)

```bash
pytest -q
# Chạy một file test cụ thể:
pytest tests/test_api.py -q
```

### 2. Chạy kịch bản Smoke Test tự động

```bash
./scripts/smoke-production.sh
```

### 3. Chạy đánh giá bộ Benchmark Golden-30

```bash
# Đánh giá tiêu chuẩn:
python eval/run.py

# Đánh giá kèm LLM Judge chấm điểm 1-5:
python eval/run.py --judge

# Kết quả đánh giá sẽ được ghi tại: eval/results/golden-30.md
```

---

## 🔭 Khởi động Langfuse Observability (Tuỳ chọn)

Hệ thống cung cấp stack Langfuse riêng biệt trong thư mục `langfuse/`:

```bash
# Khởi động stack Langfuse (PostgreSQL + Langfuse Server)
cd langfuse && docker compose up -d

# Truy cập giao diện Langfuse tại: http://localhost:3000
# Đăng ký tài khoản admin lần đầu, tạo Project và lấy Public/Secret keys điền vào .env
```

---

## 🛠️ Xử lý sự cố thường gặp (Troubleshooting)

### 1. Lỗi kết nối LLM Gateway (`503 Service Unavailable` hoặc Ping thất bại)
- **Hiện tượng:** `curl http://localhost:8000/api/llm/ping` trả về lỗi kết nối hoặc timeout.
- **Nguyên nhân:** Máy host không kết nối được mạng LAN `192.168.1.196` hoặc service vLLM/gateway chưa khởi động.
- **Cách khắc phục:**
  - Kiểm tra kết nối mạng tới gateway: `curl -s http://192.168.1.196:18083/v1/models`.
  - Nếu test ngoài mạng nội bộ, chuyển `.env` sang `LLM_BACKEND=openai` và cung cấp `OPENAI_API_KEYS`.

### 2. Xung đột cổng mạng (Port Conflict: 8000 hoặc 8080 đã được sử dụng)
- **Hiện tượng:** Docker báo lỗi `bind: address already in use` cho port 8000 hoặc 8080.
- **Cách khắc phục:**
  - Kiểm tra tiến trình đang chiếm cổng: `sudo lsof -i :8000` hoặc `sudo lsof -i :8080`.
  - Hoặc đổi port trong file `.env`: `BACKEND_PORT=8001`, `FRONTEND_PORT=8081`.

### 3. Lỗi quyền truy cập Database PostgreSQL
- **Hiện tượng:** Log backend báo `Permission denied for table ...` hoặc `FATAL: password authentication failed`.
- **Cách khắc phục:**
  - Đảm bảo user database là `agent_readonly` với quyền `SELECT` trên các bảng schema VMS.
  - Kiểm tra kết nối database bằng `psql -h $DB_HOST -U $DB_USER -d $DB_NAME`.

### 4. Lỗi CORS khi chạy Frontend và Backend trên port khác nhau
- **Hiện tượng:** Console trình duyệt báo lỗi `Access to fetch at '...' from origin '...' has been blocked by CORS policy`.
- **Cách khắc phục:**
  - Backend FastAPI đã cấu hình `CORSMiddleware` cho phép mọi origin (`allow_origins=["*"]`).
  - Đảm bảo truy cập qua Nginx reverse proxy tại `http://localhost:8080` (Nginx tự động proxy `/api/` về backend `ai_backend:8000`).

### 5. Xóa bộ nhớ đệm TTL Cache khi cần kiểm thử dữ liệu mới
- **Cách thực hiện:** Khởi động lại backend container hoặc đợi 300 giây để cache tự hết hạn.
```bash
docker compose restart ai_backend
```
