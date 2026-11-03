# `src/` — layout (vn-stock `ai_backend` style)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/config.py` + `.env`.

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

## `domain/agents/`

`graph.py` (~90 dòng) facade; chi tiết: `graph_wiring.py`, `graph_run.py`, `nodes_*.py`, `state.py`.

Luồng rút gọn: `guardrail_input → recall → rewrite → classify → orchestrator → … → respond → guardrail_output`.

## Quy ước import

- Domain: `src.domain.agents.*`, `src.domain.knowledge.*`
- Infra: `src.infra.db.*`, `src.infra.memory.*`, …
- Shared: `src.shared.config`, `src.shared.guardrails`
