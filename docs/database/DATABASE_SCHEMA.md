# Storage Service - Single Table Database Architecture

**Service:** Storage Monitoring & Management  
**Port:** 31070  
**Database:** 1 bảng JSONB để lưu raw API responses

---

## Data Flow Architecture

```
Storage Service API (31070)  →  Sync Worker  →  PostgreSQL (1 table)  →  Backend API  →  Clients
    ↓ Raw JSON                    ↓ Parse            ↓ JSONB              ↓ Query         ↓ Visualize
  Filesystem scan             Save to DB        storage_records      Fast response     Dashboard
```

**Key Points:**
- ✅ Storage Service API scan filesystem & expose endpoints
- ✅ Sync Worker poll API every 15s, save RAW JSON to DB
- ✅ Backend API CHỈ query DB, KHÔNG call Storage Service
- ✅ 1 bảng universal: `storage_records` (JSONB)

---

## Database Table: storage_records

**Bảng duy nhất để lưu toàn bộ raw API responses**

### Table Schema

```sql
CREATE TABLE storage_records (
    id SERIAL PRIMARY KEY,
    record_type VARCHAR(50) NOT NULL,   -- Loại data
    record_key VARCHAR(100),             -- Identifier (camera name, hour, device name)
    record_date DATE,                    -- Ngày (cho bandwidth time-series)
    data JSONB NOT NULL,                 -- Raw JSON từ API
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_storage_records_type ON storage_records(record_type);
CREATE INDEX idx_storage_records_type_date ON storage_records(record_type, record_date DESC);
CREATE INDEX idx_storage_records_key ON storage_records(record_type, record_key);
CREATE INDEX idx_storage_records_data ON storage_records USING GIN(data);
CREATE INDEX idx_storage_records_created ON storage_records(created_at DESC);

-- Unique constraint cho current state (camera_status, block_device)
CREATE UNIQUE INDEX idx_storage_records_current_state 
ON storage_records(record_type, record_key) 
WHERE record_key IS NOT NULL AND record_type IN ('camera_status', 'block_device');
```

---

## Record Types & Data Mapping

### 1. **storage_stats** - Dung lượng disk

**API Source:** `GET /api/v1/storage` → `storage`  
**Frequency:** Every 15s  
**Storage:** Insert new snapshot (keep 7 days history)

| Field | Purpose |
|-------|---------|
| record_type | `'storage_stats'` |
| record_key | `NULL` |
| record_date | `NULL` |
| data | Raw JSON: `{device, mount_point, total_gb, used_gb, free_gb, percent, size_human, ...}` |

**Visualization Use:**
- Current disk usage gauge
- Trending chart (7 days)
- Alert when percent > 80%

---

### 2. **camera_status** - Trạng thái camera

**API Source:** `GET /api/v1/storage/cameras` → `cameras[]`  
**Frequency:** Every 15s  
**Storage:** Upsert (overwrite existing record)

| Field | Purpose |
|-------|---------|
| record_type | `'camera_status'` |
| record_key | Camera name (e.g., `'XUAN_HOA_IN'`) |
| record_date | `NULL` |
| data | Raw JSON: `{camera_name, last_modified, seconds_ago, bandwidth_mb_24h, bandwidth_gb_24h, is_active}` |

**Visualization Use:**
- Camera list table với status badge (active/inactive)
- Sort by bandwidth (top consumers)
- Filter active cameras
- Bandwidth bar chart per camera

---

### 3. **bandwidth_hourly** - Băng thông theo giờ

**API Source:** `GET /api/v1/storage/bandwidth` → `hourly`  
**Frequency:** Every 15s  
**Storage:** Insert (keep 30 days, có nested camera data)

| Field | Purpose |
|-------|---------|
| record_type | `'bandwidth_hourly'` |
| record_key | Hour `'00'` to `'23'` |
| record_date | Date của hour đó |
| data | Raw JSON: `{hour, total_mb, cameras: {cam1: mb, cam2: mb, ...}}` |

**Visualization Use:**
- Line chart: Total bandwidth 24h
- Stacked area chart: Bandwidth per camera per hour
- Heatmap: Busy hours

---

### 4. **forecast** - Dự báo storage

**API Source:** `GET /api/v1/storage/forecast` → `forecast`  
**Frequency:** Every 15s  
**Storage:** Insert snapshot (keep 7 days)

| Field | Purpose |
|-------|---------|
| record_type | `'forecast'` |
| record_key | `NULL` |
| record_date | `NULL` |
| data | Raw JSON: `{avg_gb_per_hour, avg_gb_per_day, days_until_full, retention_days, estimated_full_date}` |

**Visualization Use:**
- KPI card: Days until full
- Progress bar: Retention capacity
- Timeline: Estimated full date

---

### 5. **health** - Sức khỏe hệ thống

**API Source:** `GET /api/v1/storage/health` → `health`  
**Frequency:** Every 15s  
**Storage:** Insert snapshot (keep 7 days)

| Field | Purpose |
|-------|---------|
| record_type | `'health'` |
| record_key | `NULL` |
| record_date | `NULL` |
| data | Raw JSON: `{status, message, disk_percent, active_cameras, total_cameras}` |

**Visualization Use:**
- Health badge: healthy/warning/critical
- Alert notification
- Status card with message

---

### 6. **block_device** - Ổ cứng vật lý

**API Source:** `GET /api/v1/storage/block-devices` → `devices[]`  
**Frequency:** Every 15s  
**Storage:** Upsert (overwrite existing record, includes nested partitions)

| Field | Purpose |
|-------|---------|
| record_type | `'block_device'` |
| record_key | Device name (e.g., `'sdb'`) |
| record_date | `NULL` |
| data | Raw JSON: `{name, device, type, size_gb, size_human, model, is_primary, partitions: [...]}` |

**Visualization Use:**
- Device list with SSD/HDD icons
- Storage capacity per device
- Partition breakdown

---

### 7. **active_cameras_summary** - Tổng quan cameras

**API Source:** `GET /api/v1/storage` → `active_cameras`  
**Frequency:** Every 15s  
**Storage:** Insert snapshot

| Field | Purpose |
|-------|---------|
| record_type | `'active_cameras_summary'` |
| record_key | `NULL` |
| record_date | `NULL` |
| data | Raw JSON: `{active_count, inactive_count, total_count, active: [...], inactive: [...]}` |

**Visualization Use:**
- KPI cards: Active vs Inactive count
- Pie chart: Camera status distribution

---

## Query Patterns cho Visualization

### Dashboard Overview

```sql
-- Current storage stats
SELECT data FROM storage_records 
WHERE record_type = 'storage_stats' 
ORDER BY created_at DESC LIMIT 1;

-- Current health status
SELECT data FROM storage_records 
WHERE record_type = 'health' 
ORDER BY created_at DESC LIMIT 1;

-- Current forecast
SELECT data FROM storage_records 
WHERE record_type = 'forecast' 
ORDER BY created_at DESC LIMIT 1;

-- Active cameras summary
SELECT data FROM storage_records 
WHERE record_type = 'active_cameras_summary' 
ORDER BY created_at DESC LIMIT 1;
```

---

### Camera Management

```sql
-- All cameras sorted by bandwidth
SELECT record_key, data 
FROM storage_records 
WHERE record_type = 'camera_status'
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC;

-- Active cameras only
SELECT record_key, data 
FROM storage_records 
WHERE record_type = 'camera_status' 
  AND (data->>'is_active')::boolean = true
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC;

-- Top 5 bandwidth consumers
SELECT 
    record_key as camera_name,
    (data->>'bandwidth_gb_24h')::numeric as bandwidth_gb
FROM storage_records 
WHERE record_type = 'camera_status'
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC
LIMIT 5;

-- Filter cameras by bandwidth threshold (> 1GB)
SELECT record_key, data->'bandwidth_gb_24h' as bandwidth_gb
FROM storage_records 
WHERE record_type = 'camera_status'
  AND (data->>'bandwidth_mb_24h')::numeric > 1000;
```

---

### Bandwidth Analytics

