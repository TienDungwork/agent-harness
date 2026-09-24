# agent dong — VMS Analytics Agent (v8)

Trợ lý tiếng Việt thông minh cho hệ thống VMS KCN Hưng Phú: truy vấn số liệu read-only (Text-to-SQL), Master Data Registry 10 camera AIOC, hướng dẫn vận hành VMS/AIOC, trực quan hóa biểu đồ (Chart.js & PNG), phản hồi dạng stream mượt mà qua SSE, hệ thống đánh giá Human Feedback (Like/Dislike + Lý do + Ảnh đính kèm) và đồ thị giám sát thực thi thời gian thực (Live Graph).

---

## 📑 Specs & Tài liệu tham chiếu

| File | Nội dung |
|------|----------|
| [specs/product-spec.md](specs/product-spec.md) | Mục tiêu v8, phân tích lỗi 6 camera, thiết kế Human Feedback & Streaming, tiêu chí nghiệm thu |
| [specs/implementation-plan.md](specs/implementation-plan.md) | Kế hoạch triển khai tuần tự Phase 1–7 |
| [specs/test-plan.md](specs/test-plan.md) | Kế hoạch kiểm thử unit test và kịch bản manual smoke checklist |
| [specs/change-log.md](specs/change-log.md) | Nhật ký thay đổi và đánh giá qua từng phase |
| [AGENTS.md](AGENTS.md) | Quy chuẩn và hướng dẫn dành cho AI agent |

---

## 🏗️ Kiến trúc luồng thực thi (v8)

```text
câu hỏi → guardrail → classify
              ├─ chào / clarify → respond_inline (1 hop) → stream delta → xong
              ├─ hướng dẫn → retrieve_docs → answer_from_docs → stream delta → xong
              ├─ camera registry (10 cams) → fast master lookup → stream delta → xong
              └─ số liệu → retrieve_schema (≤4 bảng)
                           → generate_sql (cap tokens + time_range + chart hint)
                           → validate_sql ↔ repair_sql (≤2 lần)
                           → execute_sql (Postgres read-only)
                           → render_chart / respond → stream delta → xong

Sau khi hoàn tất:
Người dùng đánh giá: 👍 (Like) hoặc 👎 (Dislike + Lý do + Ảnh) → Lưu vào SQLite data/feedback.db (bảng feedback, kèm full agent trace) và đồng bộ data/feedback.json
```

---

## 📋 1. Prerequisites (Yêu cầu hệ thống)

Trước khi cài đặt và chạy ứng dụng, hãy đảm bảo môi trường máy của bạn đáp ứng các yêu cầu sau:

- **Hệ điều hành:** Linux (Ubuntu 20.04/22.04 LTS khuyên dùng), macOS, hoặc Windows (thông qua WSL2).
- **Python:** Phiên bản `>= 3.10` (khuyên dùng Python 3.11 hoặc 3.12).
- **Công cụ dòng lệnh:**
  - `git` (quản lý mã nguồn)
  - `curl` (kiểm tra API endpoints)
  - `jq` (đọc định dạng JSON trên terminal, tùy chọn)
- **Docker & Docker Compose (cho triển khai container):**
  - Docker Engine `>= 20.10`
  - Docker Compose v2 (`docker compose version`)
- **Trình duyệt Web:** Chrome, Microsoft Edge, Firefox, Safari (phiên bản hiện đại có hỗ trợ Server-Sent Events / SSE).
- **Dịch vụ phụ trợ (Tùy chọn theo cấu hình):**
  - **LLM Backend:** LiteLLM self-hosted gateway nội bộ (`http://192.168.1.196:18083/v1`) hoặc tài khoản OpenAI API Key (`sk-...`).
  - **PostgreSQL Database:** Quyền đọc (Read-Only) vào các cơ sở dữ liệu VMS (`its`, `virtual_fence`, `smart_face`, `firesmoke`, `anomaly`). *Ghi chú: Nếu không có kết nối DB, agent vẫn hoạt động ở chế độ giải đáp nghiệp vụ (docs YAML) và tra cứu danh mục 10 camera AIOC.*

---

## ⚙️ 2. Environment Variables (Biến môi trường)

Hệ thống sử dụng file `.env` tại thư mục gốc `agent-harness/dong/` để cấu hình. Tạo file `.env` từ file mẫu:

