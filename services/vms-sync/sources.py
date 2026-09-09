from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

BLOB_KEYS = frozenset({'snapshot_base64', 'image', 'face_feature'})
ZERO_UUID = UUID('00000000-0000-0000-0000-000000000000')
TIME_MIN = datetime(2020, 1, 1, tzinfo=UTC)
AI_COLUMNS = (
    'event_time',
    'module',
    'event_type',
    'severity',
    'organization_id',
    'site_id',
    'iam_area_id',
    'iam_zone_id',
    'node_id',
    'node_path',
    'camera_id',
    'camera_code',
    'camera_name',
    'zone_id',
    'zone_name',
    'entity_type',
    'entity_id',
    'direction',
    'confidence',
    'person_id',
    'person_name',
    'license_plate',
    'snapshot_url',
    'video_clip_url',
    'attrs',
    'payload',
    'src_db',
    'src_table',
    'src_id',
    'created_at',
)


def _s(value: Any) -> str:
    if value is None:
        return ''
    return str(value)


def _i64(value: Any) -> int:
    if value is None or value == '':
        return 0
    return int(value)


def _f32(value: Any) -> float:
    if value is None or value == '':
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _uuid(value: Any) -> UUID:
    if value is None or value == '':
        return ZERO_UUID
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes | memoryview):
        return None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items() if k not in BLOB_KEYS}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return str(value)


def _payload_json(row: dict[str, Any]) -> str:
    data = {k: _jsonable(v) for k, v in row.items() if k not in BLOB_KEYS}
    return json.dumps(data, ensure_ascii=False, default=str)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith('{'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _event_times(
    event_time: Any, created_at: Any
) -> tuple[datetime, datetime, dict[str, str]]:
    created = _dt(created_at) or _dt(event_time) or datetime.now(UTC)
    event = _dt(event_time) or created
    attrs: dict[str, str] = {}
    now = datetime.now(UTC)
    if event < TIME_MIN or event > now + timedelta(days=1):
        attrs['time_suspect'] = '1'
    return event, created, attrs


def _base(
    *,
    row: dict[str, Any],
    module: str,
    event_type: str,
    src_db: str,
    src_table: str,
    time_col: str,
    created_col: str,
    extra_attrs: dict[str, str] | None = None,
) -> dict[str, Any]:
    event, created, attrs = _event_times(row.get(time_col), row.get(created_col))
    if extra_attrs:
        attrs.update(extra_attrs)
    return {
        'event_time': event,
        'module': module,
        'event_type': event_type,
        'severity': '',
        'organization_id': _i64(row.get('organization_id')),
        'site_id': _i64(row.get('site_id')),
        'iam_area_id': _i64(row.get('iam_area_id')),
        'iam_zone_id': _i64(row.get('iam_zone_id')),
        'node_id': _i64(row.get('node_id')),
        'node_path': _s(row.get('node_path')),
        'camera_id': _uuid(row.get('camera_id')),
        'camera_code': _s(row.get('camera_code')),
        'camera_name': _s(row.get('camera_name')),
        'zone_id': '',
        'zone_name': '',
        'entity_type': _s(row.get('entity_type')),
        'entity_id': _s(row.get('entity_id')),
        'direction': _s(row.get('direction')),
        'confidence': 0.0,
        'person_id': 0,
        'person_name': '',
        'license_plate': '',
        'snapshot_url': _s(row.get('snapshot_url')),
        'video_clip_url': _s(row.get('video_clip_url')),
        'attrs': attrs,
        'payload': _payload_json(row),
        'src_db': src_db,
        'src_table': src_table,
        'src_id': _i64(row.get('id')),
        'created_at': created,
    }


def map_plate(row: dict[str, Any]) -> dict[str, Any]:
    out = _base(
        row=row,
        module='PLATE',
        event_type=_s(row.get('direction')) or 'UNKNOWN',
        src_db='its',
        src_table='plate_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs={
            k: _s(row.get(k))
            for k in (
                'plate_color',
                'vehicle_type',
                'car_type',
                'manufacturer',
                'vehicle_color',
                'license_plate_status',
            )
            if row.get(k) not in (None, '')
        },
    )
    out['attrs']['is_blacklisted'] = '1' if row.get('is_blacklisted') else '0'
    out['attrs']['is_whitelisted'] = '1' if row.get('is_whitelisted') else '0'
    plate = _s(row.get('normalized_license_plate')) or _s(row.get('license_plate_text'))
    out['license_plate'] = plate
    if not out['entity_id']:
        out['entity_id'] = plate
    return out


