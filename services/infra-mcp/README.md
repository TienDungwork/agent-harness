# Infra MCP bridge (agent tools → local-gateway)

```bash
cd services/infra-mcp
uv run --with fastapi --with uvicorn --with httpx --with pydantic python main.py
```

- Port: **18120** (loopback)
- Env: `GATEWAY_URL`, `GATEWAY_COOKIE`, `PORT`

List tools: `GET /tools`
Call tool: `POST /tools/call` with `{ "name", "arguments", "cookie" }`
