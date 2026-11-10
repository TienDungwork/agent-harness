# `src/` — layout (v16 hierarchical + v18 RBAC)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/settings/` (shim `shared.config`) + `.env`.

**Agent Postgres (bắt buộc khi `MEMORY_ENABLED=true`):** `DB_NAME_AGENT` — sessions/feedback + LangGraph checkpointer. Long-term → Qdrant. **API_ACCESS_KEY** (tùy chọn): header `X-API-Key`.

```
src/
├── main.py
├── api/
│   ├── routers/
│   │   ├── agent/               # /api/chat, /ask, /api/agent/stream
│   │   └── web_backend/         # sessions, memory, meta, feedback
│   ├── helpers/
│   └── models/
├── application/                 # AgentTurnService
├── domain/
│   ├── agents/
│   │   ├── graph.py             # root build/run/stream
│   │   ├── state.py
│   │   ├── nodes/
│   │   ├── analytics/           # SQL team + sql_agent/tools
│   │   └── knowledge/           # docs team
│   │       ├── graph.py
│   │       ├── docs_agent/      # nodes + camera/docs adapters
│   │       └── retrieval/       # corpus YAML: loader / retrieve / answer
│   └── authz/
├── infra/
└── shared/
```

## Quy ước import

- SQL: `src.domain.agents.analytics.sql_agent.tools.*`
- Docs corpus: `src.domain.agents.knowledge.retrieval.*`
- Docs team: `src.domain.agents.knowledge.docs_agent.*`

Luồng: `guardrail → recall → rewrite → classify → top_supervisor ⇄ analytics_team|knowledge_team → respond`.

## Current state

- `infra/llm/params.py`: `GenerationParams` + preset `DETERMINISTIC` (SQL/structured, temp=0), `TASK` (`LLM_TEMPERATURE`), `RESPOND` (`LLM_RESPOND_TEMPERATURE`, mặc định 0.7).
