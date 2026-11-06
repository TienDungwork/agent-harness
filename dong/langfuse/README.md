# Langfuse (self-hosted)

Stack observability tách riêng khỏi `docker-compose.yml` gốc của dong.

## Chạy

```bash
cd agent-harness/dong/langfuse
cp .env.example .env   # nếu chưa có
docker compose up -d
```

Container/volume đều có prefix `kcn_hungphu_langfuse_*` (vd. `kcn_hungphu_langfuse_web`, `kcn_hungphu_langfuse_redis`) — dễ nhận trong `docker ps`.

**Web UI tùy biến:** `langfuse-web` build từ `Dockerfile.web` (base `langfuse:4`) — patch bundle Next.js để cột latency trên cây trace hiển thị **giây với 3 chữ số thập phân** (`formatIntervalSeconds` mặc định `scale=3`). Sau khi pull image Langfuse mới, chạy lại `docker compose build langfuse-web`.

```bash
docker compose build langfuse-web && docker compose up -d langfuse-web
```

Sau khi rebuild patch, **xóa cache site** cho `http://localhost:3001` (DevTools → Application → Clear site data) hoặc tab ẩn danh — Next gắn `immutable` 1 năm trên `/_next/static/chunks/*`, cùng URL có thể vẫn là JS cũ nếu không clear.

Dừng:

```bash
docker compose down
```

Reset data (xóa volume):

```bash
docker compose down -v
docker compose up -d
```

## Đăng nhập UI

- URL: http://localhost:3001 (host; map `3001:3000` nếu cổng 3000 bận)
- Email: `admin@agent-atin.local`
- Mật khẩu: `Atin@123#`
- Project: **agent_ATIN**

API keys (khớp `../.env`):

- `LANGFUSE_PUBLIC_KEY=pk-lf-0c271516-d371-4a03-9ea6-0a9c22f131c2`
- `LANGFUSE_SECRET_KEY=sk-lf-cda213a6-b0a0-4e61-9df5-ca38c0d280c3`

## Kết nối backend dong

| Chạy backend | `LANGFUSE_HOST` | Ghi chú |
|---|---|---|
| Docker (`docker compose up`) | `http://host.docker.internal:3000` | Override trong `docker-compose.yml` gốc |
| Local dev (`uvicorn`) | `http://localhost:3000` | Trong `.env` thư mục gốc `dong` |

App dong (frontend + backend) chạy riêng từ thư mục gốc:

```bash
cd agent-harness/dong
docker compose up --build -d
```
