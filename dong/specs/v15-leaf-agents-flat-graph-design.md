# v15 — Leaf agents + flat `vms/graph.py` (kiểu `ai_backend`)

**Status:** Design approved (chat 2026-11-09) — chờ user review file này rồi mới writing-plans / code.  
**Approach:** Move-only packaging (Approach 1 + wiring flat **A**).  
**Không:** LangGraph subgraph `compile()` trong leaf; không đổi logic node.

## Goal

Cây `domain/agents` gần `vn-stock-swarm/.../ai_backend/domain/agents`: leaf `sql_agent` / `docs_agent` + `vms/graph.py` một file “máy chạy” như `ai_backend/.../graph.py`. Hành vi, tên node, edge, HTTP/SSE **giữ nguyên**.

## Non-goals

- Không compile subgraph thật (`sql_agent` / `docs_agent` không gọi `StateGraph.compile()`).
- Không tạo `chart_agent/` (một node `render_chart` → ở `vms/nodes`).
- Không sửa body logic SQL/docs/respond/orchestrator.
- Không bắt buộc drop shim `domain.agents.graph` / `state` / `shared.config` trong cùng phase (14.5 còn lại).
- Không đụng logic `multi_agent/` (chỉ import path nếu cần).

## Quyết định đã chốt

| # | Quyết định |
|---|------------|
| 1 | Scope C (flatten leaf), không chỉ gộp `core/` |
| 2 | Package giống agent (`sql_agent`, `docs_agent`) nhưng wiring **flat** trong `vms/graph.py` |
| 3 | Approach 1 — leaf theo nhánh; bỏ `chart_agent` |
| 4 | Kết quả chạy phải như cũ |

## Target tree

```text
domain/agents/
├── graph.py                 # shim → vms.graph (tạm)
├── state.py                 # shim → vms.state (tạm)
├── vms/
│   ├── graph.py             # build + run + stream + wrap (gộp core/)
│   ├── state.py
│   ├── nodes/
│   │   ├── guardrails.py
│   │   ├── memory.py
│   │   ├── rewrite_classify.py   # gồm routing rewrite/intent/inline
│   │   ├── respond.py            # + simple_answer nếu chỉ respond dùng
│   │   ├── render_chart.py       # từ pipeline; không package chart_agent
│   │   └── io.py
│   └── tools.py             # helpers (strip_thinking, memory_context, chart_fallback, …)
├── sql_agent/
│   ├── graph.py             # re-export node entrypoints only (no compile)
│   ├── state.py             # re-export AgentState
│   └── tools.py             # generate/validate/execute/batch/pre_sql/scope (+ modules nội bộ nếu cần)
├── docs_agent/
│   ├── graph.py             # retrieve_docs / answer_from_docs entrypoints
│   ├── state.py
│   └── tools.py             # docs adapter, camera_registry nếu thuộc docs/list
└── multi_agent/             # giữ
```

**Xóa sau migrate:** `vms/core/`, `vms/sql/`, `vms/routing/`, `vms/respond/`, `vms/adapters/` (nội dung đã chuyển).

## Map hiện tại → đích

| Hiện tại | Đích |
|----------|------|
| `vms/core/{wiring,run,runtime,helpers}` | `vms/graph.py` (+ `vms/tools.py` nếu helper không thuộc graph) |
| `vms/sql/*` | `sql_agent/tools.py` (có thể giữ file con trong package rồi re-export) |
| `pipeline.retrieve_schema` + SQL nodes | `sql_agent` |
| `pipeline.retrieve_docs` / `answer_from_docs` | `docs_agent` |
| `pipeline.render_chart` | `vms/nodes/render_chart.py` |
| `vms/routing/*` | `vms/nodes/rewrite_classify.py` (hoặc module cạnh nodes, import từ nodes) |
| `vms/respond/*` | `vms/nodes/respond` + `vms/tools` (chart_fallback) |
| `vms/adapters/*` | `docs_agent/tools` |

## Data flow (không đổi)

`START → guardrail_input → recall → rewrite → classify → (respond_inline \| orchestrator) → … → respond → guardrail_output → END`

- SQL: `retrieve_schema → generate_sql → validate_sql ⇄ repair_sql → execute_sql → (render_chart\|) → respond`
- Docs: `retrieve_docs → answer_from_docs → respond \| orchestrator_collect`
- Multi: `multi_agent` nodes như hiện tại

Mọi `add_node` / `add_edge` / conditional **chỉ** trong `vms/graph.py`.

## Tương thích

**Giữ:** tên node LangGraph; symbol công khai `_build_graph`, `run_agent`, `run_agent_stream`, `_wrap_node`, `reset_graph` trên `vms.graph`; HTTP + SSE shape.

**Đổi:** import path; tests/monkeypatch path.

**Cấm:** shim chồng cho mọi path cũ trừ khi rollback ngắn có ghi change-log; `compile()` trong leaf.

## Phases

| Phase | Việc | Done khi |
|:-----:|------|----------|
| **15.1** | Spec + AC + plan checkbox | SDD index có v15 |
| **15.2** | Skeleton + move `sql_agent` / `docs_agent` | Import mới OK |
| **15.3** | Gộp `core/` → `vms/graph.py`; routing/respond/chart → nodes/tools | Xóa `vms/core` |
| **15.4** | Rewire repo/tests; xóa package cũ | Grep sạch path cũ |
| **15.5** | `src/README` + change-log + pytest subset | AC-11 pass |

## Acceptance criteria

1. Cây khớp target tree (không `chart_agent`, không `vms/core`).  
2. Tên node LangGraph + edge semantics không đổi.  
3. `run_agent` / stream API không đổi contract.  
4. Leaf `sql_agent` / `docs_agent` **không** `compile()` graph.  
5. Pytest subset: nodes structure, camera registry, greeting offline, `test_v13_*` xanh (fail pre-existing ghi change-log).  
6. Grep không còn `vms.core` / `vms.sql` / `vms.routing` / `vms.respond` / `vms.adapters` trong `.py` (trừ archive/change-log nếu cần).

## Risks

| Risk | Mitigation |
|------|------------|
| Monkeypatch path cũ | Bulk update tests cùng phase 15.4 |
| `_get_graph` mock `_build_graph` | Giữ symbol trên `vms.graph` |
| File `graph.py` quá dài sau gộp core | Chấp nhận tạm (giống ai_backend một file máy chạy); không tách lại `core/` |

## Out of scope follow-ups

- Drop shim `domain.agents.graph` / `state` / `shared.config` (14.5).  
- Subgraph LangGraph thật (cần phase riêng + chấp nhận đổi namespace node).
