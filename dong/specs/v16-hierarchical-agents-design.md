# v16 — Hierarchical agents (`analytics_team` | `knowledge_team`)

**Status:** Design approved + plan written — [v16-hierarchical-agents-plan.md](v16-hierarchical-agents-plan.md). Chờ chọn cách execute.  
**Approach:** Spec-first theo phase (Approach 3).  
**Baseline:** v15 (leaf + flat `vms/graph.py`) đang chạy.  
**Tham chiếu:** `vn-stock-swarm/.../ai_backend/domain/agents` + `application/chat_service.py`.

## Goal

Reshape `dong/src/domain/agents` thành hierarchical multi-agent: root graph + team subgraphs + `AgentTurnService` như swarm `ChatService`. Giảm shim/cây trùng; graph build đúng chỗ; application điều phối turn.

## Non-goals

- Không copy domain chứng khoán (scan HITL, portfolio, …).
- Không thêm ReAct loop trong worker SQL/docs ở v16 (giữ node deterministic). ReAct = scope sau nếu product đòi.
- Không big-bang một PR: mỗi phase một task theo `AGENTS.md`.
- Không giữ flat-only rule của v15 khi mâu thuẫn với v16 (v16 **supersede** non-goal “không compile subgraph”).

## Quyết định đã chốt

| # | Quyết định | Chọn |
|---|------------|------|
| 1 | Scope reshape | **C** — hierarchical multi-agent (supervisor + teams) |
| 2 | Team topology | **2** — `analytics_team` (SQL+chart) \| `knowledge_team` (docs/RAG) |
| 3 | Multi-intent | **A** — `top_supervisor` lặp team, rồi `synth` ở root |
| 4 | Shared prefix | **1** — `guardrail → recall → rewrite → classify → top_supervisor` |
| 5 | HTTP / SSE | **B** — được đổi contract; cập nhật frontend cùng phase |
| 6 | Delivery | **3** — spec-first, 7 phase |

## Relationship to v14 / v15

| Spec | Vai trò sau v16 |
|------|-----------------|
| v14 | Layout `vms` + `multi_agent` + `application` — baseline packaging |
| v15 | Leaf `sql_agent`/`docs_agent` + flat wiring — **hoàn thành**; logic node tái sử dụng |
| v16 | Nâng flat → hierarchical subgraphs; root `graph.py` thật; SSE mới |

## Target tree

```text
domain/agents/
  graph.py                 # root: build_graph, start_graph, checkpointer
  state.py                 # AssistantState + AgentState
  nodes/                   # package (file nodes.py không đủ chỗ): supervisor + prefix
    __init__.py            # top_supervisor_node, route_from_top
    supervisor.py plan.py synth.py
    guardrails.py memory.py rewrite*.py respond.py …
  stream.py tools.py       # SSE queue + helpers (cần cho graph)
  analytics/
    state.py graph.py nodes.py chart_fallback.py
    sql_agent/tools/       # worker SQL deterministic
  knowledge/
    state.py graph.py nodes.py
    docs_agent/            # worker docs/RAG
application/
  agent_turn.py            # AgentTurnService
```

**Quy tắc**

- Chỉ root `graph.py` compile graph tổng + expose `start_graph` (yield `token` / `result` / progress).
- Team chỉ `build_*_graph()`; không `run_agent` trong package team.
- Sau phase 7: xóa shim/`vms/` wiring phẳng + cây trùng (`nodes/`, `sql/`, `routing/`, `orchestrator/`, `core/` nếu còn) khi logic đã chuyển.
- Router mỏng: validate/cache → service; không rewrite/classify ở API.

## Graph flow

```text
START → guardrail_input → recall → rewrite → classify
  → top_supervisor ⇄ analytics_team | knowledge_team
  → synth → guardrail_output → END
```

- Greeting / out_of_scope: **classify** (prefix) set intent → `top_supervisor` route thẳng `synth` (không vào team).  
  (Override câu chữ topology-2 “gộp vào entry team”: với shared prefix đã chọn, không nhân đôi greeting trong từng team.)
- Multi: supervisor chọn team theo step còn lại; hết step → `synth`.

## Loops (so với graph v15 flat)