```sql
-- Bandwidth for last 24 hours
SELECT 
    record_key as hour,
    (data->>'total_mb')::numeric as total_mb,
    data->'cameras' as camera_breakdown
FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
  AND record_date >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY record_date DESC, record_key DESC;

-- Bandwidth for specific camera (last 7 days)
SELECT 
    record_key as hour,
    record_date,
    (data->'cameras'->>'XUAN_HOA_IN')::numeric as bandwidth_mb
FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
  AND record_date >= CURRENT_DATE - INTERVAL '7 days'
  AND data->'cameras' ? 'XUAN_HOA_IN'
ORDER BY record_date DESC, record_key DESC;

-- Peak hours analysis (top 5 busy hours)
SELECT 
    record_key as hour,
    AVG((data->>'total_mb')::numeric) as avg_bandwidth_mb
FROM storage_records 
WHERE record_type = 'bandwidth_hourly'
  AND record_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY record_key
ORDER BY avg_bandwidth_mb DESC
LIMIT 5;
```

---

### Storage Trends

```sql
-- Disk usage trend (last 7 days)
SELECT 
    created_at::date as date,
    (data->>'percent')::integer as usage_percent,
    (data->>'used_gb')::numeric as used_gb,
    (data->>'free_gb')::numeric as free_gb
FROM storage_records 
WHERE record_type = 'storage_stats'
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- Daily average bandwidth
SELECT 
    record_date,
    AVG((data->>'total_mb')::numeric) as avg_mb_per_hour,
    SUM((data->>'total_mb')::numeric) as total_mb_per_day
FROM storage_records 
WHERE record_type = 'bandwidth_hourly'
  AND record_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY record_date
ORDER BY record_date DESC;
```

---

### Device Management

```sql
-- All block devices
SELECT 
    record_key as device_name,
    data->>'type' as device_type,
    data->>'size_human' as size,
    data->>'model' as model,
    data->'partitions' as partitions
FROM storage_records 
WHERE record_type = 'block_device';

-- Only SSDs
SELECT record_key, data 
FROM storage_records 
WHERE record_type = 'block_device'
  AND data->>'type' = 'SSD';

-- Primary storage device
SELECT record_key, data 
FROM storage_records 
WHERE record_type = 'block_device'
  AND (data->>'is_primary')::boolean = true;
```

---

## Data Retention & Cleanup

```sql
-- Cleanup bandwidth data older than 30 days
DELETE FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
  AND record_date < CURRENT_DATE - INTERVAL '30 days';

-- Cleanup old snapshots (keep last 7 days)
DELETE FROM storage_records 
WHERE record_type IN ('storage_stats', 'forecast', 'health', 'active_cameras_summary')
  AND created_at < NOW() - INTERVAL '7 days';

-- Keep only latest state for cameras and devices (not historical)
-- Already handled by UPSERT (ON CONFLICT UPDATE)
```

---

## Deployment Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    PRODUCTION FLOW                         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  [Storage Service API:31070]                               │
│         ↓ Raw JSON Response                                │
│  [Sync Worker - Poll 15s]                                  │
│         ↓ INSERT/UPSERT                                    │
│  [PostgreSQL: storage_records]                             │
│         ↑ SELECT queries                                   │
│  [Backend API]                                             │
│         ↓ JSON response                                    │
│  [Frontend Dashboard]                                      │
│         - Storage overview                                 │
│         - Camera management                                │
│         - Bandwidth analytics                              │
│         - Trending charts                                  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Components:**

1. **Storage Service** - Scan filesystem, calculate stats, expose API
2. **Sync Worker** - Poll API every 15s, save raw JSON to DB
3. **Backend API** - Query DB only (5-20ms response)
4. **Frontend** - Visualize data từ Backend API

---

## API Response → Database Mapping

### Example 1: Storage Stats

**API Response:**
```json
{
  "storage": {
    "device": "/dev/sdb1",
    "mount_point": "/var/lib/nxstorage",
    "total_gb": 3600.0,
    "used_gb": 1000.0,
    "free_gb": 2600.0,
    "percent": 24
  }
}
```

**Database Record:**
```
record_type: 'storage_stats'
record_key: NULL
record_date: NULL
data: {"device": "/dev/sdb1", "mount_point": "/var/lib/nxstorage", ...}
```

---

### Example 2: Camera Status

**API Response:**
```json
{
  "cameras": [
    {
      "camera": "XUAN_HOA_IN",
      "last_modified": "2026-02-12T11:08:40",
      "seconds_ago": 3,
      "bandwidth_mb_24h": 13330.78,
      "bandwidth_gb_24h": 13.02,
      "is_active": true
    }
  ]
}
```

**Database Records (1 per camera):**
```
record_type: 'camera_status'
record_key: 'XUAN_HOA_IN'
record_date: NULL
data: {"camera": "XUAN_HOA_IN", "last_modified": "2026-02-12T11:08:40", ...}
```

---

### Example 3: Bandwidth Hourly

**API Response:**
```json
{
  "hourly": {
    "11": {
      "total_mb": 206.97,
      "cameras": {
        "XUAN_HOA_IN": 123.35,
        "CAM_235": 63.39
      }
    }
  }
}
```

**Database Record:**
```
record_type: 'bandwidth_hourly'
record_key: '11'
record_date: '2026-02-12'
data: {"hour": "11", "total_mb": 206.97, "cameras": {...}}
```

---

## Visualization Dashboard Requirements

### 1. **Overview Page**
- Storage usage gauge (current percent)
- Days until full counter
- Active cameras count
- Health status badge
- Disk usage trend chart (7 days)

**Queries needed:**
- Latest storage_stats
- Latest forecast
- Latest health
- Latest active_cameras_summary
- storage_stats history (7 days)

---

### 2. **Camera Management Page**
- Camera list table (sortable by bandwidth)
- Filter: Active/Inactive/All
- Search by camera name
- Bandwidth per camera bar chart
- Top 5 consumers highlight

**Queries needed:**
- All camera_status records
- Filter by is_active
- Sort by bandwidth_mb_24h
- Search by record_key

---

### 3. **Bandwidth Analytics Page**
- 24h bandwidth line chart
- Per-camera bandwidth breakdown (stacked area chart)
- Peak hours heatmap
- Daily/Weekly/Monthly trends
- Export data

**Queries needed:**
- bandwidth_hourly (last 24h)
- bandwidth_hourly per camera (aggregated)
- Peak hours analysis
- Historical trends (30 days)

---

### 4. **Storage Trends Page**
- Disk usage over time (line chart)
- Forecast estimation
- Retention days calculator
- Alert history
- Capacity planning recommendations

**Queries needed:**
- storage_stats history (30 days)
- forecast history
- health status history
- Aggregated metrics

---

### 5. **Device Management Page**
- Block devices list (SSD/HDD)
- Partition breakdown
- Device health indicators
- Model & capacity info

**Queries needed:**
- All block_device records
- Filter by device_type
- JSON query for partitions

---

## Performance Optimization

### Index Strategy
✅ **GIN index on JSONB** - Fast JSON queries  
✅ **Composite index** (record_type, record_date) - Time-series queries  
✅ **Unique index** (record_type, record_key) - Current state queries  
✅ **B-tree index** on created_at - Historical queries  

### Query Performance
- **Current state:** 1-5ms (indexed direct lookup)
- **Time-series (24h):** 5-15ms (date index)
- **Aggregation (30 days):** 20-50ms (depends on data volume)
- **JSON field queries:** 10-30ms (GIN index)

### Scaling Considerations
- Partition `storage_records` by `record_date` (monthly) for large datasets
- Use materialized views for complex aggregations
- Archive old data (>90 days) to separate table

---

## Quick Reference

| Record Type | record_key | record_date | Update Strategy | Retention |
|-------------|------------|-------------|-----------------|-----------|
| storage_stats | NULL | NULL | Insert | 7 days |
| camera_status | camera_name | NULL | Upsert | Current only |
| bandwidth_hourly | hour (00-23) | date | Insert | 30 days |
| forecast | NULL | NULL | Insert | 7 days |
| health | NULL | NULL | Insert | 7 days |
| block_device | device_name | NULL | Upsert | Current only |
| active_cameras_summary | NULL | NULL | Insert | 7 days |

---

**Architecture completed for single-table solution!** 🚀

**Mục đích:** Lưu thống kê dung lượng disk chính của NVR

**Endpoint:** `GET /api/v1/storage` → `storage`

