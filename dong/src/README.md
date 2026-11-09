# `src/` — layout (vn-stock `ai_backend` style)

Entry: `uvicorn src.main:app` từ `agent-harness/dong/`. Cấu hình: `src/shared/settings/` (shim `shared.config`) + `.env`.

**Agent Postgres (bắt buộc khi `MEMORY_ENABLED=true`):** `DB_NAME_AGENT` — `chat_sessions`, `chat_session_messages`, `human_feedback` + LangGraph `PostgresSaver.setup()`. Long-term facts → Qdrant. **API_ACCESS_KEY** (tùy chọn): header `X-API-Key`.

```
src/
├── main.py
├── api/
├── application/            # use-cases mỏng (agent_turn)
├── domain/
│   ├── agents/
│   │   ├── vms/            # graph.py (máy chạy flat) + state + nodes + tools
│   │   ├── sql_agent/      # leaf: graph re-export nodes, tools SQL (no compile)
│   │   ├── docs_agent/     # leaf: docs/camera tools + nodes
│   │   ├── multi_agent/    # orchestrator plan / core / synth
│   │   ├── graph.py        # shim → vms.graph
│   │   └── state.py        # shim → vms.state
│   └── knowledge/
├── infra/
└── shared/
    ├── settings/
    └── config.py           # shim → settings
```

## `domain/agents/`

| Package | Nội dung |
|---------|----------|
| `vms/graph.py` | Build + run + stream + wrap (gộp core cũ) |
| `vms/nodes/` | guardrail, memory, rewrite/intent, respond, render_chart |
| `vms/tools.py` + `stream.py` | helpers + SSE queue |
| `sql_agent/` | retrieve_schema + generate/validate/execute… |
| `docs_agent/` | retrieve_docs / answer_from_docs + adapters |
| `multi_agent/` | multi-hop orchestrator |

Luồng (flat): `guardrail_input → recall → rewrite → classify → orchestrator → … → respond → guardrail_output`.

## Quy ước import

- Canonical: `src.domain.agents.vms.*`, `sql_agent.*`, `docs_agent.*`, `multi_agent.*`
- Application: `src.application.agent_turn`
- Shared: `src.shared.settings` (hoặc shim `src.shared.config`)
