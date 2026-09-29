# agent dong — VMS Analytics Multi-Agent (v9: Unified Memory & Context Engineering)

Trợ lý tiếng Việt thông minh cho hệ thống VMS KCN Hưng Phú: truy vấn số liệu read-only (Text-to-SQL), Master Data Registry 10 camera AIOC, hướng dẫn vận hành VMS/AIOC, trực quan hóa biểu đồ (Chart.js & PNG), phản hồi dạng stream SSE mượt mà, hệ thống đánh giá Human Feedback, và **Hệ thống Memory & Context Engineering 3 tầng chuẩn Enterprise (Short-Term, Long-Term, TTL Cache) lưu trữ bền vững trên PostgreSQL**.

---

## 📑 Specs & Tài liệu tham chiếu (Spec-Driven Development)

| File | Nội dung |
|------|----------|
| [specs/product-spec.md](specs/product-spec.md) | Mục tiêu v9: Hệ thống Memory 3 tầng + Context Engineering Engine, cấu trúc PostgreSQL persistence, tiêu chí nghiệm thu AC-1 đến AC-8 |
| [specs/implementation-plan.md](specs/implementation-plan.md) | Kế hoạch triển khai tuần tự Phase 1–7 bám sát nguyên tắc Clean Architecture & SDD |
| [specs/test-plan.md](specs/test-plan.md) | Kế hoạch kiểm thử tự động (Unit tests Context/Postgres/Cache/Short-term) và manual smoke checklist |
| [specs/change-log.md](specs/change-log.md) | Nhật ký thay đổi và đánh giá qua từng phase phát triển |
| [AGENTS.md](AGENTS.md) | Quy chuẩn hành vi và nguyên tắc thực thi dành cho AI Coding Agent |

---

## 🏗️ Kiến trúc luồng thực thi & Context Engineering (v9)

```text
                             [ Người dùng gửi câu hỏi ]
                           (question, user_id, session_id)
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │    TẦNG 1: TTL Response Cache         │
                      │    (SHA-256 Hash, TTL = 300s)         │
                      └───────────────────┬───────────────────┘
                                          │
                       [Hit] ─────────────┴───────────── [Miss]
                         │                                 │
                         ▼                                 ▼
               [ Trả ngay câu trả lời ]        ┌───────────────────────┐
                    (Latency < 5ms)            │ TẦNG 2: Long-Term     │
                                               │ Memory Recall         │
                                               │ (PostgreSQL/Fallback) │
                                               └───────────┬───────────┘
                                                           │
                                                           ▼
                                               ┌───────────────────────┐
                                               │ TẦNG 3: Context       │
                                               │ Engineering Engine    │
                                               │ - Context-Usage (40%) │
                                               │ - Summarize Old Msg   │
                                               │ - Sliding Window (N)  │
                                               │ - Re-inject Core Rule │
                                               └───────────┬───────────┘
                                                           │
                                                           ▼
                                               ┌───────────────────────┐
                                               │  Agent Orchestrator   │
                                               │  (Guardrail -> Router)│
                                               └───────────┬───────────┘
                                                           │
                                  ┌────────────────────────┼────────────────────────┐
                                  ▼                        ▼                        ▼
                           [ respond_inline ]       [ retrieve_docs ]        [ Text-to-SQL ]
                           (chào hỏi/out of scope)  (hướng dẫn VMS/AIOC)     (truy vấn Postgres)
                                  │                        │                        │
                                  │                        │        [Tool Compression]
                                  │                        │        (nén bảng SQL/docs dài)
                                  │                        │                        │
                                  └────────────────────────┼────────────────────────┘
                                                           │
                                                           ▼
                                               ┌───────────────────────┐
                                               │ Extract & Store Fact  │
                                               │ (Ghi PostgreSQL       │
                                               │  bảng user_memories)  │
                                               └───────────┬───────────┘
                                                           │
                                                           ▼
                                               ┌───────────────────────┐
                                               │ Set TTL Cache & Stream│
                                               │ (Lưu cache và SSE)    │
                                               └───────────────────────┘
```

---

## 📋 1. Prerequisites (Yêu cầu hệ thống)

Trước khi cài đặt và chạy ứng dụng, hãy đảm bảo môi trường máy của bạn đáp ứng các yêu cầu sau:

