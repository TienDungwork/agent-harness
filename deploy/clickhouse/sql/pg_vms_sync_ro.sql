-- Run once as Postgres superuser (dev) against 192.168.1.242:18644.
-- psql interpolates :'pwd' from:  psql -v pwd='the-password' -f this-file
--
-- Example:
--   docker run --rm -i --network host -e PGPASSWORD="$DEV_PASSWORD" postgres:16-alpine \
--     psql -h 192.168.1.242 -p 18644 -U dev -d postgres \
--     -v pwd="$PG_PASSWORD" -f - < deploy/clickhouse/sql/pg_vms_sync_ro.sql

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE vms_sync_ro LOGIN PASSWORD %L', :'pwd')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vms_sync_ro')
\gexec

ALTER ROLE vms_sync_ro LOGIN PASSWORD :'pwd';

GRANT CONNECT ON DATABASE its TO vms_sync_ro;
GRANT CONNECT ON DATABASE anomaly TO vms_sync_ro;
GRANT CONNECT ON DATABASE smart_face TO vms_sync_ro;
GRANT CONNECT ON DATABASE virtual_fence TO vms_sync_ro;
GRANT CONNECT ON DATABASE firesmoke TO vms_sync_ro;
GRANT CONNECT ON DATABASE footfall TO vms_sync_ro;
GRANT CONNECT ON DATABASE ppe TO vms_sync_ro;
GRANT CONNECT ON DATABASE thermal_db TO vms_sync_ro;
GRANT CONNECT ON DATABASE vms_db TO vms_sync_ro;

\c its
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.plate_event TO vms_sync_ro;

\c anomaly
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.anomaly_event TO vms_sync_ro;

\c smart_face
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.smf_face_events TO vms_sync_ro;

\c virtual_fence
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.zone_event TO vms_sync_ro;

\c firesmoke
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.fire_smoke_event TO vms_sync_ro;

\c footfall
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.footfall_event TO vms_sync_ro;

\c ppe
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.ppe_event TO vms_sync_ro;

\c thermal_db
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.thermal_alert TO vms_sync_ro;

\c vms_db
GRANT USAGE ON SCHEMA public TO vms_sync_ro;
GRANT SELECT ON TABLE public.ai_event TO vms_sync_ro;
