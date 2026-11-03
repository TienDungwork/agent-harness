# v7 Dead-code inventory (Phase 1 — list only, **do not delete yet**)

Xóa / ngắt ở **Phase 3e** (sau khi text-to-SQL path mới pass pytest).  
Cập nhật lần cuối: Phase 1 project setup.

## A. Legacy ReAct — không wire vào graph production

| Path | Ghi chú |
|------|---------|
| `src/agent/tools.py` | Tool-calling ReAct; graph chỉ import `QueryResult` → tách model rồi xóa tools |
| `src/db/queries.py` | Parameterized queries cho tools ReAct; không dùng trên QueryPlan path |
| `src/agent/answer.py` | Answer layer ReAct (`agent_answer` prompt) |
| `resource/prompts/agent_system/` | System prompt ReAct |
| `resource/prompts/agent_answer/` | Prompt answer ReAct |

## B. Path sẽ thay ở Phase 3c — deprecate sau khi path mới xanh

| Path | Ghi chú |
|------|---------|
| `src/agent/query_plan.py` | Sinh QueryPlan JSON (path chính v6) |
| `src/db/query_builder.py` | QueryPlan → SQL parameterized |
| `resource/prompts/plan_query/` | Prompt kế hoạch QueryPlan |
| `resource/prompts/plan_query_repair/` | Prompt repair QueryPlan |

## C. Dead / stale trong graph & docs

| Path | Ghi chú |
|------|---------|
| `route_intent()` trong `src/agent/graph.py` | Định nghĩa nhưng không nối edge (orchestrator thay) |
| `graph.mmd` / `graph_diagram.html` (nếu có) | Sơ đồ lệch graph thật — cập nhật Phase 3e |
| `eval/datasets/agent_stat/v1.yaml` | Assert tool cũ (`count_vehicle_flow`) — ưu tiên v2 |

## D. Không xóa (vẫn cần v6/v7)

- `QueryResult` (sau khi tách khỏi `tools.py`)
- `src/db/validator.py`, `executor.py`, `catalog.py`, `connection.py`
- Memory, sessions, guardrails, frontend, Docker scripts
- Prompts: `classify`, `rewrite`, `respond_stat`, `plan_chart`, `orchestrator`, docs, …

## Quy tắc

1. **Chưa xóa** cho đến Phase 3e + `pytest -q` xanh trên path mới.  
2. Mỗi lần xóa: cập nhật import + tests + entry `specs/change-log.md`.
