# ClickHouse VMS warehouse (long-term AI events)

Postgres on `192.168.1.242:18644` stays the hot OLTP store. This stack copies **analytics columns** (no `snapshot_base64` / `image` / `face_feature`) into ClickHouse `vms.ai_events` for history queries.

**One replica only** (`creanova-vms-sync`). Do not `compose scale`.

Which files from the cloned `ClickHouse/` tree this stack actually uses: [UPSTREAM.md](UPSTREAM.md).

## Boot

```bash
cp deploy/clickhouse/.env.example deploy/clickhouse/.env
# set CLICKHOUSE_PASSWORD, CH_*_PASSWORD, PG_PASSWORD

# Once, as Postgres superuser `dev` (creates read-only role vms_sync_ro):
docker run --rm -i --network host -e PGPASSWORD="$DEV_PASSWORD" postgres:16-alpine \
  psql -h 192.168.1.242 -p 18644 -U dev -d postgres \
  -v pwd="$PG_PASSWORD" -f - < deploy/clickhouse/sql/pg_vms_sync_ro.sql

docker compose -f deploy/clickhouse/docker-compose.yml --env-file deploy/clickhouse/.env up -d
```

Requires existing Docker network `agent-canvas_net` (Agent Canvas compose).

- HTTP: `http://127.0.0.1:18123` (loopback only)
- Image: `clickhouse/clickhouse-server:26.8.2.7` (26.8 LTS line; Hub has no `26.8-lts` tag yet)
- Native TCP: `127.0.0.1:19000`
- Docker net: `creanova_clickhouse_net` → `10.240.126.0/24`

```bash
curl -sS http://127.0.0.1:18123/ping
docker exec creanova-clickhouse clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q "SHOW TABLES FROM vms"
docker exec agent-canvas curl -sS http://creanova-clickhouse:8123/ping
```

Init users/schema run **only on first empty volume**. To recreate: `docker compose ... down -v` (destroys data).

## Verify backfill

Wait until logs show idle batches, then:

```bash
set -a && source deploy/clickhouse/.env && set +a
bash deploy/clickhouse/scripts/verify_parity.sh
```

GĐ1 accepts snapshot-at-copy: later Postgres UPDATEs (e.g. `is_blacklisted`) are **not** replayed.

`its.plate_event` / `firesmoke` on Postgres may be shorter than ClickHouse (warehouse already holds history). Extra AI tables (`footfall_event`, `ppe_event`, `ai_event`) are mapped; re-run `pg_vms_sync_ro.sql` as `dev` to GRANT SELECT, then restart `creanova-vms-sync`. `thermal_alert` is UUID-keyed and still empty — mapper exists, not in the poll loop.

Query indexes/projection: `deploy/clickhouse/sql/migrate_001_query_indexes.sql`. Benchmark: [BENCHMARK.md](BENCHMARK.md).

## Agent tools (no SQL)

The agent **does not write ClickHouse SQL**. Curated queries live in `local-gateway` (`/api/infra/analytics/*`). Header `X-Creanova-Infra-Token`. Copy `CH_VMS_PASSWORD` into `agent-canvas/.env` as `CH_PASSWORD` (user `vms_ro`).

| Intent | GET | MCP |
|--------|-----|-----|
| Counts | `/api/infra/analytics/summary?days=7&module=ANOMALY` | `vms_summary` |
| Top cameras | `/api/infra/analytics/top-cameras?days=30&module=ANOMALY&event_type=INTRUSION_DETECTION` | `vms_top_cameras` |
| Plate | `/api/infra/analytics/search-plate?q=<plate>` | `vms_search_plate` |
| Person | `/api/infra/analytics/search-person?q=<name>` | `vms_search_person` |
| Daily trend | `/api/infra/analytics/daily?days=30` | `vms_daily` |

`module`: `FACE` \| `PLATE` \| `ZONE` \| `ANOMALY` \| `FIRE`. Do not give the agent `default` or `vms_sync`.

Ask a new conversation: “tháng này camera nào nhiều leo trèo nhất” / “biển 30A12345 xuất hiện khi nào”.

## GĐ2 (not in this stack)

VMS UI must query via API with `vms_ro` + `organization_id`, not from the browser. Opening `:18123` on the LAN is a later decision.

## Subnet check (Atin191)

```bash
docker network inspect creanova_clickhouse_net --format '{{json .IPAM.Config}}'
ip route get 192.168.1.242   # must go via LAN, not br-*
```