| Column        | Type          | Description                    | Example         |
|--------------|---------------|--------------------------------|-----------------|
| id           | SERIAL PK     | Primary key                    | 1               |
| device       | VARCHAR(255)  | Device path                    | /dev/sdb1       |
| mount_point  | VARCHAR(255)  | Mount point                    | /var/lib/nxstorage |
| total_gb     | DECIMAL(10,2) | Total disk size (GB)           | 3600.0          |
| used_gb      | DECIMAL(10,2) | Used space (GB)                | 1000.0          |
| free_gb      | DECIMAL(10,2) | Free space (GB)                | 2600.0          |
| percent      | INTEGER       | Usage percentage (0-100)       | 24              |
| size_human   | VARCHAR(50)   | Human readable total           | 3.6T            |
| used_human   | VARCHAR(50)   | Human readable used            | 826G            |
| avail_human  | VARCHAR(50)   | Human readable available       | 2.6T            |
| created_at   | TIMESTAMP     | Record timestamp               | NOW()           |

**Indexes:**
```sql
CREATE INDEX idx_storage_stats_created ON storage_stats(created_at DESC);
CREATE INDEX idx_storage_stats_device ON storage_stats(device);
```

**Sample Data:**
```json
{
    "device": "/dev/sdb1",
    "mount_point": "/var/lib/nxstorage",
    "total_gb": 3600.0,
    "used_gb": 1000.0,
    "free_gb": 2600.0,
    "percent": 24,
    "size_human": "3.6T",
    "used_human": "826G",
    "avail_human": "2.6T"
}
```

---

## 2. bandwidth_hourly

**Mục đích:** Lưu tổng băng thông recording theo từng giờ trong ngày

**Endpoint:** `GET /api/v1/storage/bandwidth` → `hourly`

| Column     | Type          | Description                | Example    |
|-----------|---------------|----------------------------|------------|
| id        | SERIAL PK     | Primary key                | 1          |
| hour      | VARCHAR(2)    | Hour of day (00-23)        | 11         |
| date      | DATE          | Date                       | 2026-02-12 |
| total_mb  | DECIMAL(10,2) | Total bandwidth (MB)       | 206.97     |
| created_at| TIMESTAMP     | Record timestamp           | NOW()      |

**Indexes:**
```sql
CREATE INDEX idx_bandwidth_hourly_date ON bandwidth_hourly(date DESC, hour DESC);
CREATE UNIQUE INDEX idx_bandwidth_hourly_unique ON bandwidth_hourly(date, hour);
```

**Sample Data:**
```json
{
    "11": {
        "total_mb": 206.97
    },
    "10": {
        "total_mb": 1475.78
    }
}
```

---

## 3. bandwidth_camera_hourly

**Mục đích:** Chi tiết băng thông từng camera trong từng giờ

**Endpoint:** `GET /api/v1/storage/bandwidth` → `hourly[hour].cameras`

| Column              | Type          | Description                    | Example      |
|--------------------|---------------|--------------------------------|--------------|
| id                 | SERIAL PK     | Primary key                    | 1            |
| bandwidth_hourly_id| INTEGER       | FK to bandwidth_hourly         | 1            |
| camera_name        | VARCHAR(100)  | Camera identifier              | XUAN_HOA_IN  |
| bandwidth_mb       | DECIMAL(10,2) | Bandwidth for this camera (MB) | 123.35       |
| created_at         | TIMESTAMP     | Record timestamp               | NOW()        |

**Foreign Keys:**
```sql
FOREIGN KEY (bandwidth_hourly_id) REFERENCES bandwidth_hourly(id) ON DELETE CASCADE
```

**Indexes:**
```sql
CREATE INDEX idx_bw_camera_hourly_camera ON bandwidth_camera_hourly(camera_name);
CREATE INDEX idx_bw_camera_hourly_bw ON bandwidth_camera_hourly(bandwidth_hourly_id);
CREATE UNIQUE INDEX idx_bw_camera_hourly_unique ON bandwidth_camera_hourly(bandwidth_hourly_id, camera_name);
```

**Sample Data:**
```json
{
    "11": {
        "cameras": {
            "23": 9.99,
            "CAM_235": 63.39,
            "XUAN_HOA_IN": 123.35,
            "236": 10.24
        }
    }
}
```

---

## 4. camera_status

**Mục đích:** Trạng thái recording và bandwidth của từng camera

**Endpoint:** `GET /api/v1/storage/cameras` → `cameras[]`

| Column           | Type          | Description                      | Example                  |
|-----------------|---------------|----------------------------------|--------------------------|
| id              | SERIAL PK     | Primary key                      | 1                        |
| camera_name     | VARCHAR(100)  | Camera identifier (unique)       | XUAN_HOA_IN              |
| last_modified   | TIMESTAMP     | Last recording file timestamp    | 2026-02-12T11:08:40.372  |
| seconds_ago     | INTEGER       | Seconds since last recording     | 3                        |
| bandwidth_mb_24h| DECIMAL(10,2) | Total 24h bandwidth (MB)         | 13330.78                 |
| bandwidth_gb_24h| DECIMAL(10,2) | Total 24h bandwidth (GB)         | 13.02                    |
| is_active       | BOOLEAN       | Active if seconds_ago <= 120     | true                     |
| created_at      | TIMESTAMP     | Record created                   | NOW()                    |
| updated_at      | TIMESTAMP     | Record updated                   | NOW()                    |

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_camera_status_name ON camera_status(camera_name);
CREATE INDEX idx_camera_status_active ON camera_status(is_active);
CREATE INDEX idx_camera_status_bw ON camera_status(bandwidth_mb_24h DESC);
CREATE INDEX idx_camera_status_active_bw ON camera_status(is_active, bandwidth_mb_24h DESC);
```

**Sample Data:**
```json
{
    "camera": "XUAN_HOA_IN",
    "last_modified": "2026-02-12T11:08:40.372641",
    "seconds_ago": 3,
    "bandwidth_mb_24h": 13330.78,
    "bandwidth_gb_24h": 13.02
}
```

**Business Logic:**
- Camera is **active** if `seconds_ago <= 120` (2 minutes)
- Camera is **inactive** if `seconds_ago > 120`
- Sort by `bandwidth_mb_24h DESC` to show top consumers first

---

## 5. storage_forecast

**Mục đích:** Dự báo storage dựa trên usage hiện tại

**Endpoint:** `GET /api/v1/storage/forecast` → `forecast`

| Column              | Type          | Description                    | Example                  |
|--------------------|---------------|--------------------------------|--------------------------|
| id                 | SERIAL PK     | Primary key                    | 1                        |
| avg_gb_per_hour    | DECIMAL(10,2) | Average GB written per hour    | 1.06                     |
| avg_gb_per_day     | DECIMAL(10,2) | Average GB written per day     | 25.35                    |
| hours_until_full   | INTEGER       | Hours until disk full          | 2461                     |
| days_until_full    | INTEGER       | Days until disk full           | 102                      |
| estimated_full_date| TIMESTAMP     | Estimated date when disk full  | 2026-05-26T00:08:59.311  |
| retention_days     | INTEGER       | Days of recording retention    | 142                      |
| created_at         | TIMESTAMP     | Record timestamp               | NOW()                    |

**Indexes:**
```sql
CREATE INDEX idx_forecast_created ON storage_forecast(created_at DESC);
```

**Sample Data:**
```json
{
    "avg_gb_per_hour": 1.06,
    "avg_gb_per_day": 25.35,
    "hours_until_full": 2461,
    "days_until_full": 102,
    "estimated_full_date": "2026-05-26T00:08:59.311185",
    "retention_days": 142
}
```

**Calculation Logic:**
- `avg_gb_per_hour` = Total 24h bandwidth / 24
- `avg_gb_per_day` = avg_gb_per_hour * 24
- `hours_until_full` = free_gb / avg_gb_per_hour
- `days_until_full` = hours_until_full / 24
- `retention_days` = total_gb / avg_gb_per_day

---

## 6. storage_health

**Mục đích:** Đánh giá sức khỏe tổng thể của storage system

**Endpoint:** `GET /api/v1/storage/health` → `health`

| Column         | Type        | Description                            | Example                       |
|---------------|-------------|----------------------------------------|-------------------------------|
| id            | SERIAL PK   | Primary key                            | 1                             |
| status        | VARCHAR(20) | Health status                          | healthy                       |
| message       | TEXT        | Detailed message                       | ✅ Disk storage is healthy.   |
| disk_percent  | INTEGER     | Current disk usage percentage          | 24                            |
| active_cameras| INTEGER     | Number of active cameras               | 4                             |
| total_cameras | INTEGER     | Total number of cameras                | 5                             |
| created_at    | TIMESTAMP   | Record timestamp                       | NOW()                         |

**Status Values:**
- `healthy` - disk_percent < 70%
- `attention` - disk_percent 70-79%
- `warning` - disk_percent 80-89%
- `critical` - disk_percent >= 90%
- `unknown` - Cannot determine status

**Indexes:**
```sql
CREATE INDEX idx_health_created ON storage_health(created_at DESC);
CREATE INDEX idx_health_status ON storage_health(status);
```

**Sample Data:**
```json
{
    "status": "healthy",
    "message": "✅ Disk storage is healthy.",
    "disk_percent": 24,
    "active_cameras": 4,
    "total_cameras": 5
}
```

---

## 7. block_devices

**Mục đích:** Thông tin ổ cứng vật lý (SSD/HDD)

**Endpoint:** `GET /api/v1/storage/block-devices` → `devices[]`

| Column      | Type          | Description                    | Example            |
|------------|---------------|--------------------------------|--------------------|
| id         | SERIAL PK     | Primary key                    | 1                  |
| device_name| VARCHAR(50)   | Device name (unique)           | sdb                |
| device_path| VARCHAR(255)  | Full device path               | /dev/sdb           |
| device_type| VARCHAR(10)   | Device type                    | HDD                |
| size_bytes | BIGINT        | Size in bytes                  | 4000787030016      |
| size_gb    | DECIMAL(10,2) | Size in GB                     | 3726.02            |
| size_human | VARCHAR(50)   | Human readable size            | 3.64 TB            |
| model      | VARCHAR(255)  | Device model                   | USB 3.0            |
| is_primary | BOOLEAN       | Primary storage device         | true               |
| created_at | TIMESTAMP     | Record created                 | NOW()              |
| updated_at | TIMESTAMP     | Record updated                 | NOW()              |

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_block_devices_name ON block_devices(device_name);
CREATE INDEX idx_block_devices_type ON block_devices(device_type);
CREATE INDEX idx_block_devices_primary ON block_devices(is_primary);
```

