# Specs — agent dong

Chỉ mục tài liệu Spec-Driven Development (SDD), tương tự cách [llm-engineer-demo](https://github.com/hungluu-lingolab/llm-engineer-demo) tách README module + README gốc ngắn.

## Bắt đầu (core SDD)

1. [sdd-guide-vi.md](sdd-guide-vi.md) — quy trình SDD + prompt Cursor
2. [superpowers-workflow-vi.md](superpowers-workflow-vi.md) — Superpowers + Ponytail + SDD
3. [product-spec.md](product-spec.md) — **hợp đồng** sản phẩm
4. [implementation-plan.md](implementation-plan.md) — task / phase
5. [test-plan.md](test-plan.md) — pytest + smoke
6. [change-log.md](change-log.md) — thay đổi gần đây
7. [smoke-manual-checklist.md](smoke-manual-checklist.md) — demo tay
8. [../src/README.md](../src/README.md) — cấu trúc mã nguồn

## Design / phase đang mở

| File | Nội dung |
|------|----------|
| [v16-hierarchical-agents-design.md](v16-hierarchical-agents-design.md) | **v16** — hierarchical `analytics_team` \| `knowledge_team` + `AgentTurnService` (supersede flat-only v15) |
| [v16-hierarchical-agents-plan.md](v16-hierarchical-agents-plan.md) | **v16** — implementation plan (Tasks 1–7) |
| [v15-leaf-agents-flat-graph-design.md](v15-leaf-agents-flat-graph-design.md) | **v15** — leaf `sql_agent`/`docs_agent` + flat `vms/graph.py` (baseline cho v16) |
| [v15-leaf-agents-flat-graph-plan.md](v15-leaf-agents-flat-graph-plan.md) | **v15** — implementation plan (tasks 1–6) |
| [v14-ai-backend-layout-design.md](v14-ai-backend-layout-design.md) | **v14** — align layout với `ai_backend` (`vms` + `multi_agent`) |

## Trạng thái hiện tại (tóm tắt)

| Hạng mục | Trạng thái |
|----------|------------|
| Memory v9 (Postgres + TTL + context) | Hoàn thành — implementation-plan Phase 1–7 |
| **v10 Cấu trúc `src/` (API + graph modules)** | Hoàn thành — `src/api/`, graph facade |
| **v13 Nested Langfuse `trace_step` toàn graph** | Code + tests — design trong `archive/` |
| **v14 Align `src/` ↔ `ai_backend`** | **14.1–14.4 done** — `vms/` + `multi_agent/` + `application/` + `shared/settings`; 14.5 optional |
| **v15 Leaf agents + flat graph** | **15.1–15.5 done** — `sql_agent` / `docs_agent` + flat `vms/graph.py`; AC-11 subset 17 passed |
| **v16 Hierarchical teams** | **done (finish)** — teams + service + xóa re-export junk; `vms/nodes` = impl |
| LangGraph multi-hop + batch SQL | Triển khai |
| Golden eval | `eval/datasets/agent_stat/v2.yaml` |

## Archive

| File | Nội dung |
|------|----------|
| [archive/sdd-guide-vi-full.md](archive/sdd-guide-vi-full.md) | Hướng dẫn SDD + prompt dài |
| [archive/change-log-through-2026-09-29.md](archive/change-log-through-2026-09-29.md) | Change log cũ |
| [archive/v7-chart-ui-audit.md](archive/v7-chart-ui-audit.md) | Audit UI chart v7 |
| [archive/v7-dead-code-inventory.md](archive/v7-dead-code-inventory.md) | Dead code inventory v7 |
| [archive/nested-trace-v13-design.md](archive/nested-trace-v13-design.md) | Design nested Langfuse v13 |

## Quy ước cập nhật

- Thay đổi hành vi / API / AC → sửa `product-spec.md` (hoặc mục change-log nếu chỉ fix nhỏ).
- Mỗi feature/fix merge-worthy → một block `## YYYY-MM-DD` ở **đầu** `change-log.md`.
- Task mới → thêm vào `implementation-plan.md` trước khi code.
