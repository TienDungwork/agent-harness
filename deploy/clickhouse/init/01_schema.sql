CREATE DATABASE IF NOT EXISTS vms;

CREATE TABLE IF NOT EXISTS vms.ai_events
(
    event_time      DateTime64(3, 'UTC'),
    module          LowCardinality(String),
    event_type      LowCardinality(String),
    severity        LowCardinality(String),
    organization_id Int64,
    site_id         Int64,
    iam_area_id     Int64,
    iam_zone_id     Int64,
    node_id         Int64,
    node_path       String,
    camera_id       UUID,
    camera_code     LowCardinality(String),
    camera_name     String,
    zone_id         String,
    zone_name       String,
    entity_type     LowCardinality(String),
    entity_id       String,
    direction       LowCardinality(String),
    confidence      Float32,
    person_id       Int64,
    person_name     String,
    license_plate   String,
    snapshot_url    String,
    video_clip_url  String,
    attrs           Map(LowCardinality(String), String),
    payload         String CODEC(ZSTD(3)),
    src_db          LowCardinality(String),
    src_table       LowCardinality(String),
    src_id          Int64,
    created_at      DateTime64(3, 'UTC'),
    ingested_at     DateTime DEFAULT now(),
    INDEX idx_plate license_plate TYPE bloom_filter GRANULARITY 4,
    INDEX idx_camera camera_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_person person_name TYPE ngrambf_v1(3, 512, 2, 0) GRANULARITY 4,
    INDEX idx_entity entity_id TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(event_time)
ORDER BY (module, organization_id, event_time, src_db, src_table, src_id)
TTL toDateTime(event_time) + INTERVAL 3 YEAR
SETTINGS index_granularity = 8192, deduplicate_merge_projection_mode = 'rebuild';

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

CREATE TABLE IF NOT EXISTS vms.ai_events_daily
(
    day Date,
    organization_id Int64,
    module LowCardinality(String),
    event_type LowCardinality(String),
    camera_id UUID,
    camera_name String,
    events UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (organization_id, module, event_type, camera_id, day);

CREATE MATERIALIZED VIEW IF NOT EXISTS vms.ai_events_daily_mv
TO vms.ai_events_daily
AS
SELECT
    toDate(event_time) AS day,
    organization_id,
    module,
    event_type,
    camera_id,
    any(camera_name) AS camera_name,
    count() AS events
FROM vms.ai_events
GROUP BY day, organization_id, module, event_type, camera_id;

CREATE TABLE IF NOT EXISTS vms.sync_state
(
    src_db LowCardinality(String),
    src_table LowCardinality(String),
    last_id Int64,
    rows_copied UInt32,
    ok UInt8,
    error String,
    run_at DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (src_db, src_table, run_at)
TTL run_at + INTERVAL 90 DAY;