**Sample Data:**
```json
{
    "name": "sdb",
    "device": "/dev/sdb",
    "type": "HDD",
    "size_bytes": 4000787030016,
    "size_gb": 3726.02,
    "size_human": "3.64 TB",
    "model": "USB 3.0",
    "is_primary": true
}
```

**Device Types:**
- `SSD` - Solid State Drive (ROTA=0)
- `HDD` - Hard Disk Drive (ROTA=1)

---

## 8. device_partitions

**Mục đích:** Phân vùng của các ổ cứng

**Endpoint:** `GET /api/v1/storage/block-devices` → `devices[].partitions[]`

| Column          | Type          | Description                    | Example            |
|----------------|---------------|--------------------------------|--------------------|
| id             | SERIAL PK     | Primary key                    | 1                  |
| block_device_id| INTEGER       | FK to block_devices            | 2                  |
| partition_name | VARCHAR(50)   | Partition name (unique)        | sdb1               |
| mount_point    | VARCHAR(255)  | Mount point                    | /var/lib/nxstorage |
| size_gb        | DECIMAL(10,2) | Partition size (GB)            | 3726.02            |
| fstype         | VARCHAR(50)   | Filesystem type                | ext4               |
| created_at     | TIMESTAMP     | Record timestamp               | NOW()              |

**Foreign Keys:**
```sql
FOREIGN KEY (block_device_id) REFERENCES block_devices(id) ON DELETE CASCADE
```

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_partitions_name ON device_partitions(partition_name);
CREATE INDEX idx_partitions_device ON device_partitions(block_device_id);
CREATE INDEX idx_partitions_mount ON device_partitions(mount_point);
```

**Sample Data:**
```json
{
    "name": "sdb1",
    "mount": "/var/lib/nxstorage",
    "size_gb": 3726.02,
    "fstype": "ext4"
}
```

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│  storage_stats      │
│  (Latest snapshot)  │
└─────────────────────┘

┌─────────────────────┐       ┌──────────────────────────┐
│  bandwidth_hourly   │◄─────┤ bandwidth_camera_hourly  │
│  (Time series)      │  1:N  │  (Detail per camera)     │
└─────────────────────┘       └──────────────────────────┘

┌─────────────────────┐
│  camera_status      │
│  (Current state)    │
└─────────────────────┘

┌─────────────────────┐
│  storage_forecast   │
│  (Latest snapshot)  │
└─────────────────────┘

┌─────────────────────┐
│  storage_health     │
│  (Latest snapshot)  │
└─────────────────────┘

┌─────────────────────┐       ┌──────────────────────┐
│  block_devices      │◄─────┤ device_partitions    │
│  (Physical drives)  │  1:N  │  (Partitions)        │
└─────────────────────┘       └──────────────────────┘
```

---

## API Endpoint Mapping

| Endpoint                            | Tables Used                                          |
|------------------------------------|------------------------------------------------------|
| `GET /api/v1/storage`              | All tables (complete overview)                       |
| `GET /api/v1/storage/bandwidth`    | bandwidth_hourly, bandwidth_camera_hourly            |
| `GET /api/v1/storage/cameras`      | camera_status (sorted by bandwidth_mb_24h DESC)      |
| `GET /api/v1/storage/forecast`     | storage_forecast (latest record)                     |
| `GET /api/v1/storage/health`       | storage_health (latest record)                       |
| `GET /api/v1/storage/block-devices`| block_devices, device_partitions                     |

---

## Data Retention Policy

**Recommended retention periods:**

| Table                      | Retention | Strategy                              |
|---------------------------|-----------|---------------------------------------|
| storage_stats             | 30 days   | Keep daily snapshots                  |
| bandwidth_hourly          | 30 days   | Rolling window                        |
| bandwidth_camera_hourly   | 30 days   | Cascade delete with bandwidth_hourly  |
| camera_status             | Current   | Update in place (latest state only)   |
| storage_forecast          | 7 days    | Keep recent history                   |
| storage_health            | 7 days    | Keep recent history                   |
| block_devices             | Current   | Update in place when hardware changes |
| device_partitions         | Current   | Cascade with block_devices            |

---

## Performance Optimization

### Composite Indexes
```sql
-- Camera sorting by active status and bandwidth
CREATE INDEX idx_camera_status_active_bw 
ON camera_status(is_active, bandwidth_mb_24h DESC);

-- Recent bandwidth data
CREATE INDEX idx_bandwidth_hourly_recent 
ON bandwidth_hourly(date DESC, hour DESC) 
WHERE date >= CURRENT_DATE - INTERVAL '7 days';
```

### Materialized Views (Optional for Dashboard)
```sql
-- Active cameras summary
CREATE MATERIALIZED VIEW mv_active_cameras_summary AS
SELECT 
    COUNT(*) FILTER (WHERE is_active = true) as active_count,
    COUNT(*) FILTER (WHERE is_active = false) as inactive_count,
    SUM(bandwidth_mb_24h) as total_bandwidth_mb,
    MAX(last_modified) as latest_recording
FROM camera_status;

-- Refresh every 1 minute
CREATE UNIQUE INDEX ON mv_active_cameras_summary(active_count);
```

---

## Database Setup Commands

### PostgreSQL
```sql
-- Create database
CREATE DATABASE smart_vms_storage;

-- Create user
CREATE USER storage_service WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE smart_vms_storage TO storage_service;

-- Enable extensions (if needed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
```

### Connection String
```bash
DATABASE_URL="postgresql://storage_service:your_password@localhost:5432/smart_vms_storage"
```

---

## Notes

1. **Time Series Data**: `bandwidth_hourly` và `bandwidth_camera_hourly` là time series data, nên cân nhắc dùng partitioning hoặc TimescaleDB nếu data lớn

2. **Current State Tables**: `camera_status`, `block_devices`, `device_partitions` chỉ lưu latest state, update in-place

3. **Snapshot Tables**: `storage_stats`, `storage_forecast`, `storage_health` có thể lưu historical data để trending

4. **Cascade Deletes**: Khi xóa `bandwidth_hourly` thì tự động xóa `bandwidth_camera_hourly`. Tương tự với `block_devices` và `device_partitions`

