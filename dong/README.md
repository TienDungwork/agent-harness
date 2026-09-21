# agent_ATIN (kcn_hungphu_agent v3)

Hệ thống Trợ lý AI hỏi-đáp, thống kê và giám sát toàn diện 8 loại sự kiện camera AI VMS (phương tiện, vùng cấm, khuôn mặt, ẩu đả, đám đông, leo trèo, cháy khói, mực nước) tại Khu công nghiệp Hưng Phú.

Dự án được xây dựng theo phương pháp luận **Spec-Driven Development (SDD)**, cấu trúc tinh gọn, dễ đọc, dễ bảo trì, chia tách 2 tầng độc lập **Frontend (FE)** và **AI_Backend**, **giữ nguyên kiến trúc ReAct Agent hiện tại** để dễ đối chứng và so sánh, điều phối trọn gói bằng **Docker Compose**.

---

## Mục Lục
1. [Tài Liệu Dự Án (Project Specs)](#tài-liệu-dự-án-project-specs)
2. [Kiến Trúc Hệ Thống (v3 Architecture)](#kiến-trúc-hệ-thống-v3-architecture)
3. [Phủ 8 Domain Sự Kiện VMS](#phủ-8-domain-sự-kiện-vms)
4. [Prerequisites (Yêu Cầu Tiền Đề)](#prerequisites-yêu-cầu-tiền-đề)
5. [Cài Đặt & Cấu Hình Biến Môi Trường](#cài-đặt--cấu-hình-biến-môi-trường)
6. [Hướng Dẫn Khởi Chạy Bằng Docker Compose](#hướng-dẫn-khởi-chạy-bằng-docker-compose-khuyên-dùng)
7. [Hướng Dẫn Khởi Chạy Local Standalone (Local Development)](#hướng-dẫn-khởi-chạy-local-standalone-dành-cho-development)
8. [Bảng Tổng Hợp Cổng & Địa Chỉ Truy Cập (Local URLs)](#bảng-tổng-hợp-cổng--địa-chỉ-truy-cập-local-urls)
9. [Hướng Dẫn Đăng Nhập & Sử Dụng Langfuse Dashboard](#hướng-dẫn-đăng-nhập--sử-dụng-langfuse-dashboard)
10. [Demo & Expose Ra Ngoài Internet (ngrok)](#demo--expose-ra-ngoài-internet)
11. [Troubleshooting & Xử Lý Sự Cố Thường Gặp](#troubleshooting--xử-lý-sự-cố-thường-gặp)
12. [Kiểm Thử & Đánh Giá Chất Lượng](#kiểm-thử--đánh-giá-chất-lượng)

---

## Tài Liệu Dự Án (Project Specs)

Toàn bộ quy trình phát triển và kiểm thử tuân thủ nghiêm ngặt các tài liệu kỹ thuật:
- [`specs/product-spec.md`](specs/product-spec.md) — Mục tiêu, tính năng, kiến trúc phân tách, tiêu chí nghiệm thu.
- [`specs/implementation-plan.md`](specs/implementation-plan.md) — Kế hoạch từng phase (Phase 1: Setup; Phase 2: UI; Phase 3: AI_Backend ReAct; Phase 4-9: Connect, Observability, Guardrails, Docker, Demo, Eval).
- [`specs/test-plan.md`](specs/test-plan.md) — Kịch bản kiểm thử offline, kiểm thử live model, observability và Docker Compose.
- [`specs/change-log.md`](specs/change-log.md) — Nhật ký chi tiết tiến độ phát triển.
- [`AGENTS.md`](AGENTS.md) — Nguyên tắc kiến trúc và quy chuẩn phát triển cho Coding Agent.

---

## Kiến Trúc Hệ Thống (v3 Architecture)

```
[ Frontend: Claude-inspired UI ]  ◄── Port: 8080 (hoặc 3001)
  │  ├── Tone màu ấm (warm neutral), typography tinh tế, responsive
  │  ├── Hiển thị chi tiết thực thi Tool dạng accordion (dòng DB, thời gian)
  │  └── Modal cấu hình chuyển đổi Model (OpenAI vs Self-hosted Qwen3-4B) & API URL
  │
  ▼ REST API (/api/chat, /api/health, /api/models, /api/config)
[ AI_Backend: FastAPI Service ]    ◄── Port: 8000
  │  ├── Input & Output Guardrails (Regex injection, PII redaction, bounds check)
  │  ├── ReAct Agent Engine (Giữ nguyên: seed → agent ⇄ tools → pack)
  │  ├── 8 Domain Postgres Tools (Role agent_readonly kết nối 5 DBs)
  │  ├── Git-based Prompt Registry (prompts/ qua production.txt)
  │  └── Langfuse Tracing Integration (Lưu Output + Token Metrics + Fail-safe)
  │
  ├──► [ Langfuse Observability ] ◄── Port: 3000 (User: admin@agent-atin.local / Pass: Atin@123#)
  └──► [ LLM Provider ]:
         ├── OpenAI Cloud (`gpt-4o-mini`)
         └── Self-hosted Model (`qwen3-4b` tại http://192.168.1.196:18083/v1)
```

---

## Phủ 8 Domain Sự Kiện VMS

| Domain sự kiện | Bảng dữ liệu Postgres | Tool thực thi | Ví dụ câu hỏi |
|---|---|---|---|
| **Giám sát phương tiện** (`PLATE`) | `its.plate_event` | `count_vehicle_flow`, `vehicle_by_manufacturer`, `trace_vehicle` | "Hôm nay có bao nhiêu lượt xe vào?", "Thống kê xe theo hãng", "Truy vết biển số 65A12345" |
| **Giám sát vùng cấm** (`ZONE`) | `virtual_fence.zone_event` | `zone_intrusion_by_hour` | "Khung thời gian nào xảy ra xâm nhập khu vực nhiều nhất hôm nay?" |
| **Nhận diện khuôn mặt** (`FACE`) | `smart_face.smf_face_events` | `count_face_events` | "Hôm nay có bao nhiêu lượt nhận diện khuôn mặt?" |
| **Phát hiện ẩu đả** (`FIGHT`) | `anomaly.anomaly_event` | `count_anomaly_events(FIGHT_DETECTION)` | "Hôm nay có vụ ẩu đả nào không?" |
| **Phát hiện đám đông** (`CROWD`) | `anomaly.anomaly_event` | `count_anomaly_events(CROWD_DETECTION)` | "Hôm nay có cảnh báo đám đông ở khu vực nào không?" |
| **Phát hiện leo trèo** (`INTRUSION`) | `anomaly.anomaly_event` | `count_anomaly_events(INTRUSION_DETECTION)` | "Hôm nay có phát hiện leo trèo không?" (phân biệt rõ với vùng cấm) |
| **Phát hiện cháy khói** (`FIRE`) | `firesmoke.fire_smoke_event` | `count_fire_smoke_events` | "Hôm nay có cảnh báo cháy hoặc khói không?" |
| **Giám sát mực nước** (`WATER_LEVEL`) | `anomaly.anomaly_event` | `count_anomaly_events(WATER_LEVEL_DETECTION)` | "Mực nước hôm nay có vượt ngưỡng cảnh báo không?" |

**Bổ sung phạm vi sản phẩm (dataset v2.1, tool riêng chưa code):** hỏi đáp cách dùng AIOC Cloud Cam ([https://aioc.atin.vn/devices](https://aioc.atin.vn/devices) — Quản Lý Camera) và **vẽ sơ đồ** các bước thao tác. Guardrail `STAT_KEYWORDS` đã nhận diện các câu này.

---

## Prerequisites (Yêu Cầu Tiền Đề)

Trước khi khởi chạy hệ thống, hãy đảm bảo máy chủ/máy trạm của bạn đáp ứng các yêu cầu sau:

1. **Docker & Docker Compose**:
   - Docker Engine ≥ 24.0.0
   - Docker Compose v2 (lệnh `docker compose`)
2. **Môi trường Python (khi chạy local standalone)**:
   - Python ≥ 3.11 (khuyên dùng Python 3.11 hoặc 3.12)
   - `pip` và `venv`
3. **Kết nối Cơ sở dữ liệu Postgres**:
   - Cụm 5 Database VMS (sử dụng tài khoản read-only `agent_readonly`): `its`, `virtual_fence`, `smart_face`, `firesmoke`, `anomaly`.
4. **LLM Provider (chọn 1 trong 2 hoặc kết hợp)**:
   - **OpenAI Cloud**: `OPENAI_API_KEYS` (sử dụng model `gpt-4o-mini`).
   - **Self-hosted Model (Qwen3-4B)**:
     - Base URL: `http://192.168.1.196:18083/v1`
     - Model Name: `qwen3-4b`
     - API Key: `lgw_ef6984db8f59_zSvqDWXxYzeaU-4U0pLqS7LBiD5gvOm9wI7R-L4Lpqw`

---

## Cài Đặt & Cấu Hình Biến Môi Trường

### 1. Sao Chép Tệp Cấu Hình Môi Trường
```bash
cp .env.example .env
```

### 2. Danh Sách Biến Môi Trường Chi Tiết

| Nhóm | Biến | Giá trị mẫu | Ý nghĩa |
|---|---|---|---|
| **LLM Backend** | `LLM_BACKEND` | `openai` hoặc `self_hosted` | Nhà cung cấp mô hình mặc định |
| | `OPENAI_API_KEYS` | `sk-proj-...` | Danh sách API key OpenAI (phân tách bởi dấu phẩy để hỗ trợ key rotation) |
| | `LLM_MODEL` | `gpt-4o-mini` | Tên model OpenAI mặc định |
| | `LLM_TEMPERATURE` | `0.2` | Độ sáng tạo của model (0.0 - 1.0) |
| | `MODEL_BASE_URL` | `http://192.168.1.196:18083/v1` | URL endpoint model tự host |
| | `MODEL_NAME` | `qwen3-4b` | Tên model tự host |
| | `MODEL_API_KEY` | `lgw_ef6984db8f59_...` | API key endpoint model tự host |
| | `ANSWER_USE_LLM` | `true` | Dùng LLM diễn giải số liệu sang tiếng Việt (`false` = dùng template thô) |
| **Databases** | `DB_HOST` | `192.168.1.250` | Địa chỉ IP / Host của Postgres Server |
| | `DB_PORT` | `18644` (hoặc `5432`) | Cổng kết nối Postgres |
| | `DB_USER` | `agent_readonly` | Tài khoản chỉ đọc (read-only role) |
| | `DB_PASSWORD` | `Atin@123#` | Mật khẩu database |
| | `DB_NAME_ITS` | `its` | Tên DB giám sát phương tiện |
| | `DB_NAME_FENCE` | `virtual_fence` | Tên DB giám sát hàng rào ảo |
| | `DB_NAME_FACE` | `smart_face` | Tên DB nhận diện khuôn mặt |
| | `DB_NAME_FIRE` | `firesmoke` | Tên DB cảnh báo cháy khói |
| | `DB_NAME_ANOMALY` | `anomaly` | Tên DB phát hiện bất thường (đám đông, ẩu đả, mực nước) |
| | `DB_ORGANIZATION_ID`| `106` | ID tổ chức KCN Hưng Phú |
| **Observability** | `MONITORING_ENABLED` | `true` | Bật gửi trace sang Langfuse (`false` = tắt) |
| | `LANGFUSE_HOST` | `http://localhost:3000` | URL máy chủ Langfuse (local host) |
| | `LANGFUSE_PUBLIC_KEY`| `pk-lf-...` | Public key dự án Langfuse |
| | `LANGFUSE_SECRET_KEY`| `sk-lf-...` | Secret key dự án Langfuse |
| **Port Mapping** | `FRONTEND_PORT` | `3001` (hoặc `8080`) | Cổng expose Frontend ngoài host |
| | `BACKEND_PORT` | `8000` | Cổng expose Backend ngoài host |

---

## Hướng Dẫn Khởi Chạy Bằng Docker Compose (Khuyên dùng)

Chỉ với 1 lệnh duy nhất, toàn bộ **Frontend (Claude UI)**, **AI_Backend (FastAPI & ReAct Agent)** và **Cụm Langfuse Observability** sẽ được khởi động đồng bộ và liên thông:

```bash
# 1. Build images nếu có thay đổi mã nguồn
docker compose build

# 2. Khởi động toàn bộ stack ngầm (detached mode)
docker compose up -d

# 3. Kiểm tra trạng thái sức khỏe các container
docker compose ps

# 4. Xem log thời gian thực của toàn bộ hệ thống
docker compose logs -f

# Hoặc chỉ xem log của từng service:
docker compose logs -f ai_backend
docker compose logs -f frontend
docker compose logs -f langfuse-web

# 5. Dừng toàn bộ hệ thống và giải phóng tài nguyên mạng (dữ liệu DB được bảo toàn trong named volumes)
docker compose down
```

---

## Hướng Dẫn Khởi Chạy Local Standalone (Dành cho Development)

Nếu muốn phát triển hoặc debug từng thành phần độc lập mà không qua Docker:

### 1. Khởi chạy AI_Backend (FastAPI & ReAct Agent)
```bash
# 1.1. Tạo và kích hoạt môi trường ảo Python
python3 -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

# 1.2. Cài đặt các gói phụ thuộc
pip install -r requirements.txt

# 1.3. Khởi chạy FastAPI server trên cổng 8000 với live-reload
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
*Kiểm tra backend đã chạy:* Mở trình duyệt tại [http://localhost:8000/api/health](http://localhost:8000/api/health) hoặc [http://localhost:8000/docs](http://localhost:8000/docs).

---

### 2. Khởi chạy Frontend (Claude UI)
```bash
# Phục vụ các file tĩnh HTML/CSS/JS trên cổng 8080 (hoặc cổng bất kỳ)
cd frontend
python3 -m http.server 8080
# Hoặc dùng npx serve:
# npx serve . -p 8080
```
> **Lưu ý khi chạy Frontend Standalone**:
> - Mở trình duyệt tại [http://localhost:8080/](http://localhost:8080/).
> - Nhấn vào nút **Cài đặt (Settings)** ở góc dưới bên trái giao diện để cấu hình ô **API Base URL** thành `http://localhost:8000/api`. Nhấn **Kiểm tra kết nối** và **Lưu Cấu Hình**.

---

### 3. Khởi chạy Cụm Langfuse Observability Standalone (Tùy chọn)
Nếu muốn chạy riêng cụm Langfuse để giám sát khi chạy backend local:
```bash
cd langfuse
docker compose up -d
```
*Truy cập Dashboard:* [http://localhost:3000/](http://localhost:3000/) (User: `admin@agent-atin.local` / Pass: `Atin@123#`).

---

## Bảng Tổng Hợp Cổng & Địa Chỉ Truy Cập (Local URLs)

| Dịch vụ / Giao diện | Cổng Mặc Định | URL Truy Cập | Thông Tin Đăng Nhập / Vai Trò |
|---|---|---|---|
| **Frontend Chat UI (Docker)** | `:3001` (hoặc `:8080`) | [http://localhost:3001/](http://localhost:3001/) | Giao diện Claude-inspired, hỏi đáp tự nhiên 8 domain VMS & Accordion xem chi tiết tool |
| **Frontend Chat UI (Local)** | `:8080` | [http://localhost:8080/](http://localhost:8080/) | Phục vụ file tĩnh khi chạy qua `python3 -m http.server` |
| **AI_Backend REST API** | `:8000` | [http://localhost:8000/api/chat](http://localhost:8000/api/chat) | API Gateway điều phối ReAct Agent, Tool DB & Guardrails |
| **Backend API Health** | `:8000` | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Endpoint kiểm tra sức khỏe hệ thống và kết nối DB/LLM |
| **API Docs (Swagger UI)** | `:8000` | [http://localhost:8000/docs](http://localhost:8000/docs) | Tài liệu kiểm thử API tương tác OpenAPI / Swagger |
| **Langfuse Dashboard** | `:3000` | [http://localhost:3000/](http://localhost:3000/) | **User**: `admin@agent-atin.local`<br>**Password**: `Atin@123#`<br>Giám sát toàn diện trace, output & token usage |
| **MinIO Console / Blob API** | `:9190` | [http://localhost:9190/](http://localhost:9190/) | Lưu trữ media và blob sự kiện của Langfuse |

---

## Hướng Dẫn Đăng Nhập & Sử Dụng Langfuse Dashboard

1. Mở trình duyệt và truy cập: [http://localhost:3000/](http://localhost:3000/)
2. Điền thông tin tài khoản quản trị mặc định:
   - **Email**: `admin@agent-atin.local`
   - **Mật khẩu**: `Atin@123#`
3. Truy cập dự án **`agent_ATIN`**:
   - Tab **Traces**: Xem toàn bộ cây span gọi tool (`chat` $\rightarrow$ `chon_tool` $\rightarrow$ `chay_tool` $\rightarrow$ `dien_giai`), thời gian xử lý và lưu trữ đầy đủ dữ liệu trường `output`.
   - Tab **Generations / Metrics**: Theo dõi chi tiết lượng token tiêu thụ (`prompt_tokens`, `completion_tokens`, `total_tokens`), model (`gpt-4o-mini` hoặc `qwen3-4b`) và độ trễ phản hồi (`latency_s`).

---

## Demo & Expose Ra Ngoài Internet

Hệ thống hỗ trợ demo từ xa cho Ban quản lý hoặc khách hàng thông qua công cụ tạo đường hầm an toàn như `ngrok` hoặc `cloudflared`.

### 1. Expose Giao Diện Frontend bằng `ngrok`

Khi hệ thống đang chạy qua Docker Compose (hoặc Frontend standalone):

```bash
# Trường hợp 1: Expose Frontend phục vụ qua Docker Nginx (Cổng mặc định 3001 hoặc 8080)
ngrok http 3001
# Hoặc nếu chạy cổng 8080:
ngrok http 8080
```

*Cơ chế tự động:* Khi truy cập qua đường link công khai `https://<id>.ngrok-free.app`:
- Nginx reverse-proxy đã tích hợp sẵn bên trong container Frontend sẽ tự động chuyển tiếp mọi request `/api/chat`, `/api/health`, `/api/models` sang AI_Backend.
- Người dùng có thể sử dụng ngay mà không cần cấu hình thêm bất kỳ cài đặt nào.

---

### 2. Demo AI_Backend Độc Lập & Cấu Hình API Base URL Từ Xa

Trong trường hợp bạn muốn expose riêng AI_Backend hoặc trỏ Frontend tới một máy chủ AI khác:

```bash
# Expose riêng AI_Backend
ngrok http 8000
```
*Kết quả:* `ngrok` cung cấp URL công khai, ví dụ: `https://ai-backend-demo.ngrok-free.app`.

**Các bước cấu hình trên Giao diện Claude UI:**
1. Mở giao diện web tại trình duyệt.
2. Nhấn vào thanh chọn Model / Cài đặt ở góc dưới Sidebar bên trái (`OpenAI (gpt-4o-mini)` hoặc biểu tượng bánh răng).
3. Tại ô **API Base URL (Backend)**, nhập URL công khai của Backend kèm path `/api`:
   ```
   https://ai-backend-demo.ngrok-free.app/api
   ```
4. Nhấn nút **Kiểm tra kết nối Backend** — hệ thống sẽ gọi thử `/api/health` và hiển thị thông báo trạng thái màu xanh `✅ Kết nối thành công`.
5. Chọn LLM Provider mong muốn (`OpenAI Cloud` hoặc `Model Tự Host Qwen3-4B`).
6. Nhấn nút **Lưu Cấu Hình** — cấu hình được lưu vào `localStorage` của trình duyệt và áp dụng ngay lập tức cho các câu hỏi tiếp theo.

---

## Troubleshooting & Xử Lý Sự Cố Thường Gặp

### 1. Xung Đột Cổng (Port Conflict)
- **Hiện tượng**: Báo lỗi `address already in use` trên cổng 8080, 3001, hoặc 3000 khi chạy `docker compose up -d`.
- **Cách xử lý**:
  - Mở file `.env` và thay đổi cổng expose ra host:
    ```bash
    FRONTEND_PORT=8082
    BACKEND_PORT=8002
    ```
  - Kiểm tra và tắt tiến trình chiếm dụng cổng:
    ```bash
    sudo lsof -i :8080
    sudo lsof -i :3000
    ```

### 2. Không Kết Nối Được Database Postgres
- **Hiện tượng**: Backend trả lời `"Lỗi kết nối cơ sở dữ liệu VMS..."` hoặc API health check báo `its: error`.
- **Cách xử lý**:
  - Kiểm tra kết nối mạng tới IP Postgres host (`DB_HOST`):
    ```bash
    ping -c 3 192.168.1.250
    telnet 192.168.1.250 18644
    ```
  - Đảm bảo tài khoản `agent_readonly` đã được cấp quyền đọc trên 5 DB:
    ```sql
    GRANT CONNECT ON DATABASE its, virtual_fence, smart_face, firesmoke, anomaly TO agent_readonly;
    GRANT USAGE ON SCHEMA public TO agent_readonly;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;
    ```

### 3. Lỗi Langfuse Server hoặc Tracing Không Ghi Nhận
- **Hiện tượng**: Log backend hiển thị cảnh báo `Transient error HTTPConnectionPool` hoặc trace không xuất hiện trong Langfuse UI.
- **Cách xử lý**:
  - Khi chạy trong Docker Compose: Container `ai_backend` tự động kết nối với Langfuse qua URL nội bộ `http://langfuse-web:3000`.
  - Khi chạy local standalone: Đảm bảo trong file `.env` có cấu hình `LANGFUSE_HOST=http://localhost:3000` và `LANGFUSE_BASE_URL=http://localhost:3000`.
  - Cơ chế **Fail-safe** của hệ thống đảm bảo: Nếu Langfuse server bị tắt hoặc lỗi kết nối, AI Backend **vẫn tiếp tục trả lời bình thường**, không làm crash ứng dụng.

### 4. Lỗi Gọi Model Tự Host (Timeout hoặc Không Phản Hồi)
- **Hiện tượng**: Câu hỏi mất nhiều thời gian hoặc trả về thông báo lỗi timeout.
- **Cách xử lý**:
  - Kiểm tra trạng thái endpoint model tự host:
    ```bash
    curl -s http://192.168.1.196:18083/v1/models
    ```
  - Kiểm tra API Key `MODEL_API_KEY` trong `.env`.
  - Trên giao diện web: Mở Modal Cài đặt $\rightarrow$ Chuyển sang `OpenAI Cloud (gpt-4o-mini)` để tiếp tục trải nghiệm.

### 5. Lỗi CORS Khi Chạy Frontend Local Standalone
- **Hiện tượng**: Trình duyệt báo lỗi `CORS policy: No 'Access-Control-Allow-Origin' header` trong Console.
- **Cách xử lý**:
  - AI_Backend FastAPI đã được cấu hình middleware `CORSMiddleware` với `allow_origins=["*"]`, `allow_methods=["*"]`.
  - Đảm bảo bạn nhập đúng địa chỉ API trong ô Settings: `http://localhost:8000/api` (kèm tiền tố `http://` và `/api`).

---

## Kiểm Thử & Đánh Giá Chất Lượng

### 1. Chạy Toàn Bộ Unit Test Tự Động (Offline)
```bash
pytest -v
```
*(Đảm bảo 100% test cases passed: 115/115 passed, bao phủ guardrails, LLM backends, DB tools, tracing no-op, prompt registry và docker compose)*.

---

### 2. Chạy Bộ Đánh Giá Golden Dataset (30 Cases — v2.1)
```bash
python3 eval/run.py
```
*(Dataset `eval/datasets/agent_stat/v2.yaml` version **2.1**: vẫn **30 case**, tỉ lệ **18 lookup / 6 comparison / 3 out_of_scope / 3 injection**. Lookup gồm 8 domain VMS rút gọn + **AIOC howto** ([/devices](https://aioc.atin.vn/devices)) + **vẽ sơ đồ**; comparison giữ case chống hồi quy + 2 case AIOC/diagram. Tool AIOC/diagram chưa code — case mới assert nội dung.)*

---

### 3. Xuất Sơ Đồ Đồ Thị ReAct Graph
```bash
python3 -m src.agent.graph
```
*Tạo mới tệp ảnh `graph.png`, tệp Mermaid `graph.mmd` và tệp HTML tương tác `graph_diagram.html` thể hiện cấu trúc `seed → agent ⇄ tools → pack`.*


