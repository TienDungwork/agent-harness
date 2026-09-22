# agent dong (v5)

Trợ lý VMS KCN Hưng Phú: số liệu read-only, hướng dẫn VMS, biểu đồ, live graph.

**Current state:** v5 demo-ready — chi tiết acceptance tại [specs/product-spec.md](specs/product-spec.md).

## Specs

| File | Nội dung |
|------|----------|
| [specs/product-spec.md](specs/product-spec.md) | Mục tiêu, flow, acceptance |
| [specs/implementation-plan.md](specs/implementation-plan.md) | Phase 1→7 |
| [specs/test-plan.md](specs/test-plan.md) | pytest, Docker live, golden-30 |
| [specs/change-log.md](specs/change-log.md) | Lịch sử thay đổi |
| [AGENTS.md](AGENTS.md) | Quy tắc coding agent |

## Kiến trúc (tóm tắt)

Graph v5: `rewrite → classify → [route]` — nhánh số liệu (`QueryPlan` + SQL read-only), nhánh docs (YAML cards), optional chart PNG.

```text
src/main.py          # FastAPI — /api/agent/stream, /api/health
src/llm/structured.py
src/agent/graph.py
src/db/query_builder.py
src/knowledge/       # YAML docs
src/chart/render.py
frontend/            # chat + SSE graph
langfuse/            # observability (stack riêng)
```

---

## Local development

Đường chạy trên máy dev (uvicorn + static frontend). **Deploy/demo production dùng Docker** (mục bên dưới).

### Prerequisites

- **Python 3.11+**
- **pip** / **venv**
- LAN tới **LLM gateway** (mặc định `192.168.1.196:18083`) nếu chạy LLM live
- Postgres **read-only** (`agent_readonly`) — cần cho câu hỏi số liệu; how-to/guardrail vẫn chạy khi chưa có DB
- (Tuỳ chọn) Langfuse local — `cd langfuse && docker compose up -d`

### Install

```bash
cd agent-harness/dong
cp .env.example .env          # chỉnh LLM + DB
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Chỉnh `.env` (xem [.env.example](.env.example)). Nhóm chính:

| Nhóm | Biến | Ghi chú |
|------|------|---------|
| **LLM (OpenAI)** | `LLM_BACKEND=openai`, `LLM_MODEL`, `OPENAI_API_KEYS` | Mặc định trong `.env.example` |
| **LLM (vLLM qua gateway)** | `LLM_BACKEND=self_hosted`, `MODEL_*` | Demo: gateway `196:18083` → vLLM `qwen3-4b` + `MODEL_API_KEY` |
| **Postgres** | `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME_*` | Read-only; 5 DB VMS |
| **ClickHouse** | `CH_HOST`, `CH_PORT`, … | Tuỳ chọn |
| **Langfuse** | `MONITORING_ENABLED`, `LANGFUSE_*`, `LANGFUSE_HOST` | Local dev: `LANGFUSE_HOST=http://localhost:3000` |
| **v5** | `DOCS_ROOT`, `SQL_REPAIR_MAX` | YAML cards; số lần SQL repair |
| **Cổng** | `FRONTEND_PORT`, `BACKEND_PORT` | Chủ yếu cho Docker; local thường 8080 / 8000 |

**Kiến trúc LLM:** `dong` → `MODEL_BASE_URL` (OpenAI API) → gateway `:18083` server 196 → **vLLM**.

Demo trên `.env`:

```bash
LLM_BACKEND=self_hosted
MODEL_BASE_URL=http://192.168.1.196:18083/v1
MODEL_NAME=qwen3-4b
MODEL_API_KEY=<gateway_api_key>
```

### Backend run command

Từ thư mục `agent-harness/dong` (venv đã activate):

```bash
uvicorn src.main:app --reload --port 8000
```

Kiểm tra:

```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/llm/ping
python3 -c "from src.llm import ping; print(ping())"
```

### Frontend run command

Terminal khác:

```bash
cd agent-harness/dong/frontend
python3 -m http.server 8080
```

Trong UI → **Cài đặt** → **API Base URL** = `http://localhost:8000` (local không có Nginx proxy).

### Local URLs

| Dịch vụ | URL |
|---------|-----|
| Frontend UI | http://localhost:8080 |
| Backend API / health | http://localhost:8000/api/health |
| Agent stream (SSE) | http://localhost:8000/api/agent/stream |
| Langfuse (tuỳ chọn) | http://localhost:3000 — `admin@agent-atin.local` / `Atin@123#` |

