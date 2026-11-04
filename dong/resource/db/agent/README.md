# Agent PostgreSQL (tách VMS)

Database **chỉ** cho agent: chat sessions, human feedback (like/dislike), LangGraph checkpoints. **Long-term facts** → Qdrant (`QDRANT_URL`).

| Biến | Mặc định | DBeaver (máy bạn) |
|------|----------|-------------------|
| `AGENT_DB_HOST` | `localhost` | Host |
| `AGENT_DB_PORT` | `5433` | Port |
| `DB_NAME_AGENT` | `kcn_agent` | Database |
| `AGENT_DB_USER` | `atin` | User |
| `AGENT_DB_PASSWORD` | `Atin@123#` | Password |

VMS Text-to-SQL vẫn dùng `DB_HOST` / `DB_NAME_ITS` … — **không** ghi vào DB này.

## Lưu data trên disk

PostgreSQL ghi vào **`resource/db/agent/data/pgdata/`** (bind mount). `docker compose down` **không** xóa data — chỉ dừng container. Data mất nếu bạn xóa thư mục `pgdata` hoặc chạy init lại trên thư mục trống.

Thư mục `pgdata/` nằm trong `.gitignore` (không commit DB lên git).

## Khởi động (tự chọn port nếu 5433 bận)

```bash
cd agent-harness/dong
./scripts/start-agent-db.sh
```

Script ghi `AGENT_DB_PORT` mới vào `.env` khi phải đổi port. Thủ công:

```bash
docker compose -f resource/db/agent/docker-compose.yml up -d
```

Backend Docker: `AGENT_DB_HOST=agent_postgres`, port `5432` (xem `docker-compose.yml` gốc).

## Bảng (init.sql)

- `chat_sessions`, `chat_session_messages`, `human_feedback`
- Long-term facts: **Qdrant** (`QDRANT_COLLECTION`, data: `resource/db/agent/data/qdrant/`) — không dùng bảng `user_memories` (đã DROP khi backend chạy `init.sql`).
- Checkpoint LangGraph: tạo khi `ai_backend` start (`PostgresSaver.setup()`)
