# Creanova path gateway

One host port routes by function:

| Path | App | Upstream |
|------|-----|----------|
| `/agents/` | Agent Canvas | `agent-canvas:8000` (`:18010`) |
| `/admin/` | Creanova FE (usage / LLM) | host `:12000` UI; **`/api` → same local-gateway as Agents** |
| `/monitoring/` | Beszel | `creanova-beszel-ui:8090` (`:18090`) |

Landing: `http://<IP>:18000/`

Agent Canvas backend host (same origin): `http://<IP>:18000` — gateway proxies `/server_info`, `/api/`, `/sockets` to agent-canvas. Direct canvas remains `http://<IP>:18010`.

## Docker network (network.md / Atin191)

- Bridge: `creanova_gateway_net` → **`10.240.125.0/24`**
- Also attaches to external `agent-canvas_net` (`10.240.120.0/24`)
- Do **not** use Docker default `192.168.x` pools

## Prerequisites

1. Agent Canvas stack up (`cd agent-canvas && docker compose up -d`)
2. Canvas UI built with `VITE_BASE_PATH=/agents` (and container `AGENT_CANVAS_BASE_PATH=/agents`)
3. Creanova FE on `:12000` with local gateway admin (no MSW):
   ```bash
   cd frontend
   npm run dev:local:gateway -- --port 12000 --host 0.0.0.0
   ```
4. Beszel UI on `:18090` (bundled in agent-canvas compose)

## Start

```bash
cd /path/to/OpenHands
docker compose -f deploy/gateway/docker-compose.yml up -d
docker compose -f deploy/gateway/docker-compose.yml ps
curl -sI http://127.0.0.1:18000/ | head -5
```

Override port: `GATEWAY_HOST_PORT=18000`.

## Shared `/api` routing

Agents and admin share local-gateway (`agent-canvas:8000`). Beszel still uses cookie `gateway_app=monitoring`.

Open `/admin/` first so the cookie is set, then log in with the same local-auth users as Agents (default `admin` / `admin123`). Usage lists Canvas conversations from `GET /api/conversations/search`. LLM settings use `GET`/`PATCH /api/settings`.

Do not browse Vite on `:12000` directly — `/api` must go through `:18000`.

## Notes

- Legacy `/canvas/` is still proxied for old overlays.
- Beszel under `/monitoring/` is best-effort (PocketBase absolute paths); if the UI breaks, use `:18090` directly until APP_URL/base-path is wired.
- After login: `/admin/settings/usage-monitoring`
- CORS: add `http://<IP>:18000` to `CORS_ORIGINS` in agent-canvas `.env` if browser blocks gateway-origin API calls.
- `npm run dev:mock:saas:gateway` is only for isolated MSW SaaS UI, not this path.

One host port routes by function:

| Path | App | Upstream |
|------|-----|----------|
| `/agents/` | Agent Canvas | `agent-canvas:8000` (`:18010`) |
| `/admin/` | Creanova FE (usage / org) | host `:12000` |
| `/monitoring/` | Beszel | `creanova-beszel-ui:8090` (`:18090`) |

Landing: `http://<IP>:18000/`

Agent Canvas backend host (same origin): `http://<IP>:18000` — gateway proxies `/server_info`, `/api/`, `/sockets` to agent-canvas. Direct canvas remains `http://<IP>:18010`.

## Docker network (network.md / Atin191)

- Bridge: `creanova_gateway_net` → **`10.240.125.0/24`**
- Also attaches to external `agent-canvas_net` (`10.240.120.0/24`)
- Do **not** use Docker default `192.168.x` pools

## Prerequisites

1. Agent Canvas stack up (`cd agent-canvas && docker compose up -d`)
2. Canvas UI built with `VITE_BASE_PATH=/agents` (and container `AGENT_CANVAS_BASE_PATH=/agents`)
3. Creanova FE on `:12000` with base `/admin/`:
   ```bash
   cd frontend
   npm run dev:mock:saas:gateway -- --port 12000 --host 0.0.0.0
   ```
4. Beszel UI on `:18090` (bundled in agent-canvas compose)

## Start

```bash
cd /path/to/OpenHands
docker compose -f deploy/gateway/docker-compose.yml up -d
docker compose -f deploy/gateway/docker-compose.yml ps
curl -sI http://127.0.0.1:18000/ | head -5
```

Override port: `GATEWAY_HOST_PORT=18000`.

## Shared `/api` routing

Agents, admin, and Beszel all use root `/api/`. The gateway picks upstream from cookie `gateway_app` (set when you open `/agents/`, `/admin/`, or `/monitoring/`), with Referer fallback.

## Notes

- Legacy `/canvas/` is still proxied for old overlays.
- Beszel under `/monitoring/` is best-effort (PocketBase absolute paths); if the UI breaks, use `:18090` directly until APP_URL/base-path is wired.
- Usage dashboard after login: `/admin/settings/usage-monitoring`
- CORS: add `http://<IP>:18000` to `CORS_ORIGINS` in agent-canvas `.env` if browser blocks gateway-origin API calls.
