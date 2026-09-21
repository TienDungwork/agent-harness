# Langfuse (self-hosted)

Stack observability tách riêng khỏi `docker-compose.yml` gốc của dong.

## Chạy

```bash
cd agent-harness/dong/langfuse
cp .env.example .env   # nếu chưa có
docker compose up -d
```

Hoặc từ thư mục `dong`: `./scripts/setup-langfuse.sh` (khởi động cả Langfuse + app).

## Đăng nhập UI

- URL: http://localhost:3000
- Email: `admin@agent-atin.local`
- Mật khẩu: `Atin@123#`
- Project: **agent_ATIN**

API keys (khớp `../.env`):

- `LANGFUSE_PUBLIC_KEY=pk-lf-0c271516-d371-4a03-9ea6-0a9c22f131c2`
- `LANGFUSE_SECRET_KEY=sk-lf-cda213a6-b0a0-4e61-9df5-ca38c0d280c3`

## Kết nối backend dong

| Chạy backend | `LANGFUSE_HOST` trong `.env` |
|---|---|
| Docker (`docker compose up`) | `http://host.docker.internal:3000` (mặc định trong compose) |
| Local (`uvicorn`) | `http://localhost:3000` |

## Reset data (init lại user + keys)

```bash
docker compose down -v
docker compose up -d
```