```bash
cd agent-harness/dong
cp .env.example .env
```

### Các nhóm biến quan trọng:

| Nhóm | Tên biến | Mặc định / Ví dụ | Mô tả |
|------|----------|-------------------|-------|
| **LLM Backend** | `LLM_BACKEND` | `self_hosted` (hoặc `openai`) | Lựa chọn backend LLM chính |
| | `MODEL_BASE_URL` | `http://192.168.1.196:18083/v1` | Endpoint gateway nội bộ (cho `self_hosted`) |
| | `MODEL_NAME` | `qwen3-4b` | Tên mô hình chạy trên gateway self-hosted |
| | `MODEL_API_KEY` | *(Tùy chọn gateway)* | API Key cho gateway nội bộ (nếu có yêu cầu) |
| | `LLM_MODEL` | `gpt-4o-mini` | Tên model khi chạy chế độ `LLM_BACKEND=openai` |
| | `OPENAI_API_KEYS` | `sk-...` | Danh sách API Key OpenAI (hỗ trợ xoay vòng bằng dấu phẩy) |
| **PostgreSQL (Read-Only)** | `DB_HOST` | `192.168.1.xxx` | Địa chỉ máy chủ PostgreSQL chứa dữ liệu VMS |
| | `DB_PORT` | `5432` | Cổng kết nối PostgreSQL |
| | `DB_USER` | `agent_readonly` | User truy vấn (chỉ cần quyền SELECT) |
| | `DB_PASSWORD` | *(Mật khẩu)* | Mật khẩu database |
| | `DB_NAME_ITS` | `its` | Database phương tiện & biển số giao thông |
| | `DB_NAME_FENCE` | `virtual_fence` | Database hàng rào ảo & vùng cấm |
| | `DB_NAME_FACE` | `smart_face` | Database nhận diện khuôn mặt |
| | `DB_NAME_FIRE` | `firesmoke` | Database cảnh báo cháy khói |
| | `DB_NAME_ANOMALY`| `anomaly` | Database sự kiện bất thường |
| **Cổng mạng (Ports)** | `BACKEND_PORT` | `8000` | Cổng lắng nghe của Backend API FastAPI |
| | `FRONTEND_PORT` | `8080` (hoặc `3001`) | Cổng truy cập Web UI qua Nginx |
| **Cache & Giám sát** | `CACHE_ENABLED` | `true` | Bật/tắt Response Cache |
| | `MEMORY_TTL_SECONDS` | `300` | Thời gian sống (TTL) của response cache (5 phút) |
| | `MONITORING_ENABLED` | `false` (hoặc `true`) | Bật/tắt tracing Langfuse |
| | `LANGFUSE_HOST` | `http://localhost:3000` | Địa chỉ máy chủ Langfuse |

---

## 💻 3. Local Development (Chạy trực tiếp trên máy không dùng Docker)

### 3.1. Cài đặt môi trường (Install commands)

```bash
# 1. Di chuyển vào thư mục dự án
cd agent-harness/dong

# 2. Tạo môi trường ảo Python (Virtual Environment)
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài đặt các gói phụ thuộc
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2. Chạy Backend (FastAPI + Uvicorn)

Khởi chạy máy chủ Backend API Gateway:

```bash
# Kích hoạt virtualenv (nếu chưa kích hoạt)
source .venv/bin/activate

# Chạy server với hot-reload
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

*Đặc điểm tiện lợi:* Khi chạy local, Backend FastAPI tự động mount thư mục `frontend/` tại `/static` và phục vụ trực tiếp `index.html` tại địa chỉ gốc `http://localhost:8000/`.

### 3.3. Chạy Frontend

Bạn có 2 lựa chọn để truy cập giao diện:

- **Cách 1 (Khuyên dùng — Không cần cài thêm gì):** Mở trình duyệt và truy cập trực tiếp:
  ```
  http://localhost:8000
  ```
  Backend FastAPI đã tích hợp sẵn và phục vụ frontend tĩnh cùng API trên cùng một origin.
