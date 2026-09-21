# Local AI Agent

Local · LangGraph · Ollama (`qwen3-16k-nothink`) + Remote `qwen3:4b-q4_K_M` @ 192.168.1.198 + PostgreSQL read-only.

```bash
uv sync --extra dev
cp .env.example .env   # điền DB_PASSWORD

uv run agent llm-ping
uv run agent db-ping
uv run agent ask "Có bao nhiêu event bất thường?"
uv run pytest
```

## Giao diện web

Hai terminal:

```bash
# API FastAPI :8000
uv run agent-serve

# UI React (trong thư mục web)
cd web && npm install && npm run dev
```

Mở trên máy này: http://127.0.0.1:5174  
Trong LAN: http://<IP-máy-này>:5174 (Vite `host: true`). API vẫn `127.0.0.1:8000`, UI proxy `/api`.

## Tìm kiếm web (SearXNG)

```bash
cd infra/searxng
cp .env.example .env   # lần đầu
# tạo core-config/settings.yml (xem infra/searxng/README.md)
docker compose up -d
curl 'http://127.0.0.1:8889/search?q=ALPR&format=json' | head -c 200
```

Thêm `SEARXNG_URL` vào `.env` (mặc định `http://127.0.0.1:8889`). Agent dùng intent `web_search` cho câu hỏi kiến thức/tin trên mạng.

Docs: `docs/muc-tieu.md`, `docs/ket-noi-db.md`, `docs/base_code.md`.