5. **Boolean Logic**: `camera_status.is_active` được derive từ `seconds_ago <= 120` (có thể dùng trigger hoặc computed column)

6. **Timezone**: Lưu ý API sử dụng local timezone cho response nhưng data trong DB nên là UTC

---

## Testing Queries

```sql
-- Get latest storage overview
SELECT * FROM storage_stats 
ORDER BY created_at DESC LIMIT 1;

-- Get top 5 cameras by bandwidth
SELECT camera_name, bandwidth_gb_24h 
FROM camera_status 
ORDER BY bandwidth_mb_24h DESC 
LIMIT 5;

-- Get active cameras
SELECT camera_name, seconds_ago 
FROM camera_status 
WHERE is_active = true;

-- Get bandwidth for last 24 hours
SELECT hour, total_mb 
FROM bandwidth_hourly 
WHERE date >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY date DESC, hour DESC;

-- Get latest health status
SELECT * FROM storage_health 
ORDER BY created_at DESC LIMIT 1;

-- Get all block devices with partitions
SELECT 
    bd.device_name,
    bd.device_type,
    bd.size_human,
    dp.partition_name,
    dp.mount_point
FROM block_devices bd
LEFT JOIN device_partitions dp ON bd.id = dp.block_device_id;
```

---

## Single Table Solution (Nếu chỉ có thể thêm 1 bảng)

Nếu hệ thống chỉ cho phép thêm **1 bảng duy nhất**, có 2 cách gộp:

---

### **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Storage Service API (port 31070)                               │
│  ├─ GET /api/v1/storage          → Full data                    │
│  ├─ GET /api/v1/storage/cameras  → Camera list                  │
│  ├─ GET /api/v1/storage/health   → Health status                │
│  └─ ...                                                          │
│                   │                                              │
│                   │ (Call every 15s)                             │
│                   ▼                                              │
│  Sync Worker / Cron Job                                          │
│  ├─ Fetch API responses                                          │
│  ├─ Parse JSON data                                              │
│  └─ Insert/Update DB (JSONB storage)                             │
│                   │                                              │
│                   ▼                                              │
│  PostgreSQL Database                                             │
│  └─ storage_records (JSONB columns)                              │
│                   │                                              │
│                   │ (Query only)                                 │
│                   ▼                                              │
│  Backend API (Your main API)                                     │
│  ├─ GET /api/storage          → Query from DB                    │
│  ├─ GET /api/cameras          → Query from DB                    │
│  ├─ GET /api/storage/health   → Query from DB                    │
│  └─ ...                                                          │
│                   │                                              │
│                   ▼                                              │
│  Frontend / Clients                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- ✅ Backend **KHÔNG** gọi Storage Service API trực tiếp
- ✅ Backend **CHỈ** query từ database
- ✅ Sync worker chạy background, gọi API định kỳ và sync vào DB
- ✅ Raw JSON từ API được lưu nguyên vào JSONB column

---

### **Phương án 1: Universal Storage Table với JSONB (⭐ Recommended)**

Một bảng universal dùng JSONB để lưu **raw API response**, phân biệt data bằng `record_type`:

```sql
CREATE TABLE storage_records (
    id SERIAL PRIMARY KEY,
    record_type VARCHAR(50) NOT NULL,   -- Loại data: 'storage_stats', 'camera_status', 'bandwidth_hourly', etc.
    record_key VARCHAR(100),             -- Identifier: camera name, hour, device name
    record_date DATE,                    -- Để query theo ngày (cho bandwidth)
    data JSONB NOT NULL,                 -- Toàn bộ data trong JSON
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_storage_records_type ON storage_records(record_type);
CREATE INDEX idx_storage_records_type_date ON storage_records(record_type, record_date DESC);
CREATE INDEX idx_storage_records_key ON storage_records(record_type, record_key);
CREATE INDEX idx_storage_records_data ON storage_records USING GIN(data);  -- For JSON queries
CREATE INDEX idx_storage_records_created ON storage_records(created_at DESC);

-- Optional: Unique constraint cho current state records
CREATE UNIQUE INDEX idx_storage_records_current_state 
ON storage_records(record_type, record_key) 
WHERE record_key IS NOT NULL AND record_type IN ('camera_status', 'block_device');
```

**Record Types:**
- `storage_stats` - Thống kê disk
- `camera_status` - Trạng thái camera
- `bandwidth_hourly` - Băng thông theo giờ
- `forecast` - Dự báo storage
- `health` - Sức khỏe hệ thống
- `block_device` - Ổ cứng vật lý
- `partition` - Phân vùng disk

**Ví dụ Insert Data:**

```sql
-- 1. Storage Stats
INSERT INTO storage_records (record_type, data) VALUES (
    'storage_stats',
    '{"device": "/dev/sdb1", "mount_point": "/var/lib/nxstorage", "total_gb": 3600.0, "used_gb": 1000.0, "free_gb": 2600.0, "percent": 24, "size_human": "3.6T", "used_human": "826G", "avail_human": "2.6T"}'::jsonb
);

-- 2. Camera Status (với record_key để query nhanh)
INSERT INTO storage_records (record_type, record_key, data) VALUES (
    'camera_status',
    'XUAN_HOA_IN',
    '{"camera_name": "XUAN_HOA_IN", "last_modified": "2026-02-12T11:08:40.372641", "seconds_ago": 3, "bandwidth_mb_24h": 13330.78, "bandwidth_gb_24h": 13.02, "is_active": true}'::jsonb
) ON CONFLICT (record_type, record_key) 
DO UPDATE SET 
    data = EXCLUDED.data,
    updated_at = NOW();

-- 3. Bandwidth Hourly (nested cameras data)
INSERT INTO storage_records (record_type, record_key, record_date, data) VALUES (
    'bandwidth_hourly',
    '11',
    '2026-02-12',
    '{"hour": "11", "total_mb": 206.97, "cameras": {"XUAN_HOA_IN": 123.35, "CAM_235": 63.39, "23": 9.99, "236": 10.24}}'::jsonb
);

-- 4. Storage Forecast
INSERT INTO storage_records (record_type, data) VALUES (
    'forecast',
    '{"avg_gb_per_hour": 1.06, "avg_gb_per_day": 25.35, "hours_until_full": 2461, "days_until_full": 102, "estimated_full_date": "2026-05-26T00:08:59.311185", "retention_days": 142}'::jsonb
);

-- 5. Storage Health
INSERT INTO storage_records (record_type, data) VALUES (
    'health',
    '{"status": "healthy", "message": "✅ Disk storage is healthy.", "disk_percent": 24, "active_cameras": 4, "total_cameras": 5}'::jsonb
);

-- 6. Block Device (với partitions nested)
INSERT INTO storage_records (record_type, record_key, data) VALUES (
    'block_device',
    'sdb',
    '{"name": "sdb", "device": "/dev/sdb", "type": "HDD", "size_bytes": 4000787030016, "size_gb": 3726.02, "size_human": "3.64 TB", "model": "USB 3.0", "is_primary": true, "partitions": [{"name": "sdb1", "mount": "/var/lib/nxstorage", "size_gb": 3726.02, "fstype": "ext4"}]}'::jsonb
);
```

**Query Examples:**

```sql
-- Get latest storage stats
SELECT data 
FROM storage_records 
WHERE record_type = 'storage_stats' 
ORDER BY created_at DESC 
LIMIT 1;

-- Get all active cameras
SELECT 
    record_key as camera_name,
    data->>'bandwidth_mb_24h' as bandwidth_mb,
    data->>'seconds_ago' as seconds_ago
FROM storage_records 
WHERE record_type = 'camera_status' 
    AND (data->>'is_active')::boolean = true
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC;

-- Get bandwidth for specific hour
SELECT data 
FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
    AND record_key = '11' 
    AND record_date = '2026-02-12';

-- Get bandwidth for last 24 hours
SELECT 
    record_key as hour,
    data->>'total_mb' as total_mb,
    data->'cameras' as cameras
FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
    AND record_date >= CURRENT_DATE - INTERVAL '1 day'
ORDER BY record_date DESC, record_key DESC;

-- Get latest health status
SELECT data 
FROM storage_records 
WHERE record_type = 'health' 
ORDER BY created_at DESC 
LIMIT 1;

-- Get all block devices with JSON query
SELECT 
    record_key as device_name,
    data->>'type' as device_type,
    data->>'size_human' as size,
    data->'partitions' as partitions
FROM storage_records 
WHERE record_type = 'block_device';

-- Top 5 cameras by bandwidth (JSON query)
SELECT 
    record_key as camera_name,
    (data->>'bandwidth_gb_24h')::numeric as bandwidth_gb
FROM storage_records 
WHERE record_type = 'camera_status'
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC
LIMIT 5;

-- Filter cameras by bandwidth threshold
SELECT 
    record_key as camera_name,
    data->>'bandwidth_gb_24h' as bandwidth_gb
FROM storage_records 
WHERE record_type = 'camera_status'
    AND (data->>'bandwidth_mb_24h')::numeric > 1000
ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC;
```

