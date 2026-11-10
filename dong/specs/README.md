# Specs — agent dong

Chỉ mục tài liệu Spec-Driven Development (SDD). Cấu trúc theo [sdd-guide-vi.md](sdd-guide-vi.md).

## Bắt đầu (core SDD)

1. [sdd-guide-vi.md](sdd-guide-vi.md) — quy trình SDD + prompt Cursor
2. [superpowers-workflow-vi.md](superpowers-workflow-vi.md) — Superpowers + Ponytail + SDD
3. [product-spec.md](product-spec.md) — **hợp đồng** sản phẩm
4. [implementation-plan.md](implementation-plan.md) — task / phase
5. [test-plan.md](test-plan.md) — pytest + smoke
6. [change-log.md](change-log.md) — nhật ký thay đổi
7. [smoke-manual-checklist.md](smoke-manual-checklist.md) — demo tay
8. [../src/README.md](../src/README.md) — cấu trúc mã nguồn

## Design còn tham chiếu

| File | Nội dung |
|------|----------|
| [v15-leaf-agents-flat-graph-design.md](v15-leaf-agents-flat-graph-design.md) | v15 leaf `sql_agent`/`docs_agent` + flat graph |
| [v14-ai-backend-layout-design.md](v14-ai-backend-layout-design.md) | v14 align layout `ai_backend` |

## Archive

Phase plans/designs đã đóng (v13–v17), SDD full, change-log cũ: [archive/](archive/).

## Quy ước cập nhật

- Thay đổi hành vi / API / AC → sửa `product-spec.md` (hoặc mục change-log nếu chỉ fix nhỏ).
- Mỗi feature/fix merge-worthy → một block `## YYYY-MM-DD` ở **đầu** `change-log.md`.
- Task mới → thêm vào `implementation-plan.md` trước khi code.
