# `src/` — layout (v16 hierarchical + v18 RBAC)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/settings.py` + `.env`.

**Agent Postgres (bắt buộc khi `MEMORY_ENABLED=true`):** `DB_NAME_AGENT` — sessions/feedback + LangGraph checkpointer. Long-term → Qdrant. **API_ACCESS_KEY** (tùy chọn): header `X-API-Key`.

```
src/
├── main.py
├── api/
│   ├── routers/
│   │   ├── agent/               # /api/agent/stream
│   │   └── web_backend/         # sessions, memory, meta, feedback
│   ├── helpers/
│   └── models/
├── application/                 # AgentTurnService
├── domain/
│   ├── agents/
│   │   ├── graph.py             # wiring + invoke/stream + context= (như vn-stock)
│   │   ├── state.py
│   │   ├── nodes/
│   │   ├── analytics/           # SQL team + sql_agent/tools
│   │   └── knowledge/           # docs team
│   │       ├── graph.py
│   │       ├── docs_agent/      # nodes + camera/docs adapters
│   │       └── retrieval/       # corpus YAML: loader / retrieve / answer
│   ├── authz/
│   ├── guardrails/              # injection / pii / checks
│   └── observability/           # tracing / redaction / feedback
├── infra/
└── shared/
    └── settings.py              # Settings / get_settings / settings
```

## Quy ước import

- Settings: `from src.shared.settings import settings`
- Guardrails: `src.domain.guardrails`
- Observability: `src.domain.observability.tracing` (gồm `slim_state`/`llm_io_payload`) / `.feedback`
- SQL: `src.domain.agents.analytics.sql_agent.tools.*`
- Docs corpus: `src.domain.agents.knowledge.retrieval.*`
- Docs team: `src.domain.agents.knowledge.docs_agent.*`

Luồng: `guardrail → recall → rewrite → classify → top_supervisor ⇄ analytics_team|knowledge_team → respond`.

## Current state

- `infra/llm/`: tách như demo — `backends`, `resilience`, `client` (factory sync), `completion`, `async_client`, `params` (`DETERMINISTIC`/`BALANCED`/`CREATIVE`).
- `routes_agent.py`: chỉ `/api/agent/stream` (đã bỏ `/api/chat` + `/ask`); `check_input` + `redact_pii` trước graph; logic ở `AgentTurnService`.
- `domain/agents/graph.py`: như vn-stock — bare nodes + `invoke`/`stream` với `context={trace_span, access_context, ...}`; bỏ `node_wrap` / custom invoke queue.
- `infra/prompts/`: git YAML registry + `lint` + `experiment` (như demo/vn-stock); `production.txt` chỉ alias version.
- Đã xóa shim `shared.config` / `shared.feedback` / `shared.guardrails`; settings nằm ở `shared/settings.py`.