| Loop | v15 (hiện tại) | v16 | Ghi chú |
|------|----------------|-----|---------|
| Multi | `orchestrator` ⇄ SQL/docs ⇄ `orchestrator_collect` | `top_supervisor` ⇄ teams → `synth` | Cùng semantics; đổi tầng |
| SQL repair | `validate` ⇄ `repair` (+ execute→repair) | Trong `analytics_team` | Không đưa lên root |
| ReAct worker | Không | Không (v16) | Non-goal |
| Shared prefix | Một lần | Một lần | Không loop |

**Không thêm loại loop mới so với gốc.**

## State (3 tầng)

| Layer | Type | Nội dung chính |
|-------|------|----------------|
| Root | `AssistantState` | `messages`, `user_id`, `session_id`, `question`, `rewritten`, `intent`, `recalled_memories`, `final_answer`, multi tối thiểu (`next_team`, `step_results`, …) |
| Analytics | `AnalyticsTeamState` | SQL/chart/batch (`sql`, `rows`, `chart_*`, `repair_count`, …) |
| Knowledge | `KnowledgeTeamState` | `docs_answer` + retrieval |

Team state khai báo lại field chung cần nhận/trả. Field nội bộ không lên root.

## Application — `AgentTurnService`

Giống `ChatService` swarm:

- `request_deps()` — ports/config → graph context
- `process()` — `start_graph` → DTO một lần
- `stream_sse()` — cùng graph, map event → SSE
- Cache TTL helpers có thể ở cùng module hoặc helper cạnh service; router không chứa business graph

`main.run_agent*` → thin wrapper gọi service (hoặc router gọi service trực tiếp).

## SSE contract (mới — lựa chọn B)

```text
data: {"token": "..."}
data: {"node": "<id>", "status": "done", ...}
data: {"complete": true, "question": "...", "answer": "...", "detail": {...}, "chart": {...}}
data: [DONE]
```

- Lỗi: `{"error": "..."}` rồi dừng.
- Cache-hit: `node: "cache"` rồi `complete` (cùng schema).
- Thay dual-path cũ (`__final_result__` / `node_id: "__answer__"`).
- Frontend cập nhật **cùng phase 6**.

## Error handling

- Guardrail input chặn → `final_answer` an toàn → output guardrail → END.
- Lỗi team: ghi `error`; synth/respond vẫn trả câu thân thiện; không nuốt lỗi I/O.
- TTL/cache set fail: log + vẫn trả answer.
- Store memory sau turn fail: degraded, không fail cả turn.

## Phases

1. Spec + skeleton: `state.py`, root `graph.py` / `nodes.py` stub  
2. Shared prefix nodes vào root wiring  
3. `analytics/` subgraph (SQL+chart+repair)  
4. `knowledge/` subgraph  
5. `top_supervisor` loop + root `synth`  
6. `AgentTurnService` + SSE mới + frontend  
7. Xóa dead/shim; sửa import/test; `change-log` + đánh dấu plan  

Mỗi phase: cập nhật `implementation-plan.md` task, test tối thiểu (build graph / route / contract SSE khi tới phase 6), rồi `change-log`.

## Testing (mỗi phase)

- Unit: node ids sau `build_graph`, route supervisor, reducers state.
- Adapt test memory/stream khi đổi import.
- Phase 6: ít nhất 1 test contract `token` / `complete` / `node` / `error`.
- Mock chỉ ở boundary LLM/DB.

## Open risks

- FE đang parse `node_id` / `__answer__` — phase 6 phải đồng bộ hoặc feature-flag ngắn.
- Test import sâu `vms.graph` — phase 7 sửa cùng lúc xóa.
- Tránh phình phase 3–5 bằng cách ReAct hóa worker sớm (cấm trong v16).

## Acceptance (v16 done khi)

- [x] Root `domain.agents.graph` là graph thật (không shim) — `vms.graph` shim ngược.
- [x] `analytics` và `knowledge` là subgraph compile riêng.
- [x] Multi qua `top_supervisor` + `orchestrator_collect`; SQL repair trong analytics. (`synth_node` còn stub; answer vẫn `respond`).
- [x] `AgentTurnService.process` dùng cho `/api/chat` + `/ask`; stream qua `main.run_agent_stream` + `complete` (chart/persist giữ ở router).
- [x] SSE `complete`/`node`/`token` + FE bridge legacy.
- [x] Xóa re-export thừa (`sql_agent`/`docs_agent` graph+state); `vms/nodes` giữ impl thật; `pytest tests/test_v16_*.py` xanh.