### Troubleshooting (local)

| Vấn đề | Cách xử lý |
|--------|------------|
| UI không gửi được chat | Settings → API Base URL = `http://localhost:8000` → Lưu |
| `/api/llm/ping` lỗi | Gateway: `curl -s -H "Authorization: Bearer $MODEL_API_KEY" http://192.168.1.196:18083/v1/models`; xem `LLM_BACKEND=self_hosted` + `MODEL_*` |
| Không thấy Langfuse trace | `MONITORING_ENABLED=true`; Langfuse stack đang chạy; `LANGFUSE_HOST=http://localhost:3000` |
| Câu số liệu lỗi DB | Điền `DB_*`; user read-only; nhánh how-to vẫn chạy không cần DB |
| pytest | `pytest -q` — offline, không cần LAN 196 |

---

## Docker deploy

**Đường chính** cho demo/production — không cần `.venv` trên máy deploy.

### Prerequisites

- Docker 24+ & Docker Compose 2.20+
- LAN tới LLM gateway 196:18083 (hoặc chỉnh `MODEL_*` trong `.env`)
- Postgres read-only cho câu số liệu

### Install & run

```bash
cd agent-harness/dong
cp .env.example .env              # chỉnh LLM + DB

# App dong:
docker compose up --build -d

# Langfuse (tuỳ chọn, terminal/stack riêng):
cd langfuse && cp -n .env.example .env && docker compose up -d
```

Dừng:

```bash
docker compose down
cd langfuse && docker compose down    # nếu đã bật Langfuse
```

Biến môi trường: cùng bảng [Environment variables](#environment-variables) ở trên. Trong container backend, `docker-compose.yml` **override** `LANGFUSE_HOST=http://host.docker.internal:3000` — không cần sửa `.env` cho Langfuse khi chạy Docker.

Gateway trên **cùng máy host** với Docker (hiếm — thường dùng IP LAN `196:18083`):

```bash
LLM_BACKEND=self_hosted
MODEL_BASE_URL=http://host.docker.internal:18083/v1
```

### Docker URLs

| Dịch vụ | URL |
|---------|-----|
| Frontend | http://localhost:8080 *(hoặc `$FRONTEND_PORT`)* |
| Backend health | http://localhost:8000/api/health |
| Langfuse | http://localhost:3000 — project **agent_ATIN** |

UI Docker: **API Base URL để trống** (Nginx proxy `/api/` sang backend).

Chi tiết Langfuse: [langfuse/README.md](langfuse/README.md).

### Troubleshooting (Docker)

| Vấn đề | Cách xử lý |
|--------|------------|
| UI không chat được | Settings → API Base URL **trống** → Lưu |
| Langfuse không có trace | Stack Langfuse đang chạy; `MONITORING_ENABLED=true`; backend dùng `host.docker.internal:3000` |
| LLM ping fail trong container | `curl` gateway từ host; kiểm tra `MODEL_API_KEY`; IP LAN `196:18083` thường ổn từ container |
| Build lâu | Lần đầu `docker compose up --build`; lần sau `-d` không `--build` nếu không đổi code |

---

## Demo checklist (5 phút)

1. `docker compose up --build -d` (+ `cd langfuse && docker compose up -d` nếu cần trace)
2. Health + ping: `curl -s http://localhost:8000/api/health` và `/api/llm/ping`
3. UI http://localhost:8080 — câu số liệu (*"Hôm nay có bao nhiêu xe CAR vào?"*)
4. How-to (*"Làm sao thêm camera?"*)
5. Biểu đồ (*"Vẽ biểu đồ xe vào theo loại hôm nay"*)
6. Langfuse http://localhost:3000 — trace `chat` + spans
7. Hover graph node → input/output

---

## Testing & evaluation

```bash
cd agent-harness/dong
pytest -q                                    # offline
python eval/run.py                           # golden-30 live (~15–30 phút)
python eval/run.py --judge
python eval/run.py --offline                 # CI/mock
```

Không set `PYTEST_CURRENT_TEST` khi chạy eval live. Output: `eval/results/golden-30.md`.

---

## Tham chiếu

- Structured output: `llm-engineer-demo/`
- YAML docs, SQL validator, chart: port từ `agent-harness/duy/`