def map_anomaly(row: dict[str, Any]) -> dict[str, Any]:
    payload = _as_dict(row.get('payload'))
    extra = {
        k: _s(payload.get(k))
        for k in (
            'submodule_code',
            'water_level',
            'warning_threshold',
            'danger_threshold',
            'trend',
            'unit',
        )
        if payload.get(k) not in (None, '')
    }
    out = _base(
        row=row,
        module='ANOMALY',
        event_type=_s(row.get('event_type')) or 'UNKNOWN',
        src_db='anomaly',
        src_table='anomaly_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs=extra,
    )
    out['severity'] = _s(row.get('severity'))
    out['confidence'] = _f32(row.get('confidence'))
    zone_id = row.get('zone_id')
    out['zone_id'] = _s(zone_id)
    out['zone_name'] = _s(row.get('zone_name'))
    return out


def map_face(row: dict[str, Any]) -> dict[str, Any]:
    event_type = _s(row.get('direction')) or _s(row.get('event_type_id')) or 'UNKNOWN'
    extra = {
        k: _s(row.get(k))
        for k in (
            'user_code',
            'department_name',
            'area_name',
            'device_name',
            'person_type',
            'person_type_name',
            'score_match',
            'gender',
            'age',
            'status',
        )
        if row.get(k) not in (None, '')
    }
    out = _base(
        row=row,
        module='FACE',
        event_type=event_type,
        src_db='smart_face',
        src_table='smf_face_events',
        time_col='access_time',
        created_col='access_time',
        extra_attrs=extra,
    )
    out['person_id'] = _i64(row.get('person_id'))
    out['person_name'] = _s(row.get('user_name'))
    out['entity_id'] = _s(row.get('person_id')) or out['person_name']
    out['entity_type'] = out['entity_type'] or 'PERSON'
    out['camera_name'] = _s(row.get('device_name')) or _s(row.get('camera_name'))
    return out


def map_zone(row: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, str] = {}
    if row.get('zone_name_cached'):
        extra['zone_name_cached'] = _s(row.get('zone_name_cached'))
    out = _base(
        row=row,
        module='ZONE',
        event_type=_s(row.get('direction')) or 'UNKNOWN',
        src_db='virtual_fence',
        src_table='zone_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs=extra,
    )
    out['zone_id'] = _s(row.get('zone_id'))
    out['zone_name'] = _s(row.get('zone_name_cached'))
    out['person_name'] = _s(row.get('person_name'))
    out['license_plate'] = _s(row.get('license_plate'))
    identity = (
        _s(row.get('person_identity')) or out['person_name'] or out['license_plate']
    )
    if not out['entity_id']:
        out['entity_id'] = identity
    return out


def map_fire(row: dict[str, Any]) -> dict[str, Any]:
    alert = _s(row.get('alert_level')) or 'UNKNOWN'
    out = _base(
        row=row,
        module='FIRE',
        event_type=alert,
        src_db='firesmoke',
        src_table='fire_smoke_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs={'alert_level': alert} if alert else None,
    )
    out['severity'] = alert
    return out


def map_footfall(row: dict[str, Any]) -> dict[str, Any]:
    payload = _as_dict(row.get('payload'))
    extra = {
        k: _s(v)
        for k, v in payload.items()
        if v not in (None, '') and k not in BLOB_KEYS
    }
    out = _base(
        row=row,
        module='FOOTFALL',
        event_type=_s(payload.get('event_type'))
        or _s(row.get('entity_type'))
        or 'COUNT',
        src_db='footfall',
        src_table='footfall_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs=extra or None,
    )
    return out