**Cleanup Old Data:**

```sql
-- Delete bandwidth data older than 30 days
DELETE FROM storage_records 
WHERE record_type = 'bandwidth_hourly' 
    AND record_date < CURRENT_DATE - INTERVAL '30 days';

-- Delete old forecast/health snapshots (keep last 7 days)
DELETE FROM storage_records 
WHERE record_type IN ('forecast', 'health', 'storage_stats')
    AND created_at < NOW() - INTERVAL '7 days';
```

---

### **Phương án 2: Flat Table với nhiều columns**

Gộp tất cả fields vào 1 bảng, columns không dùng để NULL:

```sql
CREATE TABLE storage_data (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,      -- Loại data
    
    -- Common fields
    record_date DATE,
    record_hour VARCHAR(2),
    entity_name VARCHAR(100),             -- Camera name, device name, etc.
    
    -- Storage stats fields
    device VARCHAR(255),
    mount_point VARCHAR(255),
    total_gb DECIMAL(10,2),
    used_gb DECIMAL(10,2),
    free_gb DECIMAL(10,2),
    usage_percent INTEGER,
    size_human VARCHAR(50),
    used_human VARCHAR(50),
    avail_human VARCHAR(50),
    
    -- Camera fields
    is_active BOOLEAN,
    last_modified TIMESTAMP,
    seconds_ago INTEGER,
    bandwidth_mb DECIMAL(10,2),
    bandwidth_gb DECIMAL(10,2),
    
    -- Forecast fields
    avg_gb_per_hour DECIMAL(10,2),
    avg_gb_per_day DECIMAL(10,2),
    hours_until_full INTEGER,
    days_until_full INTEGER,
    estimated_full_date TIMESTAMP,
    retention_days INTEGER,
    
    -- Health fields
    health_status VARCHAR(20),
    health_message TEXT,
    active_camera_count INTEGER,
    total_camera_count INTEGER,
    
    -- Block device fields
    device_type VARCHAR(10),              -- SSD/HDD
    size_bytes BIGINT,
    device_model VARCHAR(255),
    is_primary BOOLEAN,
    
    -- Partition fields
    partition_name VARCHAR(50),
    fstype VARCHAR(50),
    
    -- Extra data (cho fields khác không lường trước)
    extra_data JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_storage_data_type ON storage_data(data_type);
CREATE INDEX idx_storage_data_type_date ON storage_data(data_type, record_date DESC);
CREATE INDEX idx_storage_data_entity ON storage_data(data_type, entity_name);
CREATE INDEX idx_storage_data_created ON storage_data(created_at DESC);
CREATE INDEX idx_storage_data_bandwidth ON storage_data(bandwidth_mb DESC) WHERE data_type = 'camera_status';
```

**Ví dụ Insert:**

```sql
-- Storage Stats
INSERT INTO storage_data (
    data_type, device, mount_point, total_gb, used_gb, free_gb, 
    usage_percent, size_human, used_human, avail_human
) VALUES (
    'storage_stats', '/dev/sdb1', '/var/lib/nxstorage', 3600.0, 1000.0, 2600.0,
    24, '3.6T', '826G', '2.6T'
);

-- Camera Status
INSERT INTO storage_data (
    data_type, entity_name, last_modified, seconds_ago, 
    bandwidth_mb, bandwidth_gb, is_active
) VALUES (
    'camera_status', 'XUAN_HOA_IN', '2026-02-12T11:08:40', 3,
    13330.78, 13.02, true
);

-- Forecast
INSERT INTO storage_data (
    data_type, avg_gb_per_hour, avg_gb_per_day, hours_until_full,
    days_until_full, estimated_full_date, retention_days
) VALUES (
    'forecast', 1.06, 25.35, 2461, 102, '2026-05-26T00:08:59', 142
);
```

---

### **So sánh 2 phương án:**

| Tiêu chí | Phương án 1 (JSONB) | Phương án 2 (Flat) |
|----------|--------------------|--------------------|
| **Flexibility** | ⭐⭐⭐⭐⭐ Cực kỳ linh hoạt, dễ thêm fields | ⭐⭐ Phải ALTER TABLE mỗi khi thêm field |
| **Storage Efficiency** | ⭐⭐⭐⭐ Compact, không có NULL columns | ⭐⭐ Rất nhiều NULL values |
| **Query Performance** | ⭐⭐⭐ Cần cast và GIN index | ⭐⭐⭐⭐ Query trực tiếp nhanh hơn |
| **Maintainability** | ⭐⭐⭐⭐⭐ Dễ maintain, không cần migration | ⭐⭐ Cần migration khi thay đổi structure |
| **Code Complexity** | ⭐⭐⭐ Cần parse JSON ở application layer | ⭐⭐⭐⭐ Query SQL đơn giản |
| **Data Integrity** | ⭐⭐⭐ Phụ thuộc vào validation ở app | ⭐⭐⭐⭐ Constraints ở DB level |
| **Scalability** | ⭐⭐⭐⭐ Scale tốt với partition | ⭐⭐⭐ OK nhưng nhiều NULL |

### **Recommendation: Phương án 1 (JSONB) ⭐**

**Lý do chọn JSONB:**

✅ **Flexibility cao** - Dễ dàng thêm/sửa fields mà không cần ALTER TABLE  
✅ **Storage hiệu quả** - Không có hàng loạt NULL columns  
✅ **Schema evolution** - API thay đổi không ảnh hưởng đến DB  
✅ **PostgreSQL JSONB** - Performance rất tốt với GIN index  
✅ **Maintainability** - Ít phải migration, thay đổi ở app layer  

**Khi nào dùng Flat Table:**
- Khi cần query performance tối đa
- Khi schema rất ổn định, ít thay đổi
- Khi cần data integrity ở DB level
- Khi team không quen với JSONB

---

---

### **Sync Worker Implementation**

**Python Worker để sync từ Storage Service API vào Database:**

