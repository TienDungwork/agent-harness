# `src/` — layout (vn-stock `ai_backend` style)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/config.py` + `.env`.

**Agent Postgres (bắt buộc khi `MEMORY_ENABLED=true`):** `DB_NAME_AGENT` — `chat_sessions`, `chat_session_messages`, `human_feedback` + LangGraph `PostgresSaver.setup()`. Long-term facts → Qdrant. **API_ACCESS_KEY** (tùy chọn): header `X-API-Key`.

```
src/
├── main.py                 # FastAPI entry
├── api/
│   ├── routers/            # routes_meta, sessions, memory, feedback, agent
│   ├── models/             # Pydantic schemas
│   └── helpers/            # errors, cache, SSE, session
├── domain/
│   ├── agents/             # LangGraph VMS agent (graph facade + nodes)
│   └── knowledge/          # RAG cards AIOC/VMS
├── infra/
│   ├── db/                 # Postgres read-only, catalog, validator
│   ├── memory/             # TTL, long-term, context, checkpointer
│   ├── llm/                # LiteLLM client, schemas
│   ├── chart/              # Matplotlib render
│   ├── monitoring/         # Langfuse tracing
│   ├── prompts/            # YAML registry
│   └── session/            # Chat session store
└── shared/
    ├── config.py
    ├── guardrails.py
    └── feedback.py
```

## `domain/agents/` (giống vn-stock: graph + state ở root, package con)

| Package | Nội dung |
|---------|----------|
| `graph.py`, `state.py` | Entry + state (như `ai_backend/domain/agents/graph.py`) |
| `core/` | wiring, run, runtime, helpers |
| `nodes/` | memory, rewrite/classify, pipeline, respond, guardrails, io |
| `orchestrator/` | plan, core node, synth/collect |
| `sql/` | generate, validate, execute, batch |
| `routing/` | intent, rewrite, inline_respond |
| `respond/` | simple_answer, chart_fallback |
| `adapters/` | docs, camera_registry |

Luồng: `guardrail_input → recall → rewrite → classify → orchestrator → … → respond → guardrail_output`.

## Quy ước import

- Domain: `src.domain.agents.*`, `src.domain.knowledge.*`
- Infra: `src.infra.db.*`, `src.infra.memory.*`, …
- Shared: `src.shared.config`, `src.shared.guardrails`