- **Hệ điều hành:** Linux (Ubuntu 20.04/22.04 LTS), macOS, hoặc Windows (PowerShell / WSL2).
- **Python:** Phiên bản `>= 3.10` (khuyên dùng Python 3.11 hoặc 3.12).
- **Công cụ dòng lệnh:** `git`, `curl`.
- **Docker & Docker Compose (tùy chọn):** Docker Engine `>= 20.10`, Docker Compose v2.
- **Dịch vụ phụ trợ:**
  - **PostgreSQL Database:** Lưu trữ dữ liệu nghiệp vụ VMS và dữ liệu Memory dài hạn (`user_memories`). *Ghi chú: Nếu tạm thời không có DB, hệ thống tự động fallback an toàn sang in-memory.*
  - **LLM Backend:** LiteLLM self-hosted gateway nội bộ (`http://192.168.1.196:18083/v1`) hoặc tài khoản OpenAI API Key (`sk-...`).

---

## ⚙️ 2. Environment Variables (Biến môi trường)

Hệ thống sử dụng file `.env` tại thư mục gốc `agent-harness/dong/` để cấu hình:

```bash
cd agent-harness/dong
cp .env.example .env
```

### Các nhóm biến quan trọng:

| Nhóm | Tên biến | Mặc định / Ví dụ | Mô tả |
|------|----------|-------------------|-------|
| **Memory & Context (v9)** | `MEMORY_ENABLED` | `true` | Cờ tổng bật/tắt toàn bộ hệ thống memory |
| | `MEMORY_SHORT_TERM_ENABLED` | `true` | Bật/tắt quản lý phiên hội thoại & checkpointer |
| | `MEMORY_LONG_TERM_ENABLED` | `true` | Bật/tắt lưu và truy xuất facts người dùng vào PostgreSQL |
| | `MEMORY_TTL_SECONDS` | `300` | Thời gian sống (TTL) của response cache (5 phút) |
| | `MEMORY_MAX_MESSAGES` | `20` | Số lượng tin nhắn tối đa giữ trong sliding window |
| | `MEMORY_COMPACT_THRESHOLD` | `0.40` | Ngưỡng kích hoạt compaction chủ động (nguyên tắc 40-60%) |
| **PostgreSQL Database** | `DB_HOST` | `192.168.1.xxx` | Địa chỉ máy chủ PostgreSQL |
| | `DB_PORT` | `5432` | Cổng kết nối PostgreSQL |
| | `DB_USER` | `postgres` | User kết nối database |
| | `DB_PASSWORD` | *(Mật khẩu)* | Mật khẩu database |
| | `DB_NAME_ITS` | `its` | Database phương tiện VMS & lưu trữ `user_memories` |
| **LLM Backend** | `LLM_BACKEND` | `self_hosted` (hoặc `openai`) | Lựa chọn backend LLM chính |
| | `MODEL_BASE_URL` | `http://192.168.1.196:18083/v1` | Endpoint gateway nội bộ |
| | `MODEL_NAME` | `qwen3-4b` | Tên mô hình chạy trên gateway |
| | `OPENAI_API_KEYS` | `sk-...` | Danh sách API Key OpenAI nếu dùng cloud |
| **Cổng mạng (Ports)** | `BACKEND_PORT` | `8000` | Cổng Backend API FastAPI |
| | `FRONTEND_PORT` | `8080` (hoặc `3001`) | Cổng Web UI qua Nginx |

---

## 💻 3. Local Development (Chạy trực tiếp trên máy không dùng Docker)

### 3.1. Cài đặt môi trường Python

```bash
cd agent-harness/dong

# 1. Khởi tạo virtual environment (khuyên dùng Python 3.11 hoặc 3.12)
python -m venv .venv

# 2. Kích hoạt môi trường:
# - Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1

# - Trên Windows (CMD):
.venv\Scripts\activate.bat

# - Trên Linux / macOS:
source .venv/bin/activate

# 3. Nâng cấp pip và cài đặt dependencies
python -m pip install -U pip
pip install -r requirements.txt
```

### 3.2. Cấu hình biến môi trường

```bash
# Sao chép file cấu hình mẫu
cp .env.example .env

# Chỉnh sửa file .env phù hợp với môi trường của bạn (nếu có PostgreSQL hoặc OpenAI key)
# Ghi chú: Nếu tạm thời không kết nối PostgreSQL, hệ thống tự động fallback sang in-memory an toàn 100%.
```