def map_ppe(row: dict[str, Any]) -> dict[str, Any]:
    extra = {
        k: _s(row.get(k))
        for k in ('user_code', 'department_name', 'compliance_status')
        if row.get(k) not in (None, '')
    }
    missing = row.get('missing_items')
    if missing not in (None, ''):
        extra['missing_items'] = _s(missing)
    out = _base(
        row=row,
        module='PPE',
        event_type=_s(row.get('compliance_status')) or 'UNKNOWN',
        src_db='ppe',
        src_table='ppe_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs=extra or None,
    )
    out['person_name'] = _s(row.get('user_name'))
    out['entity_id'] = (
        out['entity_id'] or _s(row.get('user_code')) or out['person_name']
    )
    out['entity_type'] = out['entity_type'] or 'PERSON'
    return out


def map_thermal(row: dict[str, Any]) -> dict[str, Any]:
    src_uuid = _uuid(row.get('id'))
    extra = {
        k: _s(row.get(k))
        for k in ('alert_type', 'status', 'message', 'value_c', 'threshold_c')
        if row.get(k) not in (None, '')
    }
    extra['src_uuid'] = str(src_uuid)
    out = _base(
        row=row,
        module='THERMAL',
        event_type=_s(row.get('alert_type')) or _s(row.get('severity')) or 'UNKNOWN',
        src_db='thermal_db',
        src_table='thermal_alert',
        time_col='first_seen_at',
        created_col='created_at',
        extra_attrs=extra,
    )
    out['severity'] = _s(row.get('severity'))
    out['src_id'] = src_uuid.int % (2**63)
    out['camera_id'] = _uuid(row.get('device_id'))
    return out


def map_hub(row: dict[str, Any]) -> dict[str, Any]:
    out = _base(
        row=row,
        module=_s(row.get('module_code')).upper() or 'HUB',
        event_type=_s(row.get('event_type')) or 'UNKNOWN',
        src_db='vms_db',
        src_table='ai_event',
        time_col='event_time',
        created_col='created_at',
        extra_attrs={
            k: _s(row.get(k))
            for k in ('status', 'source', 'processing_status', 'module_code')
            if row.get(k) not in (None, '')
        }
        or None,
    )
    if out['module'] not in {
        'FACE',
        'PLATE',
        'ZONE',
        'ANOMALY',
        'FIRE',
        'FOOTFALL',
        'PPE',
        'THERMAL',
        'HUB',
    }:
        out['module'] = 'HUB'
    out['severity'] = _s(row.get('severity'))
    out['confidence'] = _f32(row.get('confidence'))
    return out


def map_row_safe(
    mapper: Callable[[dict[str, Any]], dict[str, Any]],
    row: dict[str, Any],
    *,
    src_db: str,
    src_table: str,
) -> dict[str, Any]:
    try:
        return mapper(row)
    except Exception as exc:
        now = datetime.now(UTC)
        return {
            'event_time': now,
            'module': 'UNKNOWN',
            'event_type': 'MAP_ERROR',
            'severity': '',
            'organization_id': 0,
            'site_id': 0,
            'iam_area_id': 0,
            'iam_zone_id': 0,
            'node_id': 0,
            'node_path': '',
            'camera_id': ZERO_UUID,
            'camera_code': '',
            'camera_name': '',
            'zone_id': '',
            'zone_name': '',
            'entity_type': '',
            'entity_id': '',
            'direction': '',
            'confidence': 0.0,
            'person_id': 0,
            'person_name': '',
            'license_plate': '',
            'snapshot_url': '',
            'video_clip_url': '',
            'attrs': {'map_error': str(exc)[:500]},
            'payload': repr(row)[:4000],
            'src_db': src_db,
            'src_table': src_table,
            'src_id': _i64(row.get('id')),
            'created_at': now,
        }


@dataclass(frozen=True)
class Source:
    db: str
    table: str
    time_col: str
    created_col: str
    select_sql: str
    mapper: Callable[[dict[str, Any]], dict[str, Any]]


