#!/usr/bin/env bash
# High-load warehouse benchmark: US1/US2 + tool queries vs NFR (< 3s).
# Usage (repo root):
#   set -a && source deploy/clickhouse/.env && set +a
#   bash deploy/clickhouse/scripts/benchmark.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a && source "$ROOT/.env" && set +a
fi
: "${CLICKHOUSE_PASSWORD:?CLICKHOUSE_PASSWORD required}"
PG_HOST="${PG_HOST:-192.168.1.242}"
PG_PORT="${PG_PORT:-18644}"
PG_USER="${PG_USER:-vms_sync_ro}"
: "${PG_PASSWORD:?PG_PASSWORD required}"

CH=(docker exec creanova-clickhouse clickhouse-client --password "$CLICKHOUSE_PASSWORD" --time)

run_ch() {
  local name="$1" sql="$2"
  echo "=== $name ==="
  local i total=0
  for i in 1 2 3 4 5; do
    local out elapsed
    out="$("${CH[@]}" -q "$sql" 2>&1)" || { echo "FAIL $name"; echo "$out"; return 1; }
    elapsed="$(printf '%s\n' "$out" | tail -n 1)"
    echo "  run $i  ${elapsed}s"
    total="$(python3 -c "print($total + float('$elapsed'))")"
  done
  python3 -c "print('  avg  {:.4f}s'.format($total / 5))"
}

echo "ClickHouse warehouse benchmark $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
docker exec creanova-clickhouse clickhouse-client --password "$CLICKHOUSE_PASSWORD" -q \
  "SELECT count() AS rows, formatReadableSize(sum(bytes_on_disk)) AS disk
   FROM system.parts WHERE database='vms' AND table='ai_events' AND active"
echo

run_ch 'US1 top cameras INTRUSION 30d (NFR <3s)' \
"SELECT camera_name, count() n FROM vms.ai_events
 WHERE module='ANOMALY' AND event_type='INTRUSION_DETECTION'
   AND event_time >= now() - INTERVAL 30 DAY
 GROUP BY camera_name ORDER BY n DESC LIMIT 10"

run_ch 'US1 top cameras INTRUSION 365d' \
"SELECT camera_name, count() n FROM vms.ai_events
 WHERE module='ANOMALY' AND event_type='INTRUSION_DETECTION'
   AND event_time >= now() - INTERVAL 365 DAY
 GROUP BY camera_name ORDER BY n DESC LIMIT 10"

run_ch 'US2 plate prefix 180d' \
"SELECT count() FROM vms.ai_events
 WHERE module='PLATE' AND event_time >= now() - INTERVAL 180 DAY
   AND license_plate LIKE '30A%'"

run_ch 'summary 7d group module/event_type' \
"SELECT module, event_type, count() n FROM vms.ai_events
 WHERE event_time >= now() - INTERVAL 7 DAY
 GROUP BY module, event_type ORDER BY n DESC LIMIT 50"

run_ch 'daily mart 30d' \
"SELECT day, module, sum(events) n FROM vms.ai_events_daily
 WHERE day >= today() - 30
 GROUP BY day, module ORDER BY day, module LIMIT 400"

run_ch 'person ILIKE 90d' \
"SELECT count() FROM vms.ai_events
 WHERE module IN ('FACE','ZONE','PPE') AND event_time >= now() - INTERVAL 90 DAY
   AND person_name ILIKE '%a%'"

echo
echo "=== Postgres anomaly (hot OLTP) vs ClickHouse same aggregation ==="
pg_sql="SELECT camera_name, count(*) n FROM anomaly_event WHERE event_type='INTRUSION_DETECTION' AND event_time >= NOW() - INTERVAL '30 days' GROUP BY camera_name ORDER BY n DESC LIMIT 10"
echo "-- Postgres"
/usr/bin/time -f '  real %e s' docker run --rm --network host -e PGPASSWORD="$PG_PASSWORD" postgres:16-alpine \
  psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d anomaly -Atc "$pg_sql" >/tmp/pg_us1.txt || true
wc -l /tmp/pg_us1.txt | awk '{print "  rows", $1}'
echo "-- ClickHouse"
"${CH[@]}" -q "SELECT camera_name, count() n FROM vms.ai_events WHERE src_db='anomaly' AND event_type='INTRUSION_DETECTION' AND event_time >= now() - INTERVAL 30 DAY GROUP BY camera_name ORDER BY n DESC LIMIT 10" >/tmp/ch_us1.txt
wc -l /tmp/ch_us1.txt | awk '{print "  rows", $1}'

echo
echo "Done. NFR: agent-style group-by on 1-12 months < 3s."
