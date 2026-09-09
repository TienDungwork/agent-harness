"""ClickHouse analytics queries for VMS events (parameterized, no agent SQL)."""

from __future__ import annotations

import re
from typing import Any

import httpx
from config import Settings
from fastapi import HTTPException

MODULES = frozenset(
    {'FACE', 'PLATE', 'ZONE', 'ANOMALY', 'FIRE', 'FOOTFALL', 'PPE', 'THERMAL', 'HUB'}
)
_EVENT_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
_PLATE_RE = re.compile(r'^[A-Za-z0-9.\- ]{2,32}$')
_PERSON_RE = re.compile(r'^[^;{}\\]{2,80}$')


def clamp_days(days: int | None, default: int = 7) -> int:
    value = default if days is None else int(days)
    return max(1, min(value, 1095))


def clamp_limit(limit: int | None, default: int = 20, cap: int = 100) -> int:
    value = default if limit is None else int(limit)
    return max(1, min(value, cap))


def require_module(module: str | None) -> str:
    raw = (module or '').strip().upper()
    if not raw:
        return ''
    if raw not in MODULES:
        raise HTTPException(
            status_code=400,
            detail=f'module must be one of {sorted(MODULES)} or empty',
        )
    return raw


def require_event_type(event_type: str | None) -> str:
    raw = (event_type or '').strip().upper()
    if not raw:
        return ''
    if not _EVENT_TYPE_RE.match(raw):
        raise HTTPException(status_code=400, detail='invalid event_type')
    return raw


def require_plate(q: str) -> str:
    raw = (q or '').strip().upper().replace(' ', '')
    if not _PLATE_RE.match(raw):
        raise HTTPException(status_code=400, detail='invalid plate query')
    return raw


def require_person(q: str) -> str:
    raw = (q or '').strip()
    if not _PERSON_RE.match(raw):
        raise HTTPException(status_code=400, detail='invalid person query')
    return raw


def _client_conf(settings: Settings) -> tuple[str, str, str, str]:
    url = (settings.ch_url or '').rstrip('/')
    password = settings.ch_password or ''
    if not url or not password:
        raise HTTPException(
            status_code=503,
            detail='ClickHouse analytics is not configured (CH_URL / CH_PASSWORD)',
        )
    return url, settings.ch_user, password, settings.ch_database


def query_json(
    settings: Settings,
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    url, user, password, database = _client_conf(settings)
    query_params: dict[str, Any] = {
        'database': database,
        'default_format': 'JSON',
    }
    for key, value in params.items():
        query_params[f'param_{key}'] = value
    try:
        response = httpx.post(
            url,
            params=query_params,
            content=sql.encode('utf-8'),
            auth=(user, password),
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail=f'ClickHouse unreachable: {exc}'
        ) from exc
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502, detail=f'ClickHouse error: {response.text[:500]}'
        )
    payload = response.json()
    rows = payload.get('data')
    return rows if isinstance(rows, list) else []


def summary(
    settings: Settings, *, days: int | None, module: str | None
) -> dict[str, Any]:
    d = clamp_days(days)
    m = require_module(module)
    sql = """
SELECT module, event_type, count() AS n
FROM vms.ai_events
WHERE event_time >= now() - toIntervalDay({days:UInt16})
  AND ({module:String} = '' OR module = {module:String})
GROUP BY module, event_type
ORDER BY n DESC
LIMIT 50
"""
    return {
        'days': d,
        'module': m or None,
        'items': query_json(settings, sql, {'days': d, 'module': m}),
    }


def top_cameras(
    settings: Settings,
    *,
    days: int | None,
    module: str | None,
    event_type: str | None,
    limit: int | None,
) -> dict[str, Any]:
    d = clamp_days(days, 30)
    m = require_module(module)
    et = require_event_type(event_type)
    lim = clamp_limit(limit, 20)
    sql = """
SELECT camera_name, camera_id, module, event_type, count() AS n
FROM vms.ai_events
PREWHERE event_time >= now() - toIntervalDay({days:UInt16})
WHERE ({module:String} = '' OR module = {module:String})
  AND ({event_type:String} = '' OR event_type = {event_type:String})
GROUP BY camera_name, camera_id, module, event_type
ORDER BY n DESC
LIMIT {lim:UInt16}
"""
    return {
        'days': d,
        'module': m or None,
        'event_type': et or None,
        'items': query_json(
            settings, sql, {'days': d, 'module': m, 'event_type': et, 'lim': lim}
        ),
    }


def search_plate(
    settings: Settings, *, q: str, days: int | None, limit: int | None
) -> dict[str, Any]:
    plate = require_plate(q)
    d = clamp_days(days, 180)
    lim = clamp_limit(limit, 50)
    sql = """
SELECT
  toTimeZone(event_time, 'Asia/Ho_Chi_Minh') AS event_time_vn,
  camera_name, direction, license_plate,
  attrs['is_blacklisted'] AS blacklisted
FROM vms.ai_events
WHERE module = 'PLATE'
  AND event_time >= now() - toIntervalDay({days:UInt16})
  AND (license_plate = {plate:String} OR license_plate LIKE concat('%', {plate:String}, '%'))
ORDER BY event_time DESC
LIMIT {lim:UInt16}
"""
    return {
        'query': plate,
        'days': d,
        'items': query_json(settings, sql, {'days': d, 'plate': plate, 'lim': lim}),
    }


def search_person(
    settings: Settings, *, q: str, days: int | None, limit: int | None
) -> dict[str, Any]:
    name = require_person(q)
    d = clamp_days(days, 90)
    lim = clamp_limit(limit, 50)
    sql = """
SELECT
  toTimeZone(event_time, 'Asia/Ho_Chi_Minh') AS event_time_vn,
  module, event_type, camera_name, person_name, zone_name, direction
FROM vms.ai_events
WHERE event_time >= now() - toIntervalDay({days:UInt16})
  AND module IN ('FACE', 'ZONE', 'PPE')
  AND (person_name ILIKE concat('%', {name:String}, '%')
       OR entity_id ILIKE concat('%', {name:String}, '%'))
ORDER BY event_time DESC
LIMIT {lim:UInt16}
"""
    return {
        'query': name,
        'days': d,
        'items': query_json(settings, sql, {'days': d, 'name': name, 'lim': lim}),
    }


def daily(
    settings: Settings, *, days: int | None, module: str | None
) -> dict[str, Any]:
    d = clamp_days(days, 30)
    m = require_module(module)
    sql = """
SELECT day, module, event_type, sum(events) AS n
FROM vms.ai_events_daily
WHERE day >= today() - {days:UInt16}
  AND ({module:String} = '' OR module = {module:String})
GROUP BY day, module, event_type
ORDER BY day, module, event_type
LIMIT 400
"""
    return {
        'days': d,
        'module': m or None,
        'items': query_json(settings, sql, {'days': d, 'module': m}),
    }
