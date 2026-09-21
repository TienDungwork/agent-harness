# agent dong (v4)

Trợ lý VMS: số liệu chỉ đọc + cách dùng + live graph trên UI. Spec-driven.

**Tiến độ:** Phase 9 hoàn tất (Local run instructions: run env, ping/pytest/eval, phụ thuộc LAN). Chuẩn bị: Phase 10 (Demo setup).

## Specs

- [specs/product-spec.md](specs/product-spec.md)
- [specs/implementation-plan.md](specs/implementation-plan.md) — Phase 1→10
- [specs/test-plan.md](specs/test-plan.md)
- [specs/change-log.md](specs/change-log.md)
- [AGENTS.md](AGENTS.md)

## Cấu trúc mục tiêu (sau các phase)

```text
src/                 # entry duy nhất
  main.py            # FastAPI — chạy: uvicorn src.main:app
frontend/            # chat | graph ~50/50, SSE live graph
tests/               # < 10 file (hiện 7 file)
eval/
  datasets/.../v2.yaml
  results/golden-30.md   # kết quả eval 30 câu
backend/             # đã xóa hoàn toàn
```

LLM mặc định: Ollama `http://192.168.1.196:11434/v1` — model `qwen3-16k-nothink:latest` (xem `.env.example`).

## Chạy Docker (Production / Demo — khuyên dùng)

Không cần `.venv`. Chỉ cần Docker + Docker Compose.

```bash
cd agent-harness/dong
# .env + langfuse/.env đã có sẵn (user admin@agent-atin.local, keys khớp agent_ATIN)
./scripts/setup-langfuse.sh          # dong + Langfuse
./scripts/setup-langfuse.sh --reset  # init lại Langfuse từ đầu (xóa trace cũ)
```

| URL | Mục đích |
| :--- | :--- |
| http://localhost:8080 | UI chat + live graph (nginx reverse proxy → API) |
| http://localhost:8000/docs | Swagger API (debug) |
| http://localhost:8000/api/health | Health check backend |

**Demo nhanh:** Mở http://localhost:8080 — **không cần** cấu hình API Base URL (nginx proxy `/api/` cùng origin). Gửi câu how-to hoặc số liệu.

**Ollama trên cùng máy deploy:** trong `.env` đặt `LLM_BASE_URL=http://host.docker.internal:11434/v1`.

**Langfuse:** `./scripts/setup-langfuse.sh` — `MONITORING_ENABLED=true` và `LANGFUSE_*` đã điền sẵn trong `.env`.  
Đăng nhập http://localhost:3000 — **`admin@agent-atin.local`** / **`Atin@123#`** → project **agent_ATIN**.

```bash
docker compose logs -f ai_backend frontend                              # log app
docker compose -f langfuse/docker-compose.yml logs -f langfuse-web      # log Langfuse
docker compose down && docker compose -f langfuse/docker-compose.yml down  # dừng cả hai
```

## Hướng dẫn chạy local (Local Run — dev, cần venv)

### 1. Chuẩn bị môi trường & cài đặt

Yêu cầu: Python 3.10+ và virtualenv.

```bash
cd agent-harness/dong

# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
```

### 2. Cấu hình biến môi trường (.env)

Sao chép từ file mẫu:

```bash
cp .env.example .env
```

**Các biến tối thiểu để gửi một câu hỏi:**
- `LLM_BASE_URL`: URL API tương thích OpenAI của Ollama (mặc định: `http://192.168.1.196:11434/v1`).
- `LLM_MODEL`: tên model (mặc định: `qwen3-16k-nothink:latest`).
- `LLM_API_KEY`: API key (mặc định: `ollama`).
- *Lưu ý về DB & ClickHouse:* Các biến kết nối Postgres (`DB_*`) và ClickHouse (`CH_*`) là tuỳ chọn nếu chỉ hỏi tài liệu how-to / hướng dẫn VMS. Khi cần truy vấn số liệu thống kê (đếm xe, sự kiện), cần cung cấp thông tin kết nối chỉ đọc (read-only).

### 3. Khởi chạy hệ thống

Hệ thống gồm 2 tiến trình chạy độc lập:

**Bước 1 — Khởi động Backend API (FastAPI):**
Chạy từ thư mục `agent-harness/dong`:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Bước 2 — Phục vụ Frontend tĩnh (mở terminal mới):**
Chạy từ thư mục `agent-harness/dong`:
```bash
cd frontend && python3 -m http.server 8080
```

