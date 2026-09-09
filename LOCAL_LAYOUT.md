# Local layout (not upstream)

These folders were placed here for convenience (upstream keeps them as separate repos):

- `agent-canvas/` — current Agent Canvas UI ([Creanova/agent-canvas](https://github.com/Creanova/agent-canvas))
- `software-agent-sdk/` — agent + agent server ([Creanova/software-agent-sdk](https://github.com/Creanova/software-agent-sdk))
- `frontend/` — UI still in this monorepo (being migrated toward agent-canvas)
- `ClickHouse/` — upstream engine source ([ClickHouse/ClickHouse](https://github.com/ClickHouse/ClickHouse.git)), tag `v26.8.2.7-lts`. Only the pieces listed in `deploy/clickhouse/UPSTREAM.md` are used for the VMS plan (image + `config.d` / initdb / MergeTree SQL). Do not compile `src/`. gitignored.

## Run Agent Canvas (recommended: Docker)

Host port `8000` is taken (Triton). Compose publishes Canvas on **18010**.

Bridge subnet is pinned to **`10.240.120.0/24`** (Atin191 rule: never use Docker default `192.168.x.0/20` — overlaps LAN/VPN).

```bash
mkdir -p ~/projects ~/.Creanova
cd agent-canvas
# If an old default network exists (192.168.80.0/20), recreate:
docker compose down
docker network rm agent-canvas_default 2>/dev/null || true
docker compose up -d
```

Open: http://localhost:18010/agents/

Path gateway (agents + admin + monitoring, one port): `cd agent-canvas && docker compose up -d --build` → http://localhost:18000/

ClickHouse VMS warehouse: see `deploy/clickhouse/` — HTTP `http://127.0.0.1:18123` (loopback). Agent reads via `local-gateway` `/api/infra/analytics/*` (no SQL). ClickHouse hostname `creanova-clickhouse:8123` on `agent-canvas_net`.

Stop: `docker compose down`

Beszel (bundled): http://localhost:18090 — login `admin@creanova.local` / `admin123`

Ports / paths are in `agent-canvas/.env` (`CANVAS_HOST_PORT`, `PROJECTS_PATH`, …).

## Run from source (optional)

Needs Node `>=22.12` and `uv` on `PATH`:

```bash
export PATH="$(dirname "$(nvm which 22)"):$HOME/.local/bin:$PATH"
cd agent-canvas
npm run dev
```

Open: http://localhost:18010/

## Creanova root `docker-compose.yml`

Legacy Creanova app server + old `frontend/`. Not needed for Agent Canvas.
