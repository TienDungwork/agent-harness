# Spec-Driven Development — agent dong

Quy trình làm việc với **Cursor Agent** trên repo này. Chi tiết prompt từng bước (nếu cần): [archive/sdd-guide-vi-full.md](archive/sdd-guide-vi-full.md).

## Nguyên tắc

1. Viết/ cập nhật spec trước, code theo từng task nhỏ trong `implementation-plan.md`.
2. Không nhờ agent build cả app một lần.
3. Sau mỗi thay đổi có ý nghĩa: ghi `change-log.md` (mục mới ở trên cùng).
4. Spec là hợp đồng; `change-log` là bộ nhớ; README là cách chạy.

## Cấu trúc `specs/`

| File | Vai trò |
|------|---------|
| [superpowers-workflow-vi.md](superpowers-workflow-vi.md) | Superpowers + Ponytail + SDD |
| [product-spec.md](product-spec.md) | Mục tiêu, user, flow, AC |
| [implementation-plan.md](implementation-plan.md) | Task triển khai (checkbox) |
| [test-plan.md](test-plan.md) | Test tự động + smoke manual |
| [change-log.md](change-log.md) | Nhật ký thay đổi (giữ gần đây) |
| [smoke-manual-checklist.md](smoke-manual-checklist.md) | Checklist demo tay |
| [../src/README.md](../src/README.md) | Bản đồ `src/` |
| [archive/](archive/) | SDD đầy đủ, change-log cũ, audit v7 |

Repo gốc: `README.md` (cài/chạy/test), `AGENTS.md` (quy tắc agent + Antigravity).

## Workflow ngắn

| Bước | Việc làm |
|------|----------|
| 1 | Đọc `product-spec.md` + task `[ ]` đầu tiên trong `implementation-plan.md` |
| 2 | Implement **một** task → test theo `test-plan.md` |
| 3 | Đánh dấu `[x]`, cập nhật `change-log.md` |
| 4 | Lặp; trước demo: smoke checklist + `pytest -q` |

## Prompt Cursor (copy-paste)

**Task tiếp theo**

```text
Read AGENTS.md and specs/.
Implement only the next unchecked task in specs/implementation-plan.md.
Keep the change small.
Update specs/change-log.md after implementation.
```

**Sửa bug**

```text
Read the relevant spec first.
Fix only this bug. Do not add unrelated features.
Update specs/change-log.md.
```

**Review vs spec**

```text
Review the feature against specs/product-spec.md and specs/test-plan.md.
Report pass / fail / missing. Fix only issues for this feature.
Update specs/change-log.md.
```

## Demo ngrok

Cài đặt và tunnel: xem **mục 6** trong [README.md](../README.md) hoặc `scripts/run_ngrok_demo.sh`.

## Superpowers + Ponytail

Chi tiết: **[superpowers-workflow-vi.md](superpowers-workflow-vi.md)**.

- **Superpowers:** brainstorming → plan → implement → verification → change-log.
- **Ponytail:** `/ponytail lite` khi implement; cài `./scripts/install-ponytail.sh` (repo root `KCNHungPhu`).

## Tham chiếu code

**[src/README.md](../src/README.md)** — bản đồ package (giống `app/` trong llm-engineer-demo).

| Khối | Thư mục |
|------|---------|
| LangGraph | `src/agent/` |
| Memory | `src/memory/` |
| SQL | `src/db/` + nodes SQL trong `src/agent/` |
| RAG | `src/knowledge/` |
| API | `src/main.py` + `src/api/` (routers) |

Mental model: bạn là product owner; agent là implementer; spec là hợp đồng.