### 4. Bảng cổng & địa chỉ truy cập (Ports & URLs)

| Thành phần | Địa chỉ URL | Ghi chú |
| :--- | :--- | :--- |
| **Backend API** | `http://localhost:8000` | Dịch vụ FastAPI |
| **API Docs (Swagger)** | `http://localhost:8000/docs` | OpenAPI documentation & interactive test |
| **Frontend UI** | `http://localhost:8080` | Giao diện Chat & Live Graph 50/50 |

### 5. Cấu hình UI & Xác thực End-to-End

1. Mở trình duyệt tại `http://localhost:8080`.
2. Mở **Cài đặt** (click model pill góc dưới sidebar trái), đặt **API Base URL** = `http://localhost:8000` (mặc định rỗng → request tới `:8080`, không tới API), bấm **Kiểm tra kết nối Backend** rồi **Lưu Cấu Hình**.
3. Mở UI, gửi một câu hỏi tiếng Việt (ví dụ: *"Cách thêm camera vào hệ thống VMS?"*) để xác thực toàn bộ luồng xử lý và live graph end-to-end.

### 6. Kiểm thử & đánh giá (Testing & Evaluation)

Các lệnh kiểm thử và đánh giá tuân thủ [specs/test-plan.md](specs/test-plan.md):

#### 6.1. Ping kiểm tra kết nối LLM (Live, cần .env + LAN tới 196)
Yêu cầu đã cấu hình các biến `LLM_*` trong `.env` (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`) và máy chủ Ollama (LAN 196) đang hoạt động, có thể kết nối được.

- **Kiểm tra qua Python CLI** (chạy từ thư mục `agent-harness/dong`, môi trường ảo đã kích hoạt):
  ```bash
  python -c "from src.llm import ping; print(ping())"
  ```
  *Kỳ vọng:* In ra `OK`.

- **Kiểm tra qua HTTP API** (khi backend uvicorn đang chạy):
  ```bash
  curl -s http://localhost:8000/api/llm/ping
  ```
  *Kỳ vọng:* Trả về JSON trạng thái: `{"status":"OK"}`.

#### 6.2. Chạy kiểm thử pytest (Offline, không cần LLM 196)
Chạy toàn bộ test suite offline (mock LLM client, không cần mạng LAN tới 196), kiểm tra guardrails, intent classification, read-only SQL, docs retrieval, trace/cache và API routes:

```bash
cd agent-harness/dong
pytest -q
find tests -name 'test_*.py' | wc -l   # kỳ vọng: < 10 (hiện tại: 7)
test ! -d backend
```

#### 6.3. Đánh giá tập Golden 30 câu (Live product, cần .env LLM + DB read-only)
Đánh giá chất lượng agent trên tập 30 câu hỏi thực tế (`eval/datasets/agent_stat/v2.yaml`) theo tài liệu [specs/test-plan.md (Mục Golden 30)](specs/test-plan.md#golden-30-phase-8).

```bash
# Chạy đánh giá tiêu chuẩn (rule-based assertions)
python eval/run.py

# (Tuỳ chọn, chậm hơn) Đánh giá kèm thêm cột judge chất lượng câu trả lời bằng LLM (thang 1-5)
python eval/run.py --judge
```

- **Lưu ý quan trọng:**
  - **Không** set biến môi trường `PYTEST_CURRENT_TEST` để script chạy ở chế độ live thật.
  - Cờ `--offline` chỉ dành cho mock nhanh trong CI/pytest, không phản ánh chất lượng sản phẩm.
  - Chạy đầy đủ 30 câu (đặc biệt kèm `--judge`) có thể mất 15–30+ phút tuỳ theo độ trễ của model Ollama.
- **Kết quả:** File báo cáo được cập nhật tại [eval/results/golden-30.md](eval/results/golden-30.md) với header `mode: live` và đầy đủ các cột: `id`, `slice`, `pass/fail`, `latency_ms`, `tool`, `note` (và `judge` nếu bật cờ).

### 7. Phụ thuộc mạng LAN

Hệ thống agent yêu cầu kết nối mạng nội bộ (LAN) tới các dịch vụ hạ tầng sau khi chạy thực tế (live), đồng bộ với [specs/product-spec.md](specs/product-spec.md) và `.env.example`:

#### 7.1. Ollama máy 196 (Bắt buộc cho live LLM)
- **Mặc định (Default):** `http://192.168.1.196:11434/v1`, model `qwen3-16k-nothink:latest`.
- **Yêu cầu mạng LAN:** Máy chạy agent phải thông mạng LAN tới máy 196 (không phải localhost trừ khi Ollama được cài đặt và chạy trực tiếp trên máy local).
- **Cách kiểm tra kết nối (Verify):** Sử dụng các lệnh ping LLM ở Mục 6.1 phía trên:
  ```bash
  python -c "from src.llm import ping; print(ping())"
  # hoặc khi backend đang chạy:
  curl -s http://localhost:8000/api/llm/ping
  ```
- **Hoạt động khi không có máy 196:** Chỉ chạy được `pytest` offline (mock LLM); các câu hỏi tài liệu how-to có thể hoạt động nếu cấu hình endpoint LLM ở nơi khác thông qua ghi đè biến môi trường `LLM_BASE_URL`.

#### 7.2. Postgres read-only (Cần cho câu hỏi số liệu / eval đầy đủ)
- **Quyền hạn truy cập:** Bắt buộc sử dụng role `agent_readonly` hoặc tương đương — chỉ cấp quyền `SELECT`, tuyệt đối không cấp quyền ghi (`INSERT`/`UPDATE`/`DELETE`/`DROP`).
- **Các biến môi trường chính (`.env.example`):**
  - Thông tin kết nối: `DB_HOST`, `DB_PORT` (mặc định: `5432`), `DB_USER`, `DB_PASSWORD`.
  - 5 database nguồn VMS: `DB_NAME_ITS` (`its`), `DB_NAME_FENCE` (`virtual_fence`), `DB_NAME_FACE` (`smart_face`), `DB_NAME_FIRE` (`firesmoke`), `DB_NAME_ANOMALY` (`anomaly`).
- **Mức độ cần thiết:** Tùy chọn nếu chỉ hỏi tài liệu how-to / hướng dẫn VMS; bắt buộc phải có cho các công cụ thống kê số liệu (stat tools) và đánh giá đầy đủ tập golden eval (`eval/run.py`).

#### 7.3. ClickHouse read-only (Tùy chọn, lưu lượng xe...)
- **Các biến môi trường chính (`.env.example`):** `CH_HOST`, `CH_PORT` (mặc định: `8123`), `CH_USER`, `CH_PASSWORD`, `CH_DATABASE`.
- **Quyền hạn truy cập:** Chỉ đọc (read-only queries).
- **Mức độ cần thiết:** Tùy chọn; theo [specs/product-spec.md](specs/product-spec.md), một số công cụ (như đếm lưu lượng xe `count_vehicle_flow`) ưu tiên truy vấn ClickHouse trước Postgres (nếu thiếu hoặc lỗi kết nối sẽ tự động fallback về Postgres).

#### 7.4. Bảng tổng hợp phụ thuộc mạng LAN (Summary Table)

| Dịch vụ (Service) | Host mặc định | Cổng (Port) | Yêu cầu cho (Required for) | Ghi chú chỉ đọc (Read-only note) |
| :--- | :--- | :--- | :--- | :--- |
| **Ollama** | `192.168.1.196` | 11434 | Live LLM (chat UI/API, phân loại intent, eval live, judge) | Model `qwen3-16k-nothink:latest`. Không có 196: chỉ chạy `pytest` offline (hoặc LLM ngoài qua `LLM_BASE_URL`). |
| **PostgreSQL** | Host LAN từ `.env` (`DB_HOST`) | 5432 | Câu hỏi số liệu đa domain (ITS, fence, face, fire, anomaly) & eval đầy đủ | Chỉ đọc (`SELECT`). Role `agent_readonly`. Cấm INSERT/UPDATE/DELETE. Tùy chọn cho how-to. |
| **ClickHouse** | Host LAN từ `.env` (`CH_HOST`) | 8123 | Tùy chọn (phân tích lưu lượng xe, ưu tiên trước Postgres) | Chỉ đọc (`SELECT` qua HTTP). Fallback về Postgres nếu thiếu hoặc lỗi kết nối. |