- **Cách 2 (Chạy server tĩnh riêng biệt cho Frontend):** Nếu bạn muốn debug riêng phần giao diện tĩnh:
  ```bash
  # Mở terminal mới và chạy:
  python3 -m http.server 8080 -d frontend
  # Hoặc dùng npx:
  # npx -y serve frontend -p 8080
  ```
  *Lưu ý khi dùng Cách 2:* Do frontend chạy ở cổng 8080 khác với backend cổng 8000, sau khi mở `http://localhost:8080`, hãy click vào icon **Cài đặt (⚙️)** ở góc trên bên phải màn hình và nhập `http://localhost:8000` vào ô **API Base URL**, sau đó bấm **"Lưu cấu hình"**.

---

## Demo with docker

Hệ thống được đóng gói hoàn chỉnh bằng Docker Compose gồm 2 container phối hợp:
- **`kcn_hungphu_frontend`** (Nginx Reverse Proxy): Chạy ở cổng **`3001`** (`FRONTEND_PORT=3001` trong `.env` map tới cổng 80 container).
- **`kcn_hungphu_backend`** (FastAPI API Gateway): Chạy ở cổng **`8000`** (`BACKEND_PORT=8000` trong `.env` map tới cổng 8000 container).

### 1. Các cổng thực tế được sử dụng (Actual Ports)

