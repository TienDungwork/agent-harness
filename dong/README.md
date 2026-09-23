# agent dong — VMS Analytics Agent (v7)

Trợ lý tiếng Việt thông minh cho hệ thống VMS KCN Hưng Phú: truy vấn số liệu read-only (text-to-SQL), hướng dẫn vận hành VMS/AIOC, biểu đồ trực quan (Canvas Chart.js & PNG), phiên hội thoại (session UI), bộ nhớ ngữ cảnh (memory) và đồ thị giám sát thực thi (live graph hover).

**Trạng thái v7:** Production verified trên Docker + gateway 196 — smoke **7/7**, pytest **595**, eval golden-30 **27/30** (target ≥28: residual case 018, 021, 023).

---

## Specs (tài liệu tham chiếu)

| File | Nội dung |
|------|----------|
| [specs/product-spec.md](specs/product-spec.md) | Mục tiêu, người dùng, kiến trúc luồng, phạm vi, tiêu chí nghiệm thu |
| [specs/implementation-plan.md](specs/implementation-plan.md) | Kế hoạch triển khai Phase 1–7 |
| [specs/v7-chart-ui-audit.md](specs/v7-chart-ui-audit.md) | Vị trí render chart (Canvas Chart.js / PNG) |
| [specs/test-plan.md](specs/test-plan.md) | Kế hoạch kiểm thử pytest + live + golden-30 |
| [specs/change-log.md](specs/change-log.md) | Nhật ký thay đổi và đánh giá qua từng phase |
| [AGENTS.md](AGENTS.md) | Quy chuẩn và hướng dẫn dành cho agent |

---

## Kiến trúc thực thi (v7)

```text
câu hỏi → guardrail → classify
              ├─ chào / clarify → respond_inline (1 hop) → xong
              ├─ hướng dẫn → retrieve_docs → answer_from_docs → xong
              └─ số liệu → retrieve_schema (≤4 bảng)
                           → generate_sql (cap tokens + time_range + chart hint)
                           → validate_sql ↔ repair_sql (≤2 lần)
                           → execute_sql (Postgres read-only)
                           → render_chart (Chart.js / Matplotlib Agg) / respond (simple answer fast skip)
                           → xong
```

---

## Quick Start (Chạy ứng dụng chỉ với Docker)

Toàn bộ ứng dụng (Backend FastAPI + Frontend Nginx) được đóng gói và chạy thông qua **Docker Compose**. Người dùng mới không cần cài đặt Python, Node.js hay `pip install` trên máy host.

### 1. Khởi động môi trường

```bash
cd agent-harness/dong

# 1. Tạo file cấu hình từ file mẫu
cp .env.example .env

# 2. Khởi động toàn bộ dịch vụ (Backend + Frontend)
docker compose up --build -d
```

### 2. Checklist kiểm tra hệ thống

- [ ] **Kiểm tra trạng thái Backend**:
  ```bash
  curl -sf http://localhost:8000/api/health
  # Trả về: {"status":"ok","llm_backend":"self_hosted","active_model":"qwen3-4b",...}
  ```
- [ ] **Kiểm tra kết nối LLM (LLM Ping)**:
  ```bash
  curl -sf http://localhost:8000/api/llm/ping
  # Trả về: {"status":"OK","backend":"self_hosted","model":"qwen3-4b",...}
  ```
- [ ] **Chạy script xác minh tự động**:
  ```bash
  ./scripts/verify-docker-self-hosted.sh
  ```
- [ ] **Mở giao diện Web UI**: Truy cập `http://localhost:3001` (hoặc port `FRONTEND_PORT` trong `.env`).
- [ ] **Chạy bộ kiểm thử khói (Smoke Tests)**:
  ```bash
  ./scripts/smoke-production.sh
  ```
- [ ] **Eval golden-30** (cần LLM 196 + DB):
  ```bash
  PYTHONPATH=. python eval/run.py
  # Kết quả: eval/results/golden-30.md
  ```

### 3. Production verify (Phase 7 — đã chạy 2026-09-23)

| Script | Kết quả |
|--------|---------|
| `verify-docker-self-hosted.sh` | PASS |
| `smoke-production.sh` | 7/7 PASS |
| `pytest -q` | 595 passed |
| `eval/run.py` | 27/30 (018, 021, 023 fail) |

Checklist UI tay: [specs/smoke-manual-checklist.md](specs/smoke-manual-checklist.md)

---

## Cấu hình Backend LLM

| Môi trường | Cấu hình trong `.env` | Mô tả |
|------------|------------------------|-------|
| **Production** *(Mặc định)* | `LLM_BACKEND=self_hosted`<br>`MODEL_BASE_URL=http://192.168.1.196:18083/v1`<br>`MODEL_NAME=qwen3-4b`<br>`MODEL_API_KEY=...` | Chạy qua LiteLLM Gateway nội bộ tại IP 196 |
| **OpenAI Smoke** *(Fallback/Dev)* | `LLM_BACKEND=openai`<br>`OPENAI_API_KEY=sk-...`<br>`OPENAI_MODEL=gpt-4o-mini` | Dùng để smoke test nhanh khi không có kết nối mạng LAN 196 |

---

## Giám sát Tracing Langfuse (Tùy chọn)

Để bật tracing toàn diện các node trong đồ thị LangGraph qua Langfuse:

1. Thêm cấu hình vào `.env`:
   ```bash
   MONITORING_ENABLED=true
   LANGFUSE_HOST=http://192.168.1.196:13000
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
2. Khởi động lại Docker: `docker compose up -d`
3. Xem vết thực thi tại giao diện Langfuse: `http://192.168.1.196:13000`.

---

## Chạy kiểm thử tự động (Dev / Test)

```bash
# Chạy toàn bộ 595 tests
pytest -q
```
