# Infra MCP bridge (agent tools → local-gateway)

```bash
cd services/infra-mcp
uv run --with fastapi --with uvicorn --with httpx --with pydantic python main.py
```

- Port: **18120** (loopback)
- Env: `GATEWAY_URL`, `GATEWAY_COOKIE` and/or `INFRA_AGENT_TOKEN`, `PORT`

List tools: `GET /tools`
Call tool: `POST /tools/call` with `{ "name", "arguments", "cookie"? }`

Harness tools:

- `infra_resolve_server` — `{ q, limit? }` → ranked hosts
- `infra_run` — `{ server_id, command, confirm_destructive?, timeout_sec? }`
- `vms_summary` / `vms_top_cameras` / `vms_search_plate` / `vms_search_person` / `vms_daily` — VMS warehouse (no SQL; ClickHouse stays on the gateway)
