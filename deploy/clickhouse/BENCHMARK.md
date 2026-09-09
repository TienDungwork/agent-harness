# ClickHouse VMS warehouse benchmark

Date: **2026-09-09** (UTC). Host `.198`, image `clickhouse-server:26.8.2.7`, table `vms.ai_events`.

NFR in plan: agent-style `GROUP BY` camera/module on **1–12 months &lt; 3 s**.

## Data

| Metric | Value |
|--------|--------|
| Rows | **744 877** |
| Compressed parts | **~94 MiB** |
| Sources | `plate_event` 544k, `anomaly_event` 134k, `smf_face_events` 40k, `zone_event` 20k, `fire_smoke_event` 7k |
| Skip indexes | bloom `license_plate` / `camera_id` / `entity_id`, ngram `person_name` |
| Projection | `prj_top_cameras` (`deduplicate_merge_projection_mode=rebuild`) |

Postgres **hot** vs warehouse: `its.plate_event` is now **167** rows on PG (history lives in ClickHouse). `firesmoke.fire_smoke_event` is **0** on PG. Extra DBs `footfall` / `ppe` / `thermal_db.thermal_alert` / `vms_db.ai_event` are **empty** and still need `GRANT SELECT` (`deploy/clickhouse/sql/pg_vms_sync_ro.sql`) before sync will enable them.

## Query times (5 runs, `clickhouse-client --time`, avg)

| Query (plan US) | Avg |
|-----------------|-----|
| US1 top cameras `INTRUSION_DETECTION` 30d | **0.026 s** |
| US1 same, 365d | **0.026 s** |
| US2 plate prefix `30A%` 180d | **0.030 s** |
| Summary 7d by module/event_type | **0.033 s** |
| Daily mart 30d | **0.018 s** |
| Person `ILIKE` 90d | **0.019 s** |

All **~100× under** the 3 s NFR.

## ClickHouse vs Postgres (same aggregation)

`ANOMALY` / `INTRUSION_DETECTION` / last 30 days / top 10 cameras:

| Store | Wall time |
|-------|-----------|
| Postgres `anomaly.anomaly_event` | **0.60 s** |
| ClickHouse `vms.ai_events` | **0.03 s** (~20×)

Re-run:

```bash
set -a && source deploy/clickhouse/.env && set +a
bash deploy/clickhouse/scripts/benchmark.sh
```
