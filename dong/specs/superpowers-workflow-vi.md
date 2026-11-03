# Superpowers + SDD — workflow cho agent dong

Tích hợp [Superpowers](https://github.com/obra/superpowers) (Cursor plugin) với Spec-Driven Development của repo này. Tham chiếu code: [src/README.md](../src/README.md).

## Khi nào dùng skill nào

| Việc | Skill Superpowers | Spec dong |
|------|-------------------|-----------|
| Feature / refactor lớn | `brainstorming` → `writing-plans` | `product-spec.md`, `implementation-plan.md` |
| Implement từng task | `executing-plans` hoặc `subagent-driven-development` | Task `[ ]` trong implementation-plan |
| Sửa bug | `systematic-debugging` | `test-plan.md` + case liên quan |
| Xong task / trước merge | `verification-before-completion` | `pytest -q`, smoke checklist |
| Review | `requesting-code-review` | So `product-spec.md` + `test-plan.md` |
| Ghi nhận thay đổi | — | `change-log.md` (mục mới trên cùng) |

**Thứ tự:** skill quy trình trước → đọc spec → code nhỏ → verify → change-log.

## Vòng lặp chuẩn (một task trong implementation-plan)

1. **Đọc** `AGENTS.md`, task đầu tiên `[ ]` trong `implementation-plan.md`, AC trong `product-spec.md`.
2. **Brainstorm** (nếu scope/UX chưa rõ) — không code.
3. **Plan** — task đủ nhỏ; success = lệnh test cụ thể.
4. **Implement** — một task; Cursor code / Antigravity delegate theo `AGENTS.md`.
5. **Verify** — chạy pytest liên quan; không claim pass nếu chưa chạy.
6. **Review** — pass/fail/missing vs spec; chỉ sửa trong scope task.
7. **Ghi** `implementation-plan.md` `[x]` + `change-log.md`.

## Ponytail (code tối thiểu)

Cài workspace `KCNHungPhu`: `./scripts/install-ponytail.sh`

| Lệnh chat | Ý nghĩa |
|-----------|---------|
| `/ponytail` / `/ponytail lite` | Diff nhỏ, ít abstraction |
| `/ponytail full` | Review chặt hơn |
| `/ponytail off` | Tắt ruleset session |
| `/ponytail-review` | Review diff theo ponytail |

Dùng **cùng** SDD: ponytail không thay spec — vẫn cập nhật `change-log.md` sau thay đổi có nghĩa.

## Prompt mẫu (Superpowers + SDD)

**Task tiếp theo**

```text
Using superpowers: read specs/implementation-plan.md — implement only the next unchecked task.
Follow src/README.md layout. Verify with pytest. Update specs/change-log.md.
/ponytail lite
```

**Bug**

```text
Using superpowers:systematic-debugging — reproduce, then minimal fix.
Read relevant spec. Update specs/change-log.md.
```

**Review feature**

```text
Review against specs/product-spec.md and specs/test-plan.md.
Report pass/fail/missing. Fix only this feature. Update specs/change-log.md.
```

## Không làm

- Implement cả phase trong một lượt chat.
- Bỏ qua `change-log.md` khi đổi hành vi API/graph.
- Refactor rộng `src/agent/graph.py` không có task trong implementation-plan.
