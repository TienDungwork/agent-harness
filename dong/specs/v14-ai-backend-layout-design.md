# v14 — Align `dong/src` với kiến trúc `vn-stock-swarm/src/ai_backend`

**Status:** Design approved (chat 2026-11-09) — chờ implementation plan + code.  
**Approach:** Target-tree + move (không rewrite hành vi).  
**Agent packaging:** `domain/agents/vms/` + `domain/agents/multi_agent/`.

## Goal

Phân tách rõ chức năng, code gọn, cây thư mục gần `ai_backend`, đồng thời **chỉ giữ file SDD core** trong `specs/` theo `sdd-guide-vi.md`.

## Non-goals

- Không copy domain chứng khoán (`scan/news`, portfolio, …).
- Không đổi HTTP contract, tên node LangGraph, schema DB, prompt YAML, Langfuse semantics.
- Không thêm dependency mới.

## Target tree

```text
src/
├── main.py
├── api/                         # routers, models, helpers (giữ)
├── application/                 # NEW mỏng: orchestration turn (cache/run)
├── domain/
│   ├── agents/
│   │   ├── vms/                 # graph, state, nodes, sql, routing, respond, adapters, core
│   │   └── multi_agent/         # orchestrator plan / core / synth
│   ├── knowledge/               # RAG docs (giữ)
│   └── guardrails/              # OPTIONAL: domain guardrail helpers (nếu tách gọn từ shared)
├── infra/                       # db, llm, memory, chart, monitoring, prompts, session, feedback
└── shared/
    ├── settings/                # tách từ config.py (re-export tương thích)
    └── …
```

## Import migration

| Cũ | Mới |
|----|-----|
| `src.domain.agents.graph` / `state` | `src.domain.agents.vms.graph` / `vms.state` |
| `src.domain.agents.nodes|sql|routing|respond|adapters|core` | dưới `vms/` |
| `src.domain.agents.orchestrator` | `src.domain.agents.multi_agent` |
| `src.shared.config` | `src.shared.settings` (+ shim `config`) |

**Shims tạm:** `domain.agents.graph` và `shared.config` re-export → xóa sau khi grep sạch (phase 14.5).

## Specs hygiene

**Giữ (core):** `README.md`, `sdd-guide-vi.md`, `superpowers-workflow-vi.md`, `product-spec.md`, `implementation-plan.md`, `test-plan.md`, `change-log.md`, `smoke-manual-checklist.md`, `archive/`, **file design này**.

**Archive:** `v7-chart-ui-audit.md`, `v7-dead-code-inventory.md`, `nested-trace-v13-design.md` (sau khi AC v13 còn sống đã nằm trong product-spec / plan).

## Phases

| Phase | Việc |
|:-----:|------|
| 14.1 | Specs hygiene + gộp AC v13 nếu cần |
| 14.2 | Skeleton packages |
| 14.3 | Move + rewire + shims |
| 14.4 | Docs + `pytest -q` |
| 14.5 | Drop shims (optional) |

Chi tiết checkbox: `implementation-plan.md` § v14.

## Acceptance criteria

1. Cây `src/` khớp target tree ở trên.  
2. `/api/chat`, `/api/agent/stream` không đổi contract.  
3. Tên node LangGraph giữ nguyên.  
4. `pytest -q` xanh (hoặc fail pre-existing đã ghi change-log).  
5. `specs/` chỉ còn core + `archive/` + design v14.  
6. Không dependency mới.

## Risks

- Test/monkeypatch path cũ → cập nhật hoặc dựa shim.  
- Backend Docker mount `./src` → restart sau migrate.
