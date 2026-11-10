# Design: tách `src/api` thành `agent/` + `web_backend/`

**Ngày:** 2026-11-10  
**Phạm vi:** layout / import only trong `agent-harness/dong`  
**Không làm:** service Docker mới, đổi URL, đổi hành vi agent memory

## Mục tiêu

Làm rõ ranh giới HTTP:

| Package | Vai trò | Routes |
|---------|---------|--------|
| `src/api/agent/` | Runtime AI chatbot | `POST /api/chat`, `POST /ask`, `POST /api/agent/stream` |
| `src/api/web_backend/` | UI + ops (không chạy LangGraph) | sessions, memory CRUD, meta, feedback |

Logic long-term / short-term / sliding window **ở lại** `src/domain` + `src/infra`. Chỉ chuyển **file router**.

## Cấu trúc đích

```
src/api/
  agent/
    __init__.py          # re-export router, ask, chat, stream_agent
    routes_agent.py      # move từ routers/routes_agent.py
  web_backend/
    __init__.py          # re-export 4 routers
    routes_sessions.py
    routes_memory.py
    routes_meta.py
    routes_feedback.py
  helpers/               # giữ nguyên
  models/                # giữ nguyên
  routers/               # XÓA sau khi chuyển + cập nhật import
                           # (tuỳ chọn: shim 1 release re-export — mặc định KHÔNG)
```

Folder root `dong/backend/` (trống) **không dùng** — xóa hoặc bỏ qua.

## Hợp đồng giữ nguyên

- Path HTTP và payload không đổi.
- `uvicorn src.main:app` / Docker `ai_backend` không đổi entry.
- Frontend / nginx không đổi.

## Thay đổi wiring

- `src/main.py`: import từ `src.api.agent` và `src.api.web_backend`.
- `tests/`: cập nhật mọi `src.api.routers.routes_*` (ít nhất `test_product_router_ttl_cache.py`).
- `src/README.md` + `specs/change-log.md`: ghi layout mới.

## Ngoài scope

- Tách process / port thứ hai.
- Di chuyển `helpers`, `schemas`, `application/`, `infra/memory`.
- Đổi auth / RBAC.

## Done khi

1. Không còn `src/api/routers/` (hoặc chỉ còn shim có chủ đích — mặc định xóa hẳn).
2. Import tests + `main` trỏ `agent` / `web_backend`.
3. Smoke: `/api/health`, `/api/sessions`, `/api/agent/stream` (mock OK) vẫn resolve.

## Rủi ro

- Patch/monkeypatch path trong tests cũ gãy nếu sót `src.api.routers.*`.
- Re-export cũ trong `api/routers/__init__.py` nếu ai import ngoài repo — grep trước khi xóa.
