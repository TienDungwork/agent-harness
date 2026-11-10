# API `agent/` + `web_backend/` Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move FastAPI routers into `src/api/agent/` (chat runtime) and `src/api/web_backend/` (sessions/memory/meta/feedback) without changing HTTP URLs or agent behavior.

**Architecture:** Same process (`src.main:app`). Physical move + import updates only. Domain memory stays in `src/domain` / `src/infra`. Delete empty `src/api/routers/` after migrate. Do not use root `dong/backend/`.

**Tech Stack:** FastAPI, pytest, existing `src.api.helpers` / `src.api.models`.

**Spec:** [docs/superpowers/specs/2026-11-10-api-agent-web-backend-layout-design.md](../specs/2026-11-10-api-agent-web-backend-layout-design.md)

## Global Constraints

- HTTP paths and payloads unchanged (`/api/chat`, `/ask`, `/api/agent/stream`, `/api/sessions*`, `/api/memory`, `/api/feedback`, `/api/health`, `/health`, `/api/models`, `/api/llm/ping`, `/api/config`).
- Entry remains `uvicorn src.main:app`.
- No new Docker service / port.
- No shim package `src.api.routers` after cutover (delete folder).
- Commit only when the user explicitly asks (do not auto-commit).
- Working directory for commands: `agent-harness/dong` with `PYTHONPATH=.` (or project venv / container as usual).

## File map

| Action | Path |
|--------|------|
| Create | `src/api/agent/__init__.py`, `src/api/agent/routes_agent.py` |
| Create | `src/api/web_backend/__init__.py`, `routes_{sessions,memory,meta,feedback}.py` |
| Modify | `src/main.py` imports |
| Modify | `tests/test_product_router_ttl_cache.py` monkeypatch path |
| Modify | `src/README.md`, `specs/change-log.md` (short note) |
| Delete | `src/api/routers/` (all files) |
| Optional | remove empty root `backend/` dir |

---

### Task 1: Scaffold packages + move router modules

**Files:**
- Create: `src/api/agent/__init__.py`
- Create: `src/api/agent/routes_agent.py` (copy content from `src/api/routers/routes_agent.py`)
- Create: `src/api/web_backend/__init__.py`
- Create: `src/api/web_backend/routes_sessions.py` (from routers)
- Create: `src/api/web_backend/routes_memory.py`
- Create: `src/api/web_backend/routes_meta.py`
- Create: `src/api/web_backend/routes_feedback.py`
- Modify: none yet for main

**Interfaces:**
- Consumes: existing route handlers unchanged
- Produces:
  - `src.api.agent`: `router` (as `agent_router`), `chat`, `ask`, `stream_agent`
  - `src.api.web_backend`: `sessions_router`, `memory_router`, `meta_router`, `feedback_router` (or `router` per module + package re-exports)

- [x] **Step 1:** `mkdir -p src/api/agent src/api/web_backend`

- [x] **Step 2:** Copy five route files into the two packages (git mv preferred):

```bash
git mv src/api/routers/routes_agent.py src/api/agent/routes_agent.py
git mv src/api/routers/routes_sessions.py src/api/web_backend/routes_sessions.py
git mv src/api/routers/routes_memory.py src/api/web_backend/routes_memory.py
git mv src/api/routers/routes_meta.py src/api/web_backend/routes_meta.py
git mv src/api/routers/routes_feedback.py src/api/web_backend/routes_feedback.py
```

- [x] **Step 3:** Write `src/api/agent/__init__.py`:

```python
"""Chatbot runtime HTTP routes."""

from src.api.agent.routes_agent import ask, chat, router as agent_router, stream_agent

__all__ = ["agent_router", "chat", "ask", "stream_agent"]
```

- [x] **Step 4:** Write `src/api/web_backend/__init__.py`:

```python
"""UI / ops HTTP routes (sessions, memory, meta, feedback)."""

from src.api.web_backend.routes_feedback import router as feedback_router
from src.api.web_backend.routes_memory import router as memory_router
from src.api.web_backend.routes_meta import router as meta_router
from src.api.web_backend.routes_sessions import router as sessions_router

__all__ = [
    "feedback_router",
    "memory_router",
    "meta_router",
    "sessions_router",
]
```

- [x] **Step 5:** Confirm route modules still import `src.api.helpers.*` / `src.api.models.*` (no path change needed inside file bodies unless they self-imported `src.api.routers`).

---

### Task 2: Rewire `main.py` + delete old `routers/`

**Files:**
- Modify: `src/main.py` (import block ~84–88 and any re-exports of `ask`/`chat`/`stream_agent`)
- Delete: `src/api/routers/__init__.py` and leftover `routers/` dir
- Modify: `tests/test_product_router_ttl_cache.py` (~line 97)

**Interfaces:**
- Consumes: Task 1 package exports
- Produces: app still `include_router` same five routers

- [x] **Step 1:** Replace imports in `src/main.py`:

```python
from src.api.agent import ask, chat, agent_router, stream_agent
from src.api.web_backend import (
    feedback_router,
    memory_router,
    meta_router,
    sessions_router,
)
```

Keep `app.include_router(...)` order as today (meta → sessions → memory → feedback → agent).

- [x] **Step 2:** Grep and fix stragglers:

```bash
rg -n "src\.api\.routers" -g '*.py' -g '*.md'
```

Expected hits to fix: `tests/test_product_router_ttl_cache.py` →  
`monkeypatch.setattr("src.api.agent.routes_agent.persist_session_turn", ...)`.

- [x] **Step 3:** Delete `src/api/routers/` entirely.

- [x] **Step 4:** Smoke import:

```bash
PYTHONPATH=. python -c "from src.main import app; print([r.path for r in app.routes if hasattr(r,'path')][:8])"
```

Expected: paths include `/api/health`, `/api/chat`, `/api/sessions`.

---

### Task 3: Docs + verify tests

**Files:**
- Modify: `src/README.md` (api layout one-liner)
- Modify: `specs/change-log.md` (block `## 2026-11-10` at top)
- Optional: remove empty `backend/` at repo root of dong

- [x] **Step 1:** Update `src/README.md` tree to show `api/agent` + `api/web_backend`.

- [x] **Step 2:** Change-log entry: layout move only; URLs unchanged.

- [x] **Step 3:** Run focused tests:

```bash
PYTHONPATH=. pytest tests/test_product_router_ttl_cache.py tests/test_product_api_gateway.py -q --tb=line
```

If host missing deps, run inside `kcn_hungphu_backend` container with same paths.

Expected: collect + pass for import/wiring; pre-existing failures unrelated to imports are OK only if identical before move — prefer green on files that only monkeypatch agent routes.

- [x] **Step 4:** Final grep — zero `src.api.routers` in `*.py`.

- [x] **Step 5:** Stop. Ask user before any git commit.

---

## Execution handoff

Plan saved to `docs/superpowers/plans/2026-11-10-api-agent-web-backend-layout.md`.

**Optional next:** implementing (subagent-driven-development or executing-plans) after you say go.