### 3.3. Khởi động ứng dụng

```bash
# Khởi động Backend API FastAPI với reload tự động
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Sau khi backend khởi động thành công:
- **Kiểm tra trạng thái Health Check**:
  ```bash
  curl http://localhost:8000/api/health
  ```
- **Truy cập giao diện Web Chat UI**:
  * Trực tiếp qua FastAPI static serving: `http://localhost:8000/`
  * Hoặc mở trực tiếp file `frontend/index.html` trên trình duyệt.

---

## 🐳 4. Docker Deployment (Chạy bằng Docker & Docker Compose)

Hệ thống hỗ trợ đóng gói đầy đủ cụm container gồm AI Backend (FastAPI) và Frontend Web UI (Nginx).

### 4.1. Khởi động cụm dịch vụ

```bash
cd agent-harness/dong

# Build images và khởi động containers chạy nền (-d)
docker compose up -d --build
```

### 4.2. Kiểm tra trạng thái và log hoạt động

```bash
# Kiểm tra danh sách container đang chạy
docker compose ps

# Xem log thời gian thực của backend
docker compose logs -f ai_backend

# Xem log của frontend nginx
docker compose logs -f frontend
```

### 4.3. Truy cập ứng dụng qua Docker

- **Web Chat UI**: `http://localhost:8080` (hoặc `http://localhost:3001` tùy cổng cấu hình trong compose).
- **Backend API**: `http://localhost:8000`.

### 4.4. Dừng và dọn dẹp cụm container

```bash
# Dừng cụm container
docker compose down

# Dừng và xóa cả volumes (nếu muốn làm mới hoàn toàn)
docker compose down -v
```

---

## 🧪 5. Chạy kiểm thử (Testing Suite)

### 5.1. Chạy các bài test cốt lõi về Memory & Context Engineering (Spec quy định)

```bash
cd agent-harness/dong

# Chạy 3 bài test cốt lõi theo implementation-plan.md:
PYTHONPATH=. pytest tests/test_product_memory_context.py tests/test_product_memory_cache.py tests/test_product_memory_postgres.py -v
```

### 5.2. Chạy toàn bộ 14 test files của hệ sinh thái Memory & Context Engineering v9

```bash
# Chạy đầy đủ 159 tests bao quát toàn bộ 5 phase Memory & Context Engineering:
PYTHONPATH=. pytest \
  tests/test_product_memory_context.py \
  tests/test_product_memory_cache.py \
  tests/test_product_memory_extract.py \
  tests/test_product_memory_postgres.py \
  tests/test_product_memory_api.py \
  tests/test_product_memory_shortterm.py \
  tests/test_product_memory_ttl_cache.py \
  tests/test_product_router_ttl_cache.py \
  tests/test_product_graph_memory.py \
  tests/test_frontend_memory_connect.py \
  tests/test_product_graceful_degradation.py \
  tests/test_product_user_isolation.py \
  tests/test_product_compaction_and_tool_compression.py \
  tests/test_product_ttl_cache_expiration.py -v
```

### 5.3. Chạy kiểm thử theo từng chuyên đề nghiệm thu

| Chuyên đề kiểm thử | Lệnh thực thi | Mục tiêu kiểm thử |
|--------------------|---------------|-------------------|
| **Context Compaction 40% & Tool Compression** | `pytest tests/test_product_compaction_and_tool_compression.py -v` | Kiểm tra ngưỡng nén chủ động 40% (AC-6) và nén bảng SQL > 300 tokens (AC-7) |
| **TTL Cache Expiry & Speed** | `pytest tests/test_product_ttl_cache_expiration.py -v` | Kiểm tra latency < 5ms và tự hủy entry sau 300s (AC-4) |
| **User Isolation** | `pytest tests/test_product_user_isolation.py -v` | Kiểm tra cô lập dữ liệu tuyệt đối giữa các user_id (AC-2) |
| **Graceful Degradation** | `pytest tests/test_product_graceful_degradation.py -v` | Kiểm tra tự phục hồi và in-memory fallback khi DB offline (AC-3) |
| **PostgreSQL Persistence** | `pytest tests/test_product_memory_postgres.py -v` | Kiểm tra lưu bền vững bảng `user_memories` (AC-1) |
| **Frontend Memory Connect** | `pytest tests/test_frontend_memory_connect.py -v` | Kiểm tra nút Reset Memory và render huy hiệu Cache Hit |
| **Phân hệ Text-to-SQL** | `pytest tests/test_product_sql_agent.py -v` | Kiểm tra sinh SQL, validation và repair loop |
| **Toàn bộ Test Suite** | `pytest -q` | Kiểm tra hồi quy toàn diện hệ thống multi-agent (> 600 tests) |

