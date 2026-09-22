# Product Spec — agent dong v5 (MVP)

**Trạng thái:** Phase 1–**7** (demo setup) xong; Đã đạt trạng thái demo-ready. Kế thừa v4 (guardrail, Langfuse, Docker).

## App goal

Trợ lý tiếng Việt cho VMS KCN Hưng Phú — **một codebase `src/`**, triển khai **chỉ qua Docker Compose**.

1. Trả **số liệu** từ DB read-only — truy vấn **linh hoạt theo schema**, không gói cứng từng tool một.
2. Trả **hướng dẫn VMS** theo cách **duy** (YAML card retrieval + trả lời bám nguồn).
3. **Vẽ biểu đồ** khi user hỏi số liệu (PNG base64 sau truy vấn).
4. UI: **live graph** SSE — node lần lượt, hover/click → input/output.
5. (Tuỳ chọn) Langfuse trace.

**Phong cách code:** học `llm-engineer-demo` — module mỏng, config một chỗ, **structured output bắt buộc** mọi lần gọi LLM.

## Target users

- Vận hành KCN: hỏi tiếng Việt, không viết SQL.
- Reviewer: graph + Langfuse + `eval/results/golden-30.md`.

## Core user flow

1. User gửi câu tiếng Việt qua UI (`POST /api/agent/stream`).
2. **Guardrail** injection / out-of-scope.
3. **`rewrite`** — LLM chuẩn hóa câu hỏi (structured) để tăng độ chính xác truy vấn.
4. **`classify_intent`** — structured → `query_data` | `how_to` | `troubleshoot` | `concept` | `out_of_scope`.
5. Nhánh:
   - **Số liệu:** inject **DB schema excerpt** vào prompt → LLM trả **`QueryPlan`** (structured) → builder SQL parameterized + validator read-only → execute → optional **chart** → **`respond`** (structured summary + câu trả lời VI).
   - **Docs:** retrieve YAML cards (duy) → **`answer_from_docs`** (structured).
   - **Khác:** từ chối một câu.
6. SSE emit từng node; UI graph + (nếu có) hiển thị chart.

## Structured output (bắt buộc)

Mọi lần gọi LLM phải trả **Pydantic schema** (OpenAI-compatible `response_format` / parse API). Không parse JSON thủ công từ free text (trừ fallback no-op khi monitoring tắt).

| Bước | Schema (ví dụ) |
|------|----------------|
| Rewrite | `RewrittenQuestion { text, filters[], time_range?, intent_hint? }` |
| Classify | `IntentResult { intent, reason }` |
| Query plan | `QueryPlan { tables[], selects[], filters[], group_by[], order_by?, limit? }` |
| Docs answer | `DocsAnswer { answer_vi, card_ids[], steps[]? }` |
| Respond số liệu | `StatAnswer { answer_vi, highlights[], chart_requested: bool }` |
| Chart (nếu LLM chọn kiểu) | `ChartSpec { chart_type, x_column, y_column, title_vi }` |

Judge eval: structured rubric 1–5 (giống demo).

## DB — linh hoạt nhưng an toàn

- **Không** giữ 9 tool cố định làm đường chính v5.
- **Có:** catalog dataset + **`describe_table`** (columns, sample values) → đưa vào prompt.
- LLM chỉ sinh **`QueryPlan`** (structured), không sinh SQL thô trực tiếp cho user.
- **`query_builder`** Python: plan → SQL `%s` parameterized; whitelist table/column từ schema excerpt.
- **`validate_sql`:** SELECT-only, chặn DML/DDL (port logic duy, đơn giản hóa).
- Postgres read-only 5 DB + ClickHouse tuỳ chọn (giữ v4).
- Repair loop tối đa `SQL_REPAIR_MAX` (mặc định 1) nếu validate/execute lỗi.

## Docs — theo duy

- Nguồn: YAML cards `VMS_doc` (index + card `how_to|troubleshoot|concept`).
- Loader + keyword retrieval (port tối thiểu từ `agent-harness/duy`).
- Không grep markdown thô `docs/vms/*.md` làm đường chính.

## Chart

- Sau execute: nếu user hỏi biểu đồ / `StatAnswer.chart_requested` → node **`render_chart`**.
- Matplotlib Agg → PNG base64; SSE event `{ node_id: "render_chart", chart_png_base64, chart_meta }`.
- FE hiển thị `<img>` dưới câu trả lời (MVP).

## Graph agent (LangGraph)

```
START → rewrite → classify → [route]
  query_data → retrieve_schema → plan_query → validate → execute → [render_chart] → respond → END
  how_to|troubleshoot|concept → retrieve_docs → answer_from_docs → END
  out_of_scope → END
```

ReAct loop v4 **thay thế** bằng pipeline trên (đơn giản hơn, dễ trace từng node).

## Deploy & repo

- **Chỉ Docker Compose** cho deploy/demo (`docker-compose.yml` + `langfuse/docker-compose.yml`).
- README không hướng dẫn `.venv` là đường chính; dev local uvicorn **tuỳ chọn** cho contributor.
- Dọn code thừa: `ai/`, script one-off không dùng, dead import — **đã xóa ở Phase 7**.

## Features in scope (v5 MVP)

- Structured output layer (`src/llm/structured.py` hoặc tương đương).
- Node **`rewrite`**.
- Schema-aware **QueryPlan** + builder + validator.
- Docs YAML (duy).
- Chart PNG.
- Giữ: guardrail, cache TTL, Langfuse, SSE graph UI, eval golden-30.
- `tests/` **< 10 file**.

## Out of scope (v5)

- Text-to-SQL tự do không qua QueryPlan/validator.
- Web search, multi-agent, MCP, ghi DB.
- Graph editor kéo-thả, semantic cache.
- ApexCharts phức tạp (chỉ PNG MVP).

## Acceptance criteria

1. `docker compose up --build -d` (+ Langfuse tuỳ chọn) → UI + API healthy.
2. Mọi LLM call trong graph dùng structured schema; pytest mock schema parse.
3. Câu số liệu: schema trong prompt; thêm filter (vd. `vehicle_type`) → query phản ánh đúng cột.
4. Câu how-to: trả lời bám card YAML; không gọi DB.
5. Câu “vẽ biểu đồ …” → PNG hiển thị trên UI.
6. Node `rewrite` xuất hiện trên graph SSE.
7. Read-only DB enforced; `DELETE` bị chặn.
8. Langfuse trace per request (stream path).
9. `pytest -q` xanh offline; golden-30 chạy live ghi `eval/results/golden-30.md`.