PLATE_SELECT = """
SELECT id, camera_id, event_time, entity_type, entity_id, direction,
       license_plate_text, license_plate_status, plate_color, vehicle_type,
       car_type, manufacturer, vehicle_color, camera_code, camera_name,
       snapshot_url, payload, created_at, normalized_license_plate,
       is_blacklisted, is_whitelisted, organization_id, site_id,
       iam_area_id, iam_zone_id, node_id, node_path
FROM plate_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

ANOMALY_SELECT = """
SELECT id, organization_id, camera_id, event_time, module_code, event_type,
       severity, confidence, camera_code, camera_name, entity_type, entity_id,
       zone_id, zone_name, snapshot_url, video_clip_url, payload, created_at,
       site_id, iam_area_id, iam_zone_id, node_id, node_path
FROM anomaly_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

FACE_SELECT = """
SELECT id, user_code, user_name, department_name, area_name, device_name,
       access_time, event_type_id, status, person_type, person_type_name,
       person_id, organization_id, score_match, gender, age, camera_id,
       direction, site_id, iam_area_id, iam_zone_id, node_id, node_path
FROM smf_face_events
WHERE id > %s
  AND access_time <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

ZONE_SELECT = """
SELECT id, zone_id, camera_id, event_time, entity_type, entity_id, direction,
       person_name, person_identity, license_plate, snapshot_url,
       zone_name_cached, camera_code, camera_name, payload, created_at,
       organization_id, site_id, iam_area_id, iam_zone_id, node_id, node_path
FROM zone_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

FIRE_SELECT = """
SELECT id, camera_id, event_time, entity_type, entity_id, alert_level,
       camera_code, camera_name, snapshot_url, payload, created_at,
       organization_id, site_id, iam_area_id, iam_zone_id, node_id, node_path
FROM fire_smoke_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

FOOTFALL_SELECT = """
SELECT id, camera_id, event_time, camera_code, camera_name, entity_type, entity_id,
       snapshot_url, payload, created_at, organization_id, site_id,
       iam_area_id, iam_zone_id, node_id, node_path
FROM footfall_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

PPE_SELECT = """
SELECT id, camera_id, event_time, camera_code, camera_name, user_code, user_name,
       department_name, entity_type, entity_id, compliance_status, missing_items,
       snapshot_url, payload, created_at, organization_id, site_id,
       iam_area_id, iam_zone_id, node_id, node_path
FROM ppe_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

HUB_SELECT = """
SELECT id, camera_id, event_time, event_type, entity_type, entity_id, confidence,
       severity, snapshot_url, video_clip_url, payload, created_at, organization_id,
       node_id, node_path, site_id, module_code, status, source, processing_status
FROM ai_event
WHERE id > %s
  AND COALESCE(created_at, event_time) <= NOW() - make_interval(secs => %s)
ORDER BY id
LIMIT %s
"""

SOURCES: tuple[Source, ...] = (
    Source('its', 'plate_event', 'event_time', 'created_at', PLATE_SELECT, map_plate),
    Source(
        'anomaly',
        'anomaly_event',
        'event_time',
        'created_at',
        ANOMALY_SELECT,
        map_anomaly,
    ),
    Source(
        'smart_face',
        'smf_face_events',
        'access_time',
        'access_time',
        FACE_SELECT,
        map_face,
    ),
    Source(
        'virtual_fence', 'zone_event', 'event_time', 'created_at', ZONE_SELECT, map_zone
    ),
    Source(
        'firesmoke',
        'fire_smoke_event',
        'event_time',
        'created_at',
        FIRE_SELECT,
        map_fire,
    ),
    Source(
        'footfall',
        'footfall_event',
        'event_time',
        'created_at',
        FOOTFALL_SELECT,
        map_footfall,
    ),
    Source('ppe', 'ppe_event', 'event_time', 'created_at', PPE_SELECT, map_ppe),
    Source('vms_db', 'ai_event', 'event_time', 'created_at', HUB_SELECT, map_hub),
)
