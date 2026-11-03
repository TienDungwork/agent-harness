# Specs — agent dong

Chỉ mục tài liệu Spec-Driven Development (SDD), tương tự cách [llm-engineer-demo](https://github.com/hungluu-lingolab/llm-engineer-demo) tách README module + README gốc ngắn.

## Bắt đầu

1. [sdd-guide-vi.md](sdd-guide-vi.md) — quy trình SDD + prompt Cursor
2. [superpowers-workflow-vi.md](superpowers-workflow-vi.md) — Superpowers + Ponytail + SDD
3. [product-spec.md](product-spec.md) — **hợp đồng** sản phẩm hiện tại (v9 Memory)
4. [implementation-plan.md](implementation-plan.md) — task còn lại / lịch sử phase
5. [test-plan.md](test-plan.md) — pytest + smoke
6. [change-log.md](change-log.md) — thay đổi gần đây
7. [../src/README.md](../src/README.md) — cấu trúc mã nguồn

## Trạng thái hiện tại (tóm tắt)

| Hạng mục | Trạng thái |
|----------|------------|
| Memory v9 (Postgres + TTL + context) | Hoàn thành — implementation-plan Phase 1–7 |
| **v10 Cấu trúc `src/` (API + graph modules)** | Hoàn thành — `src/api/`, `graph.py` facade |
| LangGraph multi-hop + batch SQL | Triển khai — change-log 2026-09-25 |
| Golden eval | `eval/datasets/agent_stat/v2.yaml` |
| Graph live | `graph.mmd`, `graph.png` (repo root) |

## Archive

| File | Nội dung |
|------|----------|
| [archive/sdd-guide-vi-full.md](archive/sdd-guide-vi-full.md) | Hướng dẫn SDD + prompt dài (675 dòng) |
| [archive/change-log-through-2026-09-29.md](archive/change-log-through-2026-09-29.md) | Change log cũ (trước khi rút gọn) |
| [archive/v7-chart-ui-audit.md](archive/v7-chart-ui-audit.md) | Audit UI chart v7 |
| [archive/v7-dead-code-inventory.md](archive/v7-dead-code-inventory.md) | Dead code inventory v7 |

## Quy ước cập nhật

- Thay đổi hành vi / API / AC → sửa `product-spec.md` (hoặc mục change-log nếu chỉ fix nhỏ).
- Mỗi feature/fix merge-worthy → một block `## YYYY-MM-DD` ở **đầu** `change-log.md`.
- Task mới → thêm vào `implementation-plan.md` trước khi code.