---

## 🌐 6. Hướng dẫn expose ứng dụng ra Internet bằng ngrok (ngrok Demo Setup)

Nhằm phục vụ việc demo trực tiếp cho khách hàng/đối tác qua internet hoặc kiểm thử trên các thiết bị di động từ xa mà không cần cấu hình mạng phức tạp, hệ thống hỗ trợ mở đường hầm an toàn (secure tunnel) qua **ngrok**.

### 6.1. Cài đặt ngrok

- **Windows** (Khuyến nghị qua winget):
  ```powershell
  winget install ngrok/ngrok
  ```
  *Hoặc tải bản đóng gói standalone `.zip` từ [ngrok.com/download](https://ngrok.com/download), giải nén file `ngrok.exe` vào thư mục của dự án hoặc đưa vào `PATH` hệ thống.*

- **macOS** (qua Homebrew):
  ```bash
  brew install ngrok/ngrok/ngrok
  ```

- **Linux (Ubuntu / Debian)**:
  ```bash
  curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
  sudo apt update && sudo apt install ngrok
  ```

### 6.2. Thiết lập Authtoken
Đăng ký tài khoản miễn phí tại [ngrok.com](https://ngrok.com) và cấu hình token cho máy của bạn:
```bash
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

### 6.3. Khởi động ứng dụng trước khi mở tunnel
Trước khi khởi chạy ngrok, đảm bảo hệ thống backend đang phục vụ trên máy:
- **Nếu chạy Local (FastAPI)**:
  ```bash
  uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- **Nếu chạy qua Docker Compose**:
  ```bash
  docker compose up -d
  ```

### 6.4. Mở Tunnel ra Internet

#### Cách 1: Sử dụng Script tự động có sẵn
- **Trên Windows**:
  ```cmd
  scripts\run_ngrok_demo.bat 8000
  ```
  *(Nếu chạy Docker Compose frontend cổng 8080: `scripts\run_ngrok_demo.bat 8080`)*

- **Trên Linux / macOS / Git Bash**:
  ```bash
  chmod +x scripts/run_ngrok_demo.sh
  ./scripts/run_ngrok_demo.sh 8000
  ```

#### Cách 2: Lệnh trực tiếp qua ngrok CLI
```bash
# Expose cổng 8000 (FastAPI Backend + Web Chat phục vụ tại /)
ngrok http 8000 --host-header="localhost:8000"

# Hoặc expose cổng 8080 (Docker Nginx Frontend)
ngrok http 8080 --host-header="localhost:8080"
```

### 6.5. Kiểm tra và tương tác qua Public URL
1. Ngrok sẽ cấp một địa chỉ Forwarding dạng: `https://<unique-subdomain>.ngrok-free.app`.
2. Mở trình duyệt trên máy tính khác hoặc điện thoại di động, dán đường dẫn public trên.
3. Nếu gặp trang cảnh báo của ngrok free tier (*"You are about to visit..."*), nhấn **Visit Site** để tiếp tục.
4. Giao diện Web Chat VMS sẽ tải trực tiếp. Người dùng có thể trò chuyện, gửi câu hỏi, kiểm tra Memory facts và biểu đồ thống kê qua internet theo thời gian thực.
5. Truy cập Web Dashboard giám sát của ngrok tại: `http://127.0.0.1:4040` để kiểm tra chi tiết các HTTP request, Server-Sent Events (SSE) stream và độ trễ phản hồi.

---

## 🎬 7. Kịch bản Demo kiểm chứng độ bền vững của Memory & Context Engineering (v9)

Kịch bản demo được thiết kế chuẩn mực theo **Mục 3 của `specs/test-plan.md`**, nhằm chứng minh trực quan toàn bộ sức mạnh và độ tin cậy của hệ thống Multi-Agent VMS KCN Hưng Phú trước khách hàng và hội đồng kỹ thuật.

### 7.1. Bảng 7 kịch bản kiểm thử trên Web UI (Live Demo Checklist)

| Bước | Thao tác trên giao diện Web (`http://localhost:8000` hoặc Link ngrok) | Kỳ vọng quan sát được | Cơ chế kỹ thuật chứng minh |
|:---:|----------------------------------------------------------------------|------------------------|---------------------------|
| **1** | Gửi: *"Chào bạn, tôi tên là Tuấn, tôi phụ trách giám sát an ninh ca đêm"* | Trợ lý phản hồi chào lịch sự, ghi nhận danh tính. Badge Memory cập nhật facts đã nhớ. | **Fact Extraction & PostgreSQL Persistence** (`user_memories`) |
| **2** | Gửi câu hỏi tiếp theo trong phiên: *"Khu vực tôi phụ trách là gì?"* | Trợ lý nhớ và trả lời: *"Bạn phụ trách giám sát an ninh ca đêm"*. | **Short-Term & Long-Term Memory Recall** |
| **3** | Mở tab ẩn danh mới (hoặc F5 / New Session) cùng `user_id`: *"Tôi là ai?"* | Trợ lý vẫn nhận ra: *"Bạn là Tuấn, phụ trách an ninh ca đêm"*. | **PostgreSQL Durability** (Dữ liệu tồn tại vĩnh viễn, không mất khi restart/tạo phiên mới) |
| **4** | Trò chuyện liên tục qua hơn 10 câu hỏi nghiệp vụ VMS | Trợ lý phản hồi nhanh, không bị lag/tràn token; các quy tắc an toàn VMS luôn được tuân thủ nghiêm ngặt. | **Sliding Window (max=20)** & **Instruction Re-injection** (chống instruction drift) |
| **5** | Gửi câu hỏi thống kê: *"Hôm nay có bao nhiêu lượt xe vào KCN?"* | Trợ lý trả về số liệu chính xác kèm biểu đồ. Nếu bảng dữ liệu SQL dài, kết quả được nén súc tích trước khi nạp vào LLM. | **Tool Output Compression** (Nén kết quả SQL dài > 300 tokens) |
| **6** | Gửi lại ngay lập tức câu hỏi y hệt: *"Hôm nay có bao nhiêu lượt xe vào KCN?"* | Trợ lý trả về kết quả ngay lập tức (< 50ms trên UI, < 5ms tại backend) kèm huy hiệu **Cache Hit**. | **TTL Response Cache (300s)** |
| **7** | Tạm dừng PostgreSQL hoặc cấu hình DB lỗi rồi gửi tin nhắn chat | Ứng dụng vẫn hoạt động bình thường, ghi nhận log warning nhẹ và tự động chuyển sang in-memory fallback, tuyệt đối không báo lỗi 500. | **Graceful Degradation** (Tự phục hồi in-memory khi DB offline) |

### 7.2. Kiểm chứng tự động bằng Script

Hệ thống cung cấp sẵn công cụ kiểm chứng tự động toàn bộ 7 bước kịch bản demo trên:

```bash
cd agent-harness/dong

# Chạy kiểm chứng tự động 7 kịch bản:
python scripts/verify_memory_demo.py
```

Kết quả kỳ vọng hiển thị trên console:
```text
=================================================================
  KIỂM CHỨNG TỰ ĐỘNG ĐỘ BỀN VỮNG CỦA MEMORY & CONTEXT ENGINEERING (v9)
  Hệ thống Multi-Agent VMS KCN Hưng Phú
=================================================================
[1/7] Ghi nhận danh tính (Fact Extraction & Storage) ... [PASS]
[2/7] Truy vấn trong cùng phiên (Memory Recall) ... [PASS]
[3/7] Phiên mới / Thiết bị mới (Long-Term Durability) ... [PASS]
[4/7] Hội thoại dài > 10 lượt (Sliding Window & Instruction Re-injection) ... [PASS]
[5/7] Truy vấn dữ liệu lớn (Tool Output Compression) ... [PASS]
[6/7] Câu hỏi trùng lặp (TTL Response Cache) ... [PASS]
[7/7] Sự cố database (Graceful Degradation Fallback) ... [PASS]
=================================================================
🎉 KẾT QUẢ: 7/7 KỊCH BẢN DEMO PASS HOÀN HẢO 100%!
=================================================================
```

