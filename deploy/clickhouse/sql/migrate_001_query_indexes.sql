-- Apply on a live volume (init/*.sql only runs on first empty data dir).
-- docker exec -i creanova-clickhouse clickhouse-client --password "$CLICKHOUSE_PASSWORD" < this file

ALTER TABLE vms.ai_events
    ADD INDEX IF NOT EXISTS idx_person person_name TYPE ngrambf_v1(3, 512, 2, 0) GRANULARITY 4;

ALTER TABLE vms.ai_events
    ADD INDEX IF NOT EXISTS idx_entity entity_id TYPE bloom_filter GRANULARITY 4;

ALTER TABLE vms.ai_events
    MODIFY SETTING deduplicate_merge_projection_mode = 'rebuild';

ALTER TABLE vms.ai_events ADD PROJECTION IF NOT EXISTS prj_top_cameras
(
    SELECT
        module,
        event_type,
        camera_id,
        camera_name,
        count()
    GROUP BY module, event_type, camera_id, camera_name
);

ALTER TABLE vms.ai_events MATERIALIZE INDEX idx_person;
ALTER TABLE vms.ai_events MATERIALIZE INDEX idx_entity;
ALTER TABLE vms.ai_events MATERIALIZE PROJECTION prj_top_cameras;
