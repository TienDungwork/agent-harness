# Creanova path gateway

One host port routes by function. **Preferred start:** from `agent-canvas/` so agents, admin, and monitoring come up together:

```bash
cd agent-canvas
docker compose up -d --build
# open http://<LAN-IP>:18000/
```

| Path | App | Upstream |
|------|-----|----------|
| `/agents/` | Agent Canvas | `agent-canvas:8000` (`:18010`) |
| `/admin/` | Creanova FE (usage / LLM) | `creanova-admin` (static image, `VITE_LOCAL_GATEWAY_ADMIN`) — **`/api` → same local-gateway as Agents** |
| `/monitoring/` | Beszel | `creanova-beszel-ui:8090` (`:18090`) |

Landing: `http://<IP>:18000/`

Agent Canvas backend host (same origin): `http://<IP>:18000` — gateway proxies `/server_info`, `/api/`, `/sockets` to agent-canvas. Direct canvas remains `http://<IP>:18010`.

Do **not** run this compose and `agent-canvas` compose at the same time — both define `creanova-gateway` / `creanova-admin`.

## Docker network (network.md / Atin191)

- `agent-canvas` compose: gateway sits on `agent-canvas_net` (`10.240.120.0/24`)
- Standalone file below also creates `creanova_gateway_net` (`10.240.125.0/24`)
- Do **not** use Docker default `192.168.x` pools

## Prerequisites

1. Agent Canvas stack (overlay UI + Beszel) — `cd agent-canvas && docker compose up -d`
2. Canvas UI built with `VITE_BASE_PATH=/agents` (and container `AGENT_CANVAS_BASE_PATH=/agents`)
3. Admin image `creanova-admin:local` (built from `frontend/Dockerfile.admin` on `docker compose up --build`)

No host Vite on `:12000`. For FE iteration: `cd frontend && npm run dev:local:gateway -- --port 12000 --host 0.0.0.0`, then temporarily point nginx back — not the default path.

## Standalone start (canvas already up)

```bash
cd /path/to/OpenHands
docker compose -f deploy/gateway/docker-compose.yml up -d --build
curl -sI http://127.0.0.1:18000/ | head -5
```

Override port: `GATEWAY_HOST_PORT=18000`.

## Shared `/api` routing

Agents and admin share local-gateway (`agent-canvas:8000`). Beszel still uses cookie `gateway_app=monitoring`.

Open `/admin/` first so the cookie is set, then log in with the same local-auth users as Agents (default `admin` / `admin123`). Usage lists Canvas conversations from `GET /api/conversations/search`. LLM settings use `GET`/`PATCH /api/settings`.

## Notes

- Legacy `/canvas/` is still proxied for old overlays.
- Beszel under `/monitoring/` is best-effort (PocketBase absolute paths); if the UI breaks, use `:18090` directly until APP_URL/base-path is wired.
- After login: `/admin/settings/usage-monitoring`
- CORS: add `http://<IP>:18000` to `CORS_ORIGINS` in agent-canvas `.env` if browser blocks gateway-origin API calls.
- Rebuild admin after FE changes: `docker compose up -d --build admin-ui`
- `npm run dev:mock:saas:gateway` is only for isolated MSW SaaS UI, not this path.
