# Creanova Local Gateway

Auth + per-user session gateway in front of the local agent-server.

## Default: no Docker auth (`AUTH_BACKEND=local`)

Seed users `admin`/`admin123`, `demo`/`demo123`. Admin tạo user tại `/admin/users`.

```bash
AUTH_BACKEND=local OH_LOCAL_AUTH=1 npm run dev   # from agent-canvas
```

## PostgreSQL (port 54288)

```bash
cp deploy/data/.env.example deploy/data/.env
docker compose -f deploy/data/docker-compose.yml --env-file deploy/data/.env up -d
```

Gateway:

```bash
export DATABASE_URL=postgresql+psycopg://creanova:PASSWORD@127.0.0.1:54288/creanova
# or from agent-canvas:
# OH_DATA_BACKEND=postgres
# LOCAL_GATEWAY_DATABASE_URL=...
```

Migrate SQLite → Postgres:

```bash
uv run python scripts/migrate_sqlite_to_postgres.py --sqlite /path/to/local-gateway.db
uv run python scripts/migrate_sqlite_to_postgres.py --sqlite /path/to/local-gateway.db --apply
```

Network: `creanova_data_net` → `10.240.123.0/24` (Atin191 rule).

## Optional Keycloak (`AUTH_BACKEND=keycloak`)

Requires Docker Compose with **subnet 10.240.122.0/24**. See `deploy/local-auth/README.md`.

## Run standalone

```bash
cp .env.example .env
uv sync
uv run python main.py
```

## Infra (SSH / GPU / services)

- Admin UI: `/admin/infra`
- **SSH workspace (Terminus-style)**: `/admin/ssh` — host sidebar + tabs + xterm.js
- WebSocket: `WS /api/infra/servers/{id}/ssh`
- REST: `/api/infra/servers`, `.../gpu`, `.../services`, `.../test`
- Credentials encrypted (Fernet); never returned in API responses
- Agent tools bridge: `services/infra-mcp` on port **18120**

## Credits

- Default cost: `CREDIT_COST_PER_CONVERSATION=1`, `CREDIT_COST_PER_RUN=1`
- HTTP **402** when balance insufficient
- Admin UI: `/admin/users`

## Smoke

```bash
curl -s http://127.0.0.1:18110/healthz
curl -s -c /tmp/c.jar -X POST http://127.0.0.1:18110/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
curl -s -b /tmp/c.jar http://127.0.0.1:18110/api/infra/servers
```