```python
"""
Sync Worker - Fetch data from Storage Service API và lưu vào DB
Chạy mỗi 15 giây (hoặc theo POLLING_INTERVAL)
"""
import asyncio
import httpx
import asyncpg
from datetime import datetime, date
import json

STORAGE_API_URL = "http://localhost:31070"
DATABASE_URL = "postgresql://user:pass@localhost/smart_vms"
POLLING_INTERVAL = 15  # seconds

class StorageSyncWorker:
    def __init__(self):
        self.db_pool = None
        self.http_client = httpx.AsyncClient(timeout=10.0)
    
    async def init_db(self):
        """Initialize database connection pool"""
        self.db_pool = await asyncpg.create_pool(DATABASE_URL)
    
    async def save_raw_response(self, record_type: str, data: dict, 
                                record_key: str = None, record_date: date = None):
        """
        Lưu RAW API response vào database
        
        Args:
            record_type: Loại data (storage_stats, camera_status, etc.)
            data: Raw JSON response từ API
            record_key: Optional key (camera name, hour, etc.)
            record_date: Optional date (cho bandwidth data)
        """
        async with self.db_pool.acquire() as conn:
            if record_key:
                # Upsert for records with key (camera_status, block_device)
                await conn.execute("""
                    INSERT INTO storage_records (record_type, record_key, record_date, data)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (record_type, record_key) 
                    DO UPDATE SET 
                        data = EXCLUDED.data,
                        record_date = EXCLUDED.record_date,
                        updated_at = NOW()
                """, record_type, record_key, record_date, json.dumps(data))
            else:
                # Insert snapshot data (storage_stats, forecast, health)
                await conn.execute("""
                    INSERT INTO storage_records (record_type, data)
                    VALUES ($1, $2)
                """, record_type, json.dumps(data))
    
    async def sync_storage_overview(self):
        """Sync GET /api/v1/storage - Complete overview"""
        try:
            response = await self.http_client.get(f"{STORAGE_API_URL}/api/v1/storage")
            if response.status_code == 200:
                data = response.json()
                
                # 1. Save storage stats
                if data.get('storage'):
                    await self.save_raw_response('storage_stats', data['storage'])
                
                # 2. Save forecast
                if data.get('forecast'):
                    await self.save_raw_response('forecast', data['forecast'])
                
                # 3. Save health
                if data.get('health'):
                    await self.save_raw_response('health', data['health'])
                
                # 4. Save active cameras info
                if data.get('active_cameras'):
                    await self.save_raw_response('active_cameras_summary', data['active_cameras'])
                
                print(f"✅ Synced storage overview at {datetime.now()}")
        except Exception as e:
            print(f"❌ Error syncing storage overview: {e}")
    
    async def sync_cameras(self):
        """Sync GET /api/v1/storage/cameras - Individual camera status"""
        try:
            response = await self.http_client.get(f"{STORAGE_API_URL}/api/v1/storage/cameras")
            if response.status_code == 200:
                data = response.json()
                
                # Save each camera as separate record
                for camera in data.get('cameras', []):
                    camera_name = camera.get('camera')
                    await self.save_raw_response(
                        record_type='camera_status',
                        record_key=camera_name,
                        data=camera
                    )
                
                print(f"✅ Synced {len(data.get('cameras', []))} cameras at {datetime.now()}")
        except Exception as e:
            print(f"❌ Error syncing cameras: {e}")
    
    async def sync_bandwidth(self):
        """Sync GET /api/v1/storage/bandwidth - Bandwidth data"""
        try:
            response = await self.http_client.get(f"{STORAGE_API_URL}/api/v1/storage/bandwidth")
            if response.status_code == 200:
                data = response.json()
                today = date.today()
                
                # Save hourly bandwidth (với nested cameras data)
                for hour, hour_data in data.get('hourly', {}).items():
                    await self.save_raw_response(
                        record_type='bandwidth_hourly',
                        record_key=hour,
                        record_date=today,
                        data=hour_data
                    )
                
                print(f"✅ Synced bandwidth data at {datetime.now()}")
        except Exception as e:
            print(f"❌ Error syncing bandwidth: {e}")
    
    async def sync_block_devices(self):
        """Sync GET /api/v1/storage/block-devices - Physical devices"""
        try:
            response = await self.http_client.get(f"{STORAGE_API_URL}/api/v1/storage/block-devices")
            if response.status_code == 200:
                data = response.json()
                
                # Save each block device
                for device in data.get('devices', []):
                    device_name = device.get('name')
                    await self.save_raw_response(
                        record_type='block_device',
                        record_key=device_name,
                        data=device  # Includes nested partitions
                    )
                
                print(f"✅ Synced {len(data.get('devices', []))} block devices at {datetime.now()}")
        except Exception as e:
            print(f"❌ Error syncing block devices: {e}")
    
    async def sync_all(self):
        """Sync all data from Storage Service API"""
        await asyncio.gather(
            self.sync_storage_overview(),
            self.sync_cameras(),
            self.sync_bandwidth(),
            self.sync_block_devices(),
            return_exceptions=True
        )
    
    async def run_polling(self):
        """Main polling loop - chạy mỗi POLLING_INTERVAL giây"""
        print(f"🚀 Storage Sync Worker started (polling every {POLLING_INTERVAL}s)")
        
        while True:
            try:
                await self.sync_all()
                await asyncio.sleep(POLLING_INTERVAL)
            except Exception as e:
                print(f"❌ Polling error: {e}")
                await asyncio.sleep(POLLING_INTERVAL)
    
    async def cleanup_old_data(self):
        """Cleanup old data (chạy mỗi ngày)"""
        async with self.db_pool.acquire() as conn:
            # Delete bandwidth older than 30 days
            await conn.execute("""
                DELETE FROM storage_records 
                WHERE record_type = 'bandwidth_hourly' 
                    AND record_date < CURRENT_DATE - INTERVAL '30 days'
            """)
            
            # Delete old snapshots (keep last 7 days)
            await conn.execute("""
                DELETE FROM storage_records 
                WHERE record_type IN ('storage_stats', 'forecast', 'health')
                    AND created_at < NOW() - INTERVAL '7 days'
            """)
            
            print(f"🧹 Cleaned up old data at {datetime.now()}")
    
    async def start(self):
        """Start the sync worker"""
        await self.init_db()
        
        # Start polling task
        polling_task = asyncio.create_task(self.run_polling())
        
        # Start daily cleanup task
        async def daily_cleanup():
            while True:
                await asyncio.sleep(86400)  # 24 hours
                await self.cleanup_old_data()
        
        cleanup_task = asyncio.create_task(daily_cleanup())
        
        # Wait for tasks
        await asyncio.gather(polling_task, cleanup_task)


# Run worker
if __name__ == "__main__":
    worker = StorageSyncWorker()
    asyncio.run(worker.start())
```

**Docker Compose Service:**

```yaml
# docker-compose.yml
services:
  storage_sync_worker:
    build: .
    container_name: storage_sync_worker
    environment:
      - STORAGE_API_URL=http://storage-service:31070
      - DATABASE_URL=postgresql://user:pass@postgres:5432/smart_vms
      - POLLING_INTERVAL=15
    depends_on:
      - postgres
      - storage-service
    restart: always
    command: python sync_worker.py
```

**Systemd Service (Linux):**

```ini
# /etc/systemd/system/storage-sync-worker.service
[Unit]
Description=Storage Sync Worker
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/smart_vms
ExecStart=/usr/bin/python3 /opt/smart_vms/sync_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

### **Backend API Implementation (Query từ DB thay vì gọi API)**

**Python/FastAPI Backend - CHỈ query DB, KHÔNG gọi Storage API:**

```python
"""
Backend API - Query từ Database (KHÔNG gọi Storage Service API)
"""
from fastapi import FastAPI, HTTPException
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

app = FastAPI()
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(
        "postgresql://user:pass@localhost/smart_vms"
    )

# ==================== ENDPOINTS ====================

