# v13 — Nested `trace_step` toàn graph LangGraph (design)

**Trạng thái:** Implemented (2026-11-05) — code + AC-T1/T2; manual Langfuse §4.2 tùy môi trường.  
**Quyết định:** Mức **B** (span con cho cả bước tính toán thuần) + cách **1** (bọc trong thân node, không decorator helper).

---

## 1. Mục tiêu

Mọi node trên graph `domain/agents` có cây observation Langfuse **đồng độ** với nhánh SQL hiện tại: span ngoài từ `_wrap_node`, span con `trace_step(current_span(), …)` cho từng khối logic bên trong node.

**Không đổi:** hành vi nghiệp vụ, API, SSE event shape, tên node graph.

**Phạm vi ngoài:** `store_extract` (chạy ngoài graph sau lượt) — giữ một span như hiện tại.

---

## 2. Quy ước kỹ thuật

| Hạng mục | Quy tắc |
|----------|---------|
| Parent span | `_wrap_node` set `_current` → `current_span()` trong node |
| Gọi | `with trace_step(current_span(), "<tên>", input={...}, as_type="tool") as sub:` |
| `as_type` | Mặc định `"tool"` cho substeps; LLM qua `invoke_text` / `invoke_structured` giữ `generation` (substep trong client), **không** bọc thêm span trùng tên |
| Input/output | Ghi metadata ngắn (`ok`, `skipped`, `count`, `len`, `error` rút gọn); không log password/SQL đầy đủ nếu đã redact ở layer khác |
| Lỗi | Exception ném ra như hiện tại; batch SQL ghi `error` per item, không nuốt lỗi cả node |
| Helper | **Không** tự trace trong `context.py`, `rewrite.py`, `guardrails.py` — chỉ tại node caller |

---

## 3. Bản đồ span con (theo node graph)

Node đã có substeps đủ (chỉ bổ sung nếu thiếu): `retrieve_schema`, `generate_sql`, `validate_sql`, `repair_sql`, `execute_sql` (single), `retrieve_docs`, `render_chart` (`render_png`), `respond` (`simple_answer`, `respond_stat`).

| Node graph | Span con (tên `trace_step`) | Ghi chú |
|------------|----------------------------|---------|
| `guardrail_input` | `check_input`, `redact_pii` | |
| `recall` | `recall_long_term` | Kể cả nhánh disabled → output `disabled: true` |
| `rewrite` | `sliding_window`, `compact_history`, `rewrite_question` | `compact_history` chỉ khi `should_compact`; `rewrite_question` bọc cả passthrough + LLM |
| `classify` | `classify_intent` | Bọc `classify_intent_safe` / sanitize |
| `respond_inline` | `inline_response` | |
| `orchestrator` | **một trong:** `plan_passthrough`, `plan_orchestration`, `dispatch_batch` | Đúng nhánh thực thi |
| `orchestrator_collect` | `collect_step` | |
| `execute_sql` | batch: lặp `apply_org_scope`, `revalidate_sql`, `postgres_query` **per** sub_question | Giống single-query |
| `answer_from_docs` | `compress_docs` | Chỉ khi nén answer |
| `respond` | `respond_inline`, `respond_out_of_scope`, `synthesize_multi` | Nhánh tương ứng; giữ substeps LLM hiện có |
| `guardrail_output` | `build_evidence`, `check_output` | |

**Không trên graph:** `guardrail_scope`, `guardrail_redact` (dead wiring).

---

## 4. Kiểm thử

### 4.1 Tự động (pytest)

File chính: `tests/test_product_observability_errors.py`.

- **AC-T1:** Monkeypatch `trace_step` ghi lại `(name, as_type)` — gọi node `rewrite_node` / `recall_node` / `guardrail_input_node` với state tối thiểu → assert đủ tên span trong bảng §3.
- **AC-T2:** `execute_sql_node` với `sql_batch` ≥2 → assert ≥2 lần `postgres_query` (hoặc tương đương) trong log mock.
- **AC-T3:** Regression: `PYTHONPATH=. pytest tests/test_product_observability_errors.py -q` pass; không đổi test hành vi graph (mock LLM/DB như cũ).

### 4.2 Manual (Langfuse)

- `MONITORING_ENABLED=true`, stack `langfuse/` + backend dong.
- Một câu stat + một câu follow-up → trace `chat` có cây: node `rewrite` → `sliding_window`, `rewrite_question`; node `recall` → `recall_long_term`; SQL giữ substeps cũ.

---

## 5. SDD — file cập nhật khi implement

| File | Việc |
|------|------|
| `specs/implementation-plan.md` | Checkbox phase v13 |
| `specs/test-plan.md` | Mục observability nested trace |
| `specs/product-spec.md` | AC-9 |
| `specs/change-log.md` | Block ngày merge code |
| `specs/README.md` | Trạng thái v13 |

---

## 6. Triển khai (gợi ý task — subagent-driven)

1. Guardrails + recall + rewrite + classify + respond_inline  
2. Orchestrator + orchestrator_collect  
3. execute_sql batch + answer_from_docs + respond branches + guardrail_output  
4. Tests AC-T1–T3 + manual checklist Langfuse  
5. Docs + change-log

**Done khi:** AC-9 + AC-T1–T3 + manual §4.2 pass.
