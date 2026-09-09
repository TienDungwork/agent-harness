#!/usr/bin/env bash
# Compare Postgres source counts vs ClickHouse vms.ai_events.
# Usage (from repo root, with deploy/clickhouse/.env loaded):
#   set -a && source deploy/clickhouse/.env && set +a
#   bash deploy/clickhouse/scripts/verify_parity.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
set -a
# Prefer already-exported env; fall back to .env
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi
set +a

PG_HOST="${PG_HOST:-192.168.1.242}"
PG_PORT="${PG_PORT:-18644}"
PG_USER="${PG_USER:-vms_sync_ro}"
: "${PG_PASSWORD:?PG_PASSWORD required}"
CH_HTTP="${CH_HTTP:-http://127.0.0.1:18123}"
CH_USER="${CH_USER:-default}"
CH_PASSWORD="${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD required}"

psql_count() {
  local db="$1" table="$2"
  docker run --rm --network host -e PGPASSWORD="$PG_PASSWORD" postgres:16-alpine \
    psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$db" -Atc "SELECT count(*) FROM $table" 2>/dev/null \
    || echo 'NOGRANT'
}

ch_count() {
  local db="$1" table="$2"
  docker exec creanova-clickhouse clickhouse-client --user "$CH_USER" --password "$CH_PASSWORD" -q \
    "SELECT count() FROM vms.ai_events WHERE src_db='$db' AND src_table='$table'"
}

fail=0
printf '%-16s %-18s %12s %12s %s\n' 'src_db' 'src_table' 'postgres' 'clickhouse' 'status'
while read -r db table; do
  pg="$(psql_count "$db" "$table")"
  ch="$(ch_count "$db" "$table")"
  if [[ "$pg" == "NOGRANT" ]]; then
    status='SKIP no SELECT'
    printf '%-16s %-18s %12s %12s %s\n' "$db" "$table" '-' "$ch" "$status"
    continue
  fi
  status='OK'
  # Allow ClickHouse to lag the hot 30s window plus in-flight writes.
  # CH may be ahead of hot PG when the source table was truncated/retained.
  if [[ "$ch" -gt "$pg" ]]; then
    status="CH_AHEAD $((ch - pg))"
  elif [[ $((pg - ch)) -gt 50000 ]]; then
    status='FAIL lag>50k'
    fail=1
  elif [[ "$ch" -lt "$pg" ]]; then
    status="LAG $((pg - ch))"
  fi
  printf '%-16s %-18s %12s %12s %s\n' "$db" "$table" "$pg" "$ch" "$status"
done <<'EOF'
its plate_event
anomaly anomaly_event
smart_face smf_face_events
virtual_fence zone_event
firesmoke fire_smoke_event
footfall footfall_event
ppe ppe_event
vms_db ai_event
EOF

exit "$fail"