| Thành phần | Cổng Host (Actual Port) | Địa chỉ truy cập | Vai trò |
|------------|-------------------------|-------------------|---------|
| **Frontend Web UI** | `3001` | [http://localhost:3001](http://localhost:3001) | Giao diện Chatbot, biểu đồ, Live Graph & Feedback |
| **Backend API Gateway** | `8000` | [http://localhost:8000](http://localhost:8000) | REST API, SSE Stream, LangGraph orchestrator |
| **Swagger API Docs** | `8000` | [http://localhost:8000/docs](http://localhost:8000/docs) | Tài liệu kiểm thử API tương tác |
| **API Health Check** | `8000` | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Kiểm tra trạng thái backend & model LLM |
| **Human Feedback API** | `8000` | [http://localhost:8000/api/feedback](http://localhost:8000/api/feedback) | Xem danh sách đánh giá đã ghi nhận |

*Lưu ý:* Khi truy cập qua giao diện Docker ở cổng `3001`, Nginx đã được cấu hình tự động chuyển tiếp (reverse proxy) các yêu cầu `/api/`, `/ask`, `/health` sang backend `ai_backend:8000`. Người dùng không cần cấu hình thêm API Base URL.

### 2. Các bước khởi động Demo

```bash
cd agent-harness/dong

# 1. Tạo file .env từ file mẫu (đã cấu hình sẵn FRONTEND_PORT=3001, BACKEND_PORT=8000)
cp -n .env.example .env

# 2. Khởi động toàn bộ container chạy ngầm
docker compose up -d

# (Tùy chọn) Nếu có thay đổi mã nguồn hoặc cần rebuild image:
docker compose up --build -d

# 3. Kiểm tra trạng thái các container (đảm bảo ai_backend báo healthy và cổng 3001, 8000 đã UP)
docker compose ps
```

### 3. Kịch bản trải nghiệm Demo trực tiếp trên Web UI

Mở trình duyệt và truy cập: **[http://localhost:3001](http://localhost:3001)**

- **Kịch bản 1 — Tra cứu Master Registry 10 Camera AIOC:**
  - Nhập câu hỏi: *"Hiện có bao nhiêu camera đang hoạt động?"*
  - **Kết quả:** Trợ lý AI báo chính xác **10 camera đang hoạt động (ONLINE)**, phân loại 3 phân hệ (6 phương tiện, 2 vùng cấm, 2 cháy khói).
  - Nhập câu hỏi: *"Kể tên các camera trong hệ thống"*
  - **Kết quả:** Liệt kê đầy đủ 10 camera kèm các mã đặc thù (`CVN_CONG_BOH`, `CVNTT`, `CVN_KHO_TANG2_BOH`, `CVN_P_CAP_PHAT_DONG_PHUC`, `congchinh1`, `congchinh2`, `congvanle1-4`).

- **Kịch bản 2 — Trải nghiệm SSE Chunk Streaming:**
  - Gửi bất kỳ câu hỏi nào (ví dụ: *"Hướng dẫn xử lý khi camera mất kết nối"* hoặc *"Chào bạn"*).
  - **Kết quả:** Câu trả lời xuất hiện dần dần từng chữ (hiệu ứng typewriter) mượt mà, không giật lag.

- **Kịch bản 3 — Đánh giá Hài lòng (Like 👍):**
  - Click icon 👍 bên dưới câu trả lời.
  - **Kết quả:** Nút đổi màu active, toast thông báo *"Cảm ơn bạn đã gửi phản hồi!"* hiển thị ở góc màn hình.

- **Kịch bản 4 — Góp ý Chưa đúng (Dislike 👎) kèm Lý do & Ảnh chụp màn hình:**
  - Click icon 👎 $\rightarrow$ Hộp thoại modal xuất hiện.
  - Nhập lý do (ví dụ: *"Cần bổ sung thêm thông tin vị trí lắp đặt"*).
  - Chọn 1 file ảnh (hoặc bấm `Ctrl + V` dán trực tiếp ảnh từ clipboard) $\rightarrow$ Xem trước thumbnail ảnh.
  - Bấm **"Xác nhận gửi phản hồi"** $\rightarrow$ Modal đóng, toast thành công xuất hiện.

### 4. Lệnh kiểm tra và giám sát dữ liệu Demo

```bash
# Xem log thời gian thực của backend
docker compose logs -f ai_backend

# Kiểm tra dữ liệu feedback trong SQLite (data/feedback.db)
sqlite3 data/feedback.db "SELECT id, rating, question, timestamp FROM feedback ORDER BY timestamp DESC LIMIT 5;"

# Hoặc kiểm tra file JSON đồng bộ (kèm đầy đủ agent trace, SQL, latencies)
cat data/feedback.json | jq .

# Kiểm tra ảnh đính kèm vừa tải lên trong container
ls -la data/feedback/attachments/

# Kiểm tra nhanh kết nối LLM
curl -sf http://localhost:8000/api/llm/ping | jq .
```

### 5. Dừng hệ thống Demo

```bash
# Dừng và giải phóng container
docker compose down
```

---

## 🌐 5. Local URLs (Địa chỉ truy cập cục bộ)

| Dịch vụ | Địa chỉ truy cập | Ghi chú |
|---------|-------------------|---------|
| **Web UI (Docker Compose)** | [http://localhost:3001](http://localhost:3001) | Giao diện qua Nginx reverse proxy (cổng chính thức) |
| **Web UI (Local Dev trực tiếp)** | [http://localhost:8000](http://localhost:8000) | Giao diện phục vụ trực tiếp bởi FastAPI |
| **API Documentation (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Tài liệu tra cứu & test API tương tác |
| **API Documentation (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Tài liệu API dạng ReDoc |
| **Health Check API** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Kiểm tra trạng thái backend & model |
| **LLM Ping API** | [http://localhost:8000/api/llm/ping](http://localhost:8000/api/llm/ping) | Kiểm tra kết nối tới LLM gateway |
| **Human Feedback API** | [http://localhost:8000/api/feedback](http://localhost:8000/api/feedback) | Xem danh sách đánh giá đã ghi nhận |
| **Langfuse Dashboard** | [http://localhost:3000](http://localhost:3000) hoặc [http://192.168.1.196:13000](http://192.168.1.196:13000) | Giao diện giám sát trace các node LLM |

---

## 🔍 6. Kiểm tra & Nghiệm thu hệ thống

### 6.1. Kiểm tra nhanh qua dòng lệnh

```bash
# 1. Kiểm tra trạng thái Backend
curl -sf http://localhost:8000/api/health | jq .

# 2. Kiểm tra kết nối tới LLM
curl -sf http://localhost:8000/api/llm/ping | jq .

# 3. Xem danh sách phản hồi người dùng
curl -sf http://localhost:8000/api/feedback | jq .
```

### 6.2. Chạy bộ kiểm thử tự động (Unit Tests)

```bash
cd agent-harness/dong

# Kích hoạt virtualenv (nếu chạy local)
source .venv/bin/activate

# Chạy toàn bộ test suite (629+ tests)
PYTHONPATH=. pytest -q

# Chỉ chạy các kiểm thử tính năng v8 (Camera Registry + Feedback + SSE Streaming)
PYTHONPATH=. pytest tests/ -k "camera or feedback"
```

### 6.3. Chạy kịch bản khói (Smoke Test)

```bash
./scripts/smoke-production.sh
```

---

## 🛠️ 7. Troubleshooting Notes (Xử lý sự cố thường gặp)

### 1. Lỗi kết nối LLM (503 Service Unavailable / Timeout / LLM Ping FAIL)
- **Triệu chứng:** Gửi câu hỏi nhận thông báo lỗi 503, hoặc lệnh `curl /api/llm/ping` trả về thất bại.
- **Nguyên nhân:** Địa chỉ LLM gateway nội bộ (`http://192.168.1.196:18083/v1`) không truy cập được từ máy của bạn (chưa kết nối VPN hoặc khác dải mạng nội bộ).
- **Cách khắc phục:**
  - Chuyển sang sử dụng OpenAI: Trong file `.env`, đặt `LLM_BACKEND=openai`, điền API key vào `OPENAI_API_KEYS=sk-...`, và đặt `LLM_MODEL=gpt-4o-mini`.
  - Khởi động lại backend hoặc container.
  - Khi chạy unit test, hệ thống tự động sử dụng mock/offline tools nên không phụ thuộc vào kết nối mạng này.

### 2. Lỗi kết nối PostgreSQL (Database Connection Error)
- **Triệu chứng:** Khi hỏi về thống kê số liệu giao thông, agent thông báo không thể truy vấn cơ sở dữ liệu.
- **Nguyên nhân:** Máy chủ PostgreSQL chứa các database VMS đang offline hoặc thông tin `DB_HOST`, `DB_USER`, `DB_PASSWORD` trong `.env` chưa chính xác.
- **Cơ chế tự bảo vệ:** Hệ thống được thiết kế với cơ chế phòng vệ suy giảm tính năng (Graceful Degradation). Khi DB offline:
  - Các câu hỏi chào hỏi (`chat`), hướng dẫn vận hành VMS (`docs`), và tra cứu 10 camera AIOC (`camera_registry`) **vẫn hoạt động hoàn hảo**.
  - Agent sẽ phản hồi giải thích rõ ràng và lịch sự thay vì làm sập ứng dụng.

### 3. Lỗi CORS hoặc không gửi được tin nhắn khi chạy Frontend độc lập
- **Triệu chứng:** Mở giao diện ở cổng 8080, nhập câu hỏi nhưng không nhận được phản hồi, bảng điều khiển (Console F12) báo lỗi CORS hoặc `Failed to fetch`.
- **Cách khắc phục:**
  - Bấm vào biểu tượng **Cài đặt (⚙️)** ở thanh bên phải của Web UI.
  - Tại ô **API Base URL**, nhập `http://localhost:8000`.
  - Bấm **"Lưu cấu hình"** và thử lại.
  - Hoặc đơn giản hơn, hãy truy cập Web UI trực tiếp tại `http://localhost:8000/`.

### 4. Xung đột cổng mạng (`Port already in use` 8000 hoặc 8080)
- **Triệu chứng:** Uvicorn hoặc Docker báo lỗi `address already in use`.
- **Cách khắc phục:**
  - Tìm và tắt tiến trình đang chiếm cổng:
    ```bash
    fuser -k 8000/tcp
    fuser -k 8080/tcp
    ```
  - Hoặc đổi cổng khác trong file `.env`: `BACKEND_PORT=8001` và `FRONTEND_PORT=3002`.

### 5. Lỗi quyền ghi dữ liệu Feedback (`PermissionError: [Errno 13] Permission denied: 'data/feedback.json'`)
- **Triệu chứng:** Bấm Like/Dislike trên UI nhận thông báo *"Gửi phản hồi thất bại"*, log container báo lỗi ghi file.
- **Nguyên nhân:** Container Docker chạy dưới user khác với user sở hữu thư mục trên máy host.
- **Cách khắc phục:**
  - Cấp quyền ghi đầy đủ cho thư mục `data/` trên máy host:
    ```bash
    chmod -R 777 data/
    ```

### 6. Lỗi xung đột thư viện `openai` và `httpx`
- **Triệu chứng:** Gặp lỗi `Decompressor.decompress missing output_buffer_limit`.
- **Cách khắc phục:**
  - Không nâng cấp `openai` lên các bản không tương thích. Đảm bảo cài đúng phiên bản đã được ghim trong `requirements.txt`:
    ```bash
    pip install openai==2.45.0
    ```
