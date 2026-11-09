# `src/` — layout (v16 hierarchical, swarm-style)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/settings/` (shim `shared.config`) + `.env`.

**Agent Postgres (bắt buộc khi `MEMORY_ENABLED=true`):** `DB_NAME_AGENT` — sessions/feedback + LangGraph checkpointer. Long-term → Qdrant. **API_ACCESS_KEY** (tùy chọn): header `X-API-Key`.

```
src/
├── main.py
├── api/
├── application/                 # AgentTurnService
├── domain/
│   ├── agents/
│   │   ├── graph.py             # root build/run/stream
│   │   ├── state.py             # AssistantState + AgentState
│   │   ├── nodes/               # top_supervisor + prefix nodes
│   │   ├── stream.py / tools.py # SSE queue + helpers
│   │   ├── analytics/           # SQL team subgraph + sql_agent/
│   │   └── knowledge/           # docs team subgraph + docs_agent/
│   └── knowledge/               # RAG corpus (infra-facing)
├── infra/
└── shared/
```

## `domain/agents/`

| Path | Vai trò |
|------|---------|
| `graph.py` | Root compile + `run_agent` / `start_graph` |
| `state.py` | `AssistantState` / `AgentState` / I/O |
| `nodes/` | Supervisor (`top_supervisor`), plan/synth, guardrail/rewrite/respond… |
| `analytics/` | `build_analytics_graph` + `sql_agent/tools` |
| `knowledge/` | `build_knowledge_graph` + `docs_agent` |

Luồng: `guardrail → recall → rewrite → classify → top_supervisor ⇄ analytics_team|knowledge_team → respond → guardrail_output`.

## Quy ước import

- Canonical: `src.domain.agents.graph`, `src.domain.agents.state`, `src.domain.agents.nodes.*`
- SQL: `src.domain.agents.analytics.sql_agent.tools.*`
- Docs: `src.domain.agents.knowledge.docs_agent.*`