@app.get("/api/storage")
async def get_storage():
    """
    Get complete storage information từ DATABASE
    Backend CHỈ query DB, KHÔNG gọi Storage Service API
    """
    async with db_pool.acquire() as conn:
        # Get latest storage stats
        storage_stats = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'storage_stats' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        # Get latest forecast
        forecast = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'forecast' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        # Get latest health
        health = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'health' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        # Get active cameras summary
        active_cameras = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'active_cameras_summary' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        # Get bandwidth hourly (last 24h)
        bandwidth_rows = await conn.fetch("""
            SELECT record_key, data 
            FROM storage_records 
            WHERE record_type = 'bandwidth_hourly' 
                AND record_date >= CURRENT_DATE - INTERVAL '1 day'
            ORDER BY record_date DESC, record_key DESC
        """)
        bandwidth_hourly = {row['record_key']: row['data'] for row in bandwidth_rows}
        
        # Get all block devices
        device_rows = await conn.fetch("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'block_device'
        """)
        block_devices = [row['data'] for row in device_rows]
        
        return {
            "storage": storage_stats,
            "forecast": forecast,
            "health": health,
            "active_cameras": active_cameras,
            "bandwidth_hourly": bandwidth_hourly,
            "block_devices": block_devices,
            "source": "database",  # Không phải từ API
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/cameras")
async def get_cameras():
    """Get all cameras with status và bandwidth từ DATABASE"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                record_key as camera_name,
                data,
                updated_at
            FROM storage_records 
            WHERE record_type = 'camera_status'
            ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC
        """)
        
        cameras = []
        for row in rows:
            camera_data = dict(row['data'])
            camera_data['last_updated'] = row['updated_at'].isoformat()
            cameras.append(camera_data)
        
        active_count = sum(1 for c in cameras if c.get('is_active'))
        
        return {
            "cameras": cameras,
            "active_count": active_count,
            "inactive_count": len(cameras) - active_count,
            "total_count": len(cameras),
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/cameras/{camera_name}")
async def get_camera_detail(camera_name: str):
    """Get specific camera detail từ DATABASE"""
    async with db_pool.acquire() as conn:
        camera_data = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'camera_status' 
                AND record_key = $1
        """, camera_name)
        
        if not camera_data:
            raise HTTPException(status_code=404, detail="Camera not found")
        
        return {
            "camera": camera_data,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/cameras/active")
async def get_active_cameras():
    """Get only active cameras từ DATABASE"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                record_key as camera_name,
                data
            FROM storage_records 
            WHERE record_type = 'camera_status' 
                AND (data->>'is_active')::boolean = true
            ORDER BY (data->>'bandwidth_mb_24h')::numeric DESC
        """)
        
        cameras = [dict(row['data']) for row in rows]
        
        return {
            "cameras": cameras,
            "count": len(cameras),
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/storage/health")
async def get_health():
    """Get storage health status từ DATABASE"""
    async with db_pool.acquire() as conn:
        health = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'health' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        return {
            "health": health,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/storage/forecast")
async def get_forecast():
    """Get storage forecast từ DATABASE"""
    async with db_pool.acquire() as conn:
        forecast = await conn.fetchval("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'forecast' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        return {
            "forecast": forecast,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/bandwidth/hourly")
async def get_bandwidth_hourly():
    """Get bandwidth by hour từ DATABASE"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                record_key as hour,
                data,
                record_date
            FROM storage_records 
            WHERE record_type = 'bandwidth_hourly' 
                AND record_date >= CURRENT_DATE - INTERVAL '1 day'
            ORDER BY record_date DESC, record_key DESC
        """)
        
        hourly_data = {}
        for row in rows:
            hourly_data[row['hour']] = {
                **row['data'],
                'date': row['record_date'].isoformat()
            }
        
        return {
            "hourly": hourly_data,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/bandwidth/cameras/{camera_name}")
async def get_camera_bandwidth(camera_name: str):
    """Get bandwidth history for specific camera"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                record_key as hour,
                record_date,
                data->'cameras'->>$1 as bandwidth_mb
            FROM storage_records 
            WHERE record_type = 'bandwidth_hourly' 
                AND record_date >= CURRENT_DATE - INTERVAL '7 days'
                AND data->'cameras' ? $1
            ORDER BY record_date DESC, record_key DESC
        """, camera_name)
        
        history = []
        for row in rows:
            if row['bandwidth_mb']:
                history.append({
                    'hour': row['hour'],
                    'date': row['record_date'].isoformat(),
                    'bandwidth_mb': float(row['bandwidth_mb'])
                })
        
        return {
            "camera": camera_name,
            "history": history,
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/devices")
async def get_block_devices():
    """Get all block devices từ DATABASE"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT data 
            FROM storage_records 
            WHERE record_type = 'block_device'
        """)
        
        devices = [row['data'] for row in rows]
        ssds = [d for d in devices if d.get('type') == 'SSD']
        hdds = [d for d in devices if d.get('type') == 'HDD']
        
        return {
            "devices": devices,
            "ssds": ssds,
            "hdds": hdds,
            "total_count": len(devices),
            "ssd_count": len(ssds),
            "hdd_count": len(hdds),
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/storage/stats/history")
async def get_storage_stats_history(days: int = 7):
    """Get storage stats history (trending)"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                data,
                created_at
            FROM storage_records 
            WHERE record_type = 'storage_stats'
                AND created_at >= NOW() - INTERVAL '1 day' * $1
            ORDER BY created_at DESC
        """, days)
        
        history = []
        for row in rows:
            history.append({
                **row['data'],
                'timestamp': row['created_at'].isoformat()
            })
        
        return {
            "history": history,
            "days": days,
            "count": len(history),
            "source": "database",
            "timestamp": datetime.now().isoformat()
        }
```

---

### **Deployment Architecture**

```
┌──────────────────────────────────────────────────────────────┐
│                       PRODUCTION SETUP                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Storage Service (Port 31070)                       │    │
│  │  - Scan filesystem every 15s                        │    │
│  │  - Calculate stats, forecast, health                │    │
│  │  - Expose API endpoints                             │    │
│  └───────────────────┬─────────────────────────────────┘    │
│                      │                                       │
│                      │ HTTP GET every 15s                    │
│                      ▼                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Sync Worker (Background Service)                   │    │
│  │  - Poll Storage Service API                         │    │
│  │  - Save raw JSON to PostgreSQL                      │    │
│  │  - Cleanup old data daily                           │    │
│  └───────────────────┬─────────────────────────────────┘    │
│                      │                                       │
│                      │ INSERT/UPDATE                         │
│                      ▼                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  PostgreSQL Database                                │    │
│  │  └─ storage_records (JSONB table)                   │    │
│  │     - record_type: 'camera_status'                  │    │
│  │     - record_key: camera name                       │    │
│  │     - data: {...raw JSON...}                        │    │
│  └───────────────────┬─────────────────────────────────┘    │
│                      │                                       │
│                      │ SELECT queries                        │
│                      ▼                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Backend API (Main Application)                     │    │
│  │  - GET /api/storage                                 │    │
│  │  - GET /api/cameras                                 │    │
│  │  - GET /api/storage/health                          │    │
│  │  *** KHÔNG gọi Storage Service API ***              │    │
│  │  *** CHỈ query từ PostgreSQL ***                    │    │
│  └───────────────────┬─────────────────────────────────┘    │
│                      │                                       │
│                      │ JSON response                         │
│                      ▼                                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Frontend / Mobile App / Clients                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Benefits của Architecture này:**

✅ **Decoupling** - Backend không phụ thuộc vào Storage Service uptime  
✅ **Performance** - Query DB nhanh hơn nhiều so với call API  
✅ **Caching** - Data đã có sẵn trong DB, không cần cache thêm  
✅ **Historical Data** - Có thể query history, trending  
✅ **Scalability** - Backend có thể scale độc lập, không ảnh hưởng Storage Service  
✅ **Fault Tolerance** - Storage Service down cũng không ảnh hưởng Backend API  

---

### **Example: Full Request Flow**

```plaintext
1. Frontend calls:
   GET http://your-backend.com/api/cameras

2. Backend API:
   - Query PostgreSQL: 
     SELECT data FROM storage_records 
     WHERE record_type = 'camera_status'
   - Parse JSON response
   - Return to frontend

3. Meanwhile (background):
   - Sync Worker gọi Storage Service API mỗi 15s
   - Lưu raw response vào PostgreSQL
   - Backend có data mới nhất để serve
```

**Latency Comparison:**

| Method | Average Latency | Notes |
|--------|----------------|-------|
| Backend → Storage API → Filesystem | 100-500ms | Slow, depends on filesystem scan |
| Backend → PostgreSQL (JSONB) | 5-20ms | ⚡ Rất nhanh |
| Backend → PostgreSQL (indexed query) | 1-5ms | ⚡⚡ Cực nhanh |

---

**Generated:** 2026-02-12  
**API Version:** 2.0.0  
**Service Port:** 31070

---

## Quick Summary

### **Full Setup (8 Tables) - Best Practice**
- ✅ Normalized schema
- ✅ Better data integrity
- ✅ Optimized for each data type
- ✅ Use if you have flexibility with database schema

### **Single Table (JSONB) - Constraint Solution**  
- ✅ Only 1 table needed: `storage_records`
- ✅ Flexible, easy to maintain
- ✅ Raw API responses stored as JSON
- ✅ **Architecture**: Storage Service API → Sync Worker → PostgreSQL → Backend API → Clients

### **Key Components**

1. **Storage Service** (port 31070)
   - Scans filesystem, calculates stats
   - Exposes REST API

2. **Sync Worker** (background service)
   - Polls Storage Service API every 15s
   - Saves raw JSON to PostgreSQL
   - Handles cleanup

3. **Backend API** (your main app)
   - **CHỈ query từ PostgreSQL**
   - **KHÔNG gọi Storage Service API**
   - Fast response (5-20ms)

4. **PostgreSQL Database**
   - 1 table: `storage_records` (JSONB)
   - Stores all data types
   - GIN indexes for fast JSON queries

### **Performance Benefits**
- Backend API latency: **5-20ms** (vs 100-500ms nếu gọi Storage API)
- Fault tolerant: Storage Service down không ảnh hưởng Backend
- Scalable: Backend có thể scale độc lập
- Historical data: Query trends, analytics từ DB

---

**Complete solution documented!** 🚀
