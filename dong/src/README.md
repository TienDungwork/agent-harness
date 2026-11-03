# `src/` — cấu trúc mã nguồn (agent dong)

Bản đồ ngắn, cùng phong cách [llm-engineer-demo/app](https://github.com/hungluu-lingolab/llm-engineer-demo): **một entry FastAPI**, package theo trách nhiệm, LangGraph chỉ orchestrate luồng.

> Entry: `uvicorn src.main:app` (từ thư mục `agent-harness/dong/`). Cấu hình: `src/config.py` + `.env`.

## Tổng quan

```
src/
├── main.py              # FastAPI app: mount routers, CORS, static UI, re-export test hooks
├── api/                 # Routers + helpers (errors, SSE, cache, session, schemas)
├── config.py            # Settings (env duy nhất)
├── guardrails.py        # check_input, in_scope, PII, output (dùng graph + HTTP sớm)
├── feedback.py          # Human feedback API
├── agent/               # LangGraph pipeline + Text-to-SQL + orchestrator (xem bên dưới)
├── db/                  # Postgres read-only: catalog, validate, execute
├── llm/                 # LiteLLM client, structured output, schemas
├── memory/              # TTL cache, long-term recall, checkpointer, context compaction
├── knowledge/           # RAG cards AIOC/VMS (YAML)
├── chart/               # Matplotlib PNG + should_render_chart heuristic
├── prompts/             # Registry YAML (classify, sql_agent, rewrite, …)
├── monitoring/          # Langfuse tracing substeps
└── sessions/            # Chat session store (Postgres / fallback)
```

## `agent/` — LangGraph

Sơ đồ live: `graph.mmd`, `graph.png` (repo root). **`graph.py`** (~90 dòng) chỉ facade + re-export (giống `llm-engineer-demo/app/agent/graph.py`).

| File | Vai trò |
|------|---------|
| `graph.py` | Facade: import wiring, nodes, `run_agent` / `run_agent_stream` |
| `state.py` | `Agent_Input`, `Agent_Output`, `AgentState` |
| `graph_runtime.py` | SSE `_stream_queue`, `_wrap_node`, `emit_answer_chunks` |
| `graph_wiring.py` | `_build_graph`, `_get_graph`, `reset_graph` |
| `graph_run.py` | `run_agent`, `run_agent_stream`, `_fresh_invoke_state` |
| `graph_helpers.py` | Prompt helpers (memory block, strip thinking, …) |
| `nodes_memory.py` | `recall_node`, `run_store_extract`, `extract_memory_node` |
| `nodes_rewrite_classify.py` | rewrite, classify, respond_inline |
| `nodes_orchestrator_core.py` | orchestrator node + routing |
| `nodes_orchestrator_synth.py` | multi-hop collect + synthesis helpers |
| `nodes_pipeline.py` | docs, schema, `render_chart_node` |
| `nodes_respond.py` | `respond_node` |
| `guardrail_nodes.py` | `guardrail_input`, `guardrail_scope`, `guardrail_redact`, `guardrail_output` |
| `rewrite.py` | Chuẩn hóa câu hỏi, `sub_questions` |
| `intent.py` | Classify 7 intent + `chart_requested` (clamp heuristic) |
| `orchestrator.py` | Multi-hop plan: cross-DB, all-events, rewrite sub-questions |
| `sql_batch.py` | Gom sub-question cùng `query_data` → nhiều SQL, execute batch |
| `retrieve_schema` (trong graph) | `select_relevant_tables` + schema excerpt |
| `generate_sql.py` | LLM/offline text-to-SQL, batch |
| `validate_sql.py` | Validator + `repair_sql_node` |
| `execute_sql.py` | Chạy SQL / batch |
| `pre_sql.py` | time_range, chart hint, `get_time_column_for_table` |
| `sql_scope.py` | `organization_id` scope |
| `simple_answer.py` | Template trả lời COUNT đơn giản |
| `inline_respond.py` | Chat / clarify / out_of_scope inline |
| `docs.py` | Adapter → `knowledge` |
| `chart_fallback.py` | Retry query khi chart thiếu điểm |
| `camera_registry.py` | Master data 10 camera AIOC |
| `node_io.py` | `node_event` cho SSE + Langfuse |

Luồng rút gọn:

```text
guardrail_input → recall → rewrite → classify → orchestrator
  → query_data: retrieve_schema → generate_sql → validate → execute → [render_chart?] → respond
  → docs: retrieve_docs → answer_from_docs → respond
  → inline: respond_inline → respond
→ guardrail_output → END
```

Multi-hop: `orchestrator` ⇄ pipeline ⇄ `orchestrator_collect` → `respond`.

## Package khác

| Package | Ghi chú |
|---------|---------|
| `db/` | `catalog.yaml` ở `resource/db/`; validator cột/bảng whitelist |
| `memory/` | Hit TTL → recall long-term → context window trước agent |
| `knowledge/` | Task cards published; không gọi DB |
| `llm/` | `use_offline_tools()` cho pytest |
| `prompts/` | `resource/prompts/<name>/vN.yaml` + `production.txt` |

## Quy ước sửa code

- Logic domain: class thuần; config/DTO: `@dataclass` (xem `code-discipline`).
- Node graph: một hàm `*_node(state) -> dict` mỗi file khi có thể; không nhét business vào `main.py`.
- Thay đổi pipeline: cập nhật `graph.mmd` + spec (`specs/product-spec.md`, `change-log.md`).
