"""ClickHouse analytics queries for VMS events (parameterized, no agent SQL)."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from config import Settings
from fastapi import HTTPException

VN_TZ = ZoneInfo('Asia/Ho_Chi_Minh')

MODULES = frozenset(
    {'FACE', 'PLATE', 'ZONE', 'ANOMALY', 'FIRE', 'FOOTFALL', 'PPE', 'THERMAL', 'HUB'}
)
_EVENT_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
_PLATE_RE = re.compile(r'^[A-Za-z0-9.\- ]{2,32}$')
_PERSON_RE = re.compile(r'^[^;{}\\]{2,80}$')
_DAY_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Dates / count intents must not go through search-plate.
_NOT_A_PLATE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}|xe|bien\s*so|plate|vehicle|count|today|homnay)$',
    re.I,
)


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
    if _DAY_RE.match((q or '').strip()) or _NOT_A_PLATE.match((q or '').strip()):
        raise HTTPException(
            status_code=400,
            detail=(
                'search-plate needs a real license plate string (e.g. 30A-12345). '
                'For vehicle COUNT on a calendar day use '
                'GET /api/infra/analytics/daily?day=YYYY-MM-DD&module=PLATE '
                '(MCP tool vms_daily with day=...).'
            ),
        )
    if not _PLATE_RE.match(raw):
        raise HTTPException(status_code=400, detail='invalid plate query')
    return raw


def require_person(q: str) -> str:
    raw = (q or '').strip()
    if not _PERSON_RE.match(raw):
        raise HTTPException(status_code=400, detail='invalid person query')
    return raw


def require_day(day: str | None) -> str:
    """Optional calendar day YYYY-MM-DD (ClickHouse Date). Empty = rolling window."""
    raw = (day or '').strip()
    if not raw:
        return ''
    if not _DAY_RE.match(raw):
        raise HTTPException(status_code=400, detail='day must be YYYY-MM-DD')
    return raw


def require_org_id(settings: Any) -> int:
    org = int(getattr(settings, 'vms_organization_id', 0) or 0)
    if org <= 0:
        raise HTTPException(
            status_code=503,
            detail='VMS analytics requires VMS_ORGANIZATION_ID',
        )
    return org


def _nonneg_id(name: str, raw: int | None) -> int:
    value = 0 if raw is None else int(raw)
    if value < 0:
        raise HTTPException(status_code=400, detail=f'{name} must be >= 0')
    return value


def vms_scope_sql(
    settings: Any,
    *,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
    hierarchy: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Server-side tenant filter. Client/LLM cannot choose organization_id."""
    parts = ['organization_id = {org_id:Int64}']
    params: dict[str, Any] = {'org_id': require_org_id(settings)}
    if hierarchy:
        sid = _nonneg_id('site_id', site_id)
        aid = _nonneg_id('iam_area_id', iam_area_id)
        zid = _nonneg_id('iam_zone_id', iam_zone_id)
        if sid:
            parts.append('site_id = {site_id:Int64}')
            params['site_id'] = sid
        if aid:
            parts.append('iam_area_id = {iam_area_id:Int64}')
            params['iam_area_id'] = aid
        if zid:
            parts.append('iam_zone_id = {iam_zone_id:Int64}')
            params['iam_zone_id'] = zid
    return ' AND '.join(parts), params


def _has_hierarchy(
    site_id: int | None, iam_area_id: int | None, iam_zone_id: int | None
) -> bool:
    return bool(site_id or iam_area_id or iam_zone_id)


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
    settings: Settings,
    *,
    days: int | None,
    module: str | None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    d = clamp_days(days)
    m = require_module(module)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    sql = f"""
SELECT module, event_type, count() AS n
FROM vms.ai_events
WHERE event_time >= now() - toIntervalDay({{days:UInt16}})
  AND {scope_sql}
  AND ({{module:String}} = '' OR module = {{module:String}})
GROUP BY module, event_type
ORDER BY n DESC
LIMIT 50
"""
    items = query_json(settings, sql, {**scope_params, 'days': d, 'module': m})
    return {
        'days': d,
        'module': m or None,
        'organization_id': scope_params['org_id'],
        'items': items,
        'total_n': sum(int(row.get('n') or 0) for row in items),
    }


def top_cameras(
    settings: Settings,
    *,
    days: int | None,
    module: str | None,
    event_type: str | None,
    limit: int | None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    d = clamp_days(days, 30)
    m = require_module(module)
    et = require_event_type(event_type)
    lim = clamp_limit(limit, 20)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    sql = f"""
SELECT camera_name, camera_id, module, event_type, count() AS n
FROM vms.ai_events
PREWHERE event_time >= now() - toIntervalDay({{days:UInt16}})
WHERE {scope_sql}
  AND ({{module:String}} = '' OR module = {{module:String}})
  AND ({{event_type:String}} = '' OR event_type = {{event_type:String}})
GROUP BY camera_name, camera_id, module, event_type
ORDER BY n DESC
LIMIT {{lim:UInt16}}
"""
    return {
        'days': d,
        'module': m or None,
        'event_type': et or None,
        'organization_id': scope_params['org_id'],
        'items': query_json(
            settings,
            sql,
            {**scope_params, 'days': d, 'module': m, 'event_type': et, 'lim': lim},
        ),
    }


def search_plate(
    settings: Settings,
    *,
    q: str,
    days: int | None,
    limit: int | None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    plate = require_plate(q)
    d = clamp_days(days, 90)
    lim = clamp_limit(limit, 5, cap=30)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    # Exact match first (bloom index). LIKE only for short partial plates.
    use_like = len(plate) < 5
    if use_like:
        plate_pred = (
            '(license_plate = {plate:String} '
            "OR license_plate LIKE concat('%', {plate:String}, '%'))"
        )
    else:
        plate_pred = 'license_plate = {plate:String}'
    sql = f"""
SELECT
  toTimeZone(event_time, 'Asia/Ho_Chi_Minh') AS event_time_vn,
  camera_name, direction, license_plate,
  attrs['is_blacklisted'] AS blacklisted
FROM vms.ai_events
PREWHERE module = 'PLATE'
  AND event_time >= now() - toIntervalDay({{days:UInt16}})
WHERE {scope_sql}
  AND {plate_pred}
ORDER BY event_time DESC
LIMIT {{lim:UInt16}}
"""
    items = query_json(
        settings, sql, {**scope_params, 'days': d, 'plate': plate, 'lim': lim}
    )
    if not items:
        reply = f'Không tìm thấy lịch sử biển số {plate} trong {d} ngày gần đây.'
    else:
        lines = [
            f'Lịch sử biển số {plate} ({len(items)} mốc gần nhất, cửa sổ {d} ngày):'
        ]
        for row in items[:10]:
            t = str(row.get('event_time_vn') or '')
            cam = str(row.get('camera_name') or '?')
            direction = str(row.get('direction') or '')
            d_vi = _DIR_VI.get(direction, direction)
            lines.append(f'- {t} · camera {cam} · {d_vi}')
        reply = '\n'.join(lines)
    return {
        'query': plate,
        'days': d,
        'organization_id': scope_params['org_id'],
        # Keep payload tiny so the LLM does not stall on 50-row JSON.
        'items': items[:10],
        'items_n': len(items),
        'reply_vi': reply,
    }


def search_person(
    settings: Settings,
    *,
    q: str,
    days: int | None,
    limit: int | None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    name = require_person(q)
    d = clamp_days(days, 90)
    lim = clamp_limit(limit, 50)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    sql = f"""
SELECT
  toTimeZone(event_time, 'Asia/Ho_Chi_Minh') AS event_time_vn,
  module, event_type, camera_name, person_name, zone_name, direction
FROM vms.ai_events
WHERE event_time >= now() - toIntervalDay({{days:UInt16}})
  AND {scope_sql}
  AND module IN ('FACE', 'ZONE', 'PPE')
  AND (person_name ILIKE concat('%', {{name:String}}, '%')
       OR entity_id ILIKE concat('%', {{name:String}}, '%'))
ORDER BY event_time DESC
LIMIT {{lim:UInt16}}
"""
    return {
        'query': name,
        'days': d,
        'organization_id': scope_params['org_id'],
        'items': query_json(
            settings, sql, {**scope_params, 'days': d, 'name': name, 'lim': lim}
        ),
    }


def daily(
    settings: Settings,
    *,
    days: int | None,
    module: str | None,
    day: str | None = None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    """Daily PLATE (etc.) counts for calendar days in Asia/Ho_Chi_Minh.

    Always reads ``ai_events`` with VN timezone — ``ai_events_daily`` is UTC-bucketed
    and disagrees with plate-flow / user-facing calendar days.
    """
    d = clamp_days(days, 30)
    m = require_module(module)
    one = require_day(day)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    if one:
        sql = f"""
SELECT
  toDate(event_time, 'Asia/Ho_Chi_Minh') AS day,
  module,
  event_type,
  count() AS n
FROM vms.ai_events
WHERE toDate(event_time, 'Asia/Ho_Chi_Minh') = {{day:Date}}
  AND {scope_sql}
  AND ({{module:String}} = '' OR module = {{module:String}})
GROUP BY day, module, event_type
ORDER BY module, event_type
LIMIT 100
"""
        items = query_json(settings, sql, {**scope_params, 'day': one, 'module': m})
        return {
            'day': one,
            'module': m or None,
            'organization_id': scope_params['org_id'],
            'items': items,
            'total_n': sum(int(row.get('n') or 0) for row in items),
            'tz': 'Asia/Ho_Chi_Minh',
        }
    sql = f"""
SELECT
  toDate(event_time, 'Asia/Ho_Chi_Minh') AS day,
  module,
  event_type,
  count() AS n
FROM vms.ai_events
WHERE toDate(event_time, 'Asia/Ho_Chi_Minh')
      >= toDate(now(), 'Asia/Ho_Chi_Minh') - {{days:UInt16}}
  AND {scope_sql}
  AND ({{module:String}} = '' OR module = {{module:String}})
GROUP BY day, module, event_type
ORDER BY day, module, event_type
LIMIT 400
"""
    items = query_json(settings, sql, {**scope_params, 'days': d, 'module': m})
    return {
        'days': d,
        'module': m or None,
        'organization_id': scope_params['org_id'],
        'items': items,
        'total_n': sum(int(row.get('n') or 0) for row in items),
        'tz': 'Asia/Ho_Chi_Minh',
    }


def require_days_list(raw: str | None, *, max_days: int = 31) -> list[str]:
    """Comma/space-separated YYYY-MM-DD list (deduped, sorted). Max 31 (full month)."""
    text = (raw or '').strip()
    if not text:
        return []
    parts = re.split(r'[,;\s]+', text)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        day = require_day(part)
        if not day or day in seen:
            continue
        seen.add(day)
        out.append(day)
        if len(out) >= max_days:
            break
    if not out:
        raise HTTPException(status_code=400, detail='days_list must be YYYY-MM-DD,…')
    return sorted(out)


def require_month(raw: str | None) -> str | None:
    """YYYY-MM calendar month."""
    text = (raw or '').strip()
    if not text:
        return None
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', text):
        raise HTTPException(
            status_code=400, detail='month must be YYYY-MM (e.g. 2026-09)'
        )
    return text


def vn_today() -> date:
    return datetime.now(VN_TZ).date()


def month_days_to_date(month: str, *, until: date | None = None) -> list[str]:
    """Days from the 1st of YYYY-MM through min(until, month-end). Default until=today VN."""
    ym = require_month(month)
    assert ym is not None
    y, m = int(ym[:4]), int(ym[5:7])
    start = date(y, m, 1)
    last_dom = calendar.monthrange(y, m)[1]
    month_end = date(y, m, last_dom)
    end = until or vn_today()
    if end < start:
        raise HTTPException(
            status_code=400,
            detail=f'month {ym} is after until={end.isoformat()}',
        )
    end = min(end, month_end)
    out: list[str] = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _fmt_dmy(iso: str) -> str:
    y, mo, dd = iso.split('-')
    return f'{dd}/{mo}/{y}'


def daily_multi(
    settings: Settings,
    *,
    days_list: list[str],
    module: str | None = 'PLATE',
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    """Count PLATE (or module) for several VN calendar days (one CH scan)."""
    m = require_module(module or 'PLATE') or 'PLATE'
    if not days_list:
        raise HTTPException(status_code=400, detail='days_list empty')
    days_sorted = sorted(days_list)
    org_id = require_org_id(settings)
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    # Single range scan in Asia/Ho_Chi_Minh — matches plate-flow calendar days.
    sql = f"""
SELECT
  toString(toDate(event_time, 'Asia/Ho_Chi_Minh')) AS day,
  count() AS total_n
FROM vms.ai_events
WHERE module = {{module:String}}
  AND {scope_sql}
  AND toDate(event_time, 'Asia/Ho_Chi_Minh') >= {{d0:Date}}
  AND toDate(event_time, 'Asia/Ho_Chi_Minh') <= {{d1:Date}}
GROUP BY day
ORDER BY day
"""
    rows = query_json(
        settings,
        sql,
        {
            **scope_params,
            'module': m,
            'd0': days_sorted[0],
            'd1': days_sorted[-1],
        },
    )
    by_day = {
        str(r.get('day') or ''): int(r.get('total_n') or 0)
        for r in rows
        if r.get('day')
    }
    # Keep zeros for requested days with no events (full month axis on chart).
    per_day = [{'day': day, 'total_n': by_day.get(day, 0)} for day in days_sorted]
    total = sum(int(r['total_n']) for r in per_day)
    if len(per_day) > 5:
        reply = (
            f'Từ {_fmt_dmy(per_day[0]["day"])} đến {_fmt_dmy(per_day[-1]["day"])}: '
            f'tổng {total} lượt biển số ({len(per_day)} ngày, giờ VN).'
        )
    else:
        lines = [
            f'Ngày {_fmt_dmy(row["day"])}: {row["total_n"]} lượt biển số.'
            for row in per_day
        ]
        if len(per_day) > 1:
            lines.append(f'Tổng {len(per_day)} ngày: {total} lượt biển số.')
        reply = '\n'.join(lines)
    return {
        'ok': True,
        'module': m,
        'organization_id': org_id,
        'days_list': days_sorted,
        'per_day': per_day,
        'items': [],
        'total_n': total,
        'tz': 'Asia/Ho_Chi_Minh',
        'reply_vi': reply,
    }


_COUNT_INTENT_RE = re.compile(
    r'(s[ốo]\s*(lư[ợo]ng\s*)?(xe|bi[ểe]n)|'
    r'[đd][ếe]m|'
    r'bao\s*nhi[êe]u\s*xe|'
    r'lư[ợo]t\s*bi[ểe]n|'
    r'vehicle\s*count|count\s*vehicles?|count\s*plates?|'
    r'license\s*plates?|'
    r'get\s*.*vehicle|'
    r'search\s*for\s*license)',
    re.I,
)
_TODAY_RE = re.compile(r'h[ôo]m\s*nay|hom\s*nay|\btoday\b', re.I)
_ISO_DAY_RE = re.compile(r'(20\d{2})-(\d{2})-(\d{2})')
_DMY_RE = re.compile(
    r'(?:ng[àa]y\s*)?(\d{1,2})[/.\-\s]+(\d{1,2})[/.\-\s]+(20\d{2})',
    re.I,
)
_DAY_AND_DAY_RE = re.compile(
    r'ng[àa]y\s*(\d{1,2})\s*v[àa]\s*(?:ng[àa]y\s*)?(\d{1,2})',
    re.I,
)
_MONTH_YEAR_RE = re.compile(
    r'th[áa]ng\s*(\d{1,2})\s*(?:năm\s*)?(20\d{2})',
    re.I,
)


def is_vehicle_count_question(q: str) -> bool:
    text = (q or '').strip()
    if not text:
        return False
    if _COUNT_INTENT_RE.search(text):
        return True
    if _ISO_DAY_RE.search(text) or _DMY_RE.search(text):
        return True
    if _DAY_AND_DAY_RE.search(text):
        return True
    return False


def ask_vehicle_count(settings: Settings, *, q: str) -> dict[str, Any]:
    """NL → plate count → reply_vi (no LLM / no MCP). Sub-second path."""
    text = (q or '').strip()
    if not text:
        raise HTTPException(status_code=400, detail='q is required')

    # "ngày 5 và ngày 6 tháng 9 năm 2026"
    pair = _DAY_AND_DAY_RE.search(text)
    my = _MONTH_YEAR_RE.search(text)
    if pair and my:
        d1, d2 = int(pair.group(1)), int(pair.group(2))
        month, year = int(my.group(1)), my.group(2)
        days_list = sorted(
            [
                f'{year}-{month:02d}-{d1:02d}',
                f'{year}-{month:02d}-{d2:02d}',
            ]
        )
        return daily_multi(settings, days_list=days_list, module='PLATE')

    iso = _ISO_DAY_RE.search(text)
    dmy = _DMY_RE.search(text)
    day: str | None = None
    if iso:
        day = f'{iso.group(1)}-{iso.group(2)}-{iso.group(3)}'
    elif dmy:
        dd, mm, yy = int(dmy.group(1)), int(dmy.group(2)), dmy.group(3)
        day = f'{yy}-{mm:02d}-{dd:02d}'

    if day:
        data = daily(settings, days=1, module='PLATE', day=day)
        total = int(data.get('total_n') or 0)
        y, m, d = day.split('-')
        reply = f'Ngày {d}/{m}/{y} có {total} lượt biển số.'
        return {
            'ok': True,
            'day': day,
            'module': 'PLATE',
            'total_n': total,
            'items': data.get('items') or [],
            'reply_vi': reply,
            'source': 'daily',
        }

    data = summary(settings, days=1, module='PLATE')
    total = int(data.get('total_n') or 0)
    reply = f'Hôm nay có {total} lượt biển số.'
    return {
        'ok': True,
        'days': 1,
        'module': 'PLATE',
        'total_n': total,
        'items': data.get('items') or [],
        'reply_vi': reply,
        'source': 'summary',
        'today': bool(_TODAY_RE.search(text)),
    }


_VEHICLE_TYPE_VI = {
    'MOTORCYCLE': 'xe máy',
    'CAR': 'ô tô',
    'TRUCK': 'xe tải',
    'BUS': 'xe khách',
}
_DIR_VI = {'IN': 'vào', 'OUT': 'ra'}


def _day_clause(day: str | None) -> tuple[str, dict[str, Any], str]:
    """Return (SQL predicate, params, day_label YYYY-MM-DD or 'today')."""
    one = require_day(day)
    if one:
        return (
            "toDate(event_time, 'Asia/Ho_Chi_Minh') = {day:Date}",
            {'day': one},
            one,
        )
    return (
        "toDate(event_time, 'Asia/Ho_Chi_Minh') = toDate(now(), 'Asia/Ho_Chi_Minh')",
        {},
        'today',
    )


def _fmt_day_vi(day_label: str) -> str:
    if day_label == 'today':
        return 'Hôm nay'
    y, m, d = day_label.split('-')
    return f'Ngày {d}/{m}/{y}'


def _latest_event_day(
    settings: Settings,
    *,
    module: str,
    event_type: str | None = None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
    lookback_days: int = 90,
) -> str | None:
    """Newest VN calendar day that still has rows for module(/event_type)."""
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    et_sql = ''
    params: dict[str, Any] = {
        **scope_params,
        'mod': module,
        'lb': int(lookback_days),
    }
    if event_type:
        et_sql = 'AND event_type = {et:String}'
        params['et'] = event_type
    sql = f"""
SELECT toString(max(toDate(event_time, 'Asia/Ho_Chi_Minh'))) AS d
FROM vms.ai_events
WHERE module = {{mod:String}}
  AND {scope_sql}
  {et_sql}
  AND toDate(event_time, 'Asia/Ho_Chi_Minh') >= toDate(now(), 'Asia/Ho_Chi_Minh') - {{lb:UInt16}}
"""
    rows = query_json(settings, sql, params)
    if not rows:
        return None
    d = str(rows[0].get('d') or '').strip()
    if not d or d.lower() in ('', '1970-01-01', 'none', 'null'):
        return None
    if not _DAY_RE.fullmatch(d):
        return None
    return d


def _today_vn() -> str:
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d')


def _should_fallback_empty_day(day: str | None, total_n: int) -> bool:
    """Empty result for omitted day or explicit calendar-today → try latest."""
    if int(total_n or 0) > 0:
        return False
    if not day:
        return True
    return day == _today_vn()


def _day_clause_with_fallback(
    settings: Settings,
    day: str | None,
    *,
    module: str,
    event_type: str | None = None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
    empty: bool,
) -> tuple[str, dict[str, Any], str, str | None]:
    """Like ``_day_clause``, but if asking for today and empty, use latest day.

    Returns (clause, params, day_label, fallback_note_or_None).
    """
    clause, params, day_label = _day_clause(day)
    if not empty or not _should_fallback_empty_day(day, 0):
        return clause, params, day_label, None
    latest = _latest_event_day(
        settings,
        module=module,
        event_type=event_type,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    if not latest:
        return clause, params, day_label, None
    clause2, params2, label2 = _day_clause(latest)
    note = (
        f'Hôm nay chưa có dữ liệu; dùng ngày gần nhất có dữ liệu '
        f'({_fmt_day_vi(latest)}).'
    )
    return clause2, params2, label2, note


def plate_flow(
    settings: Settings,
    *,
    day: str | None = None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    """PLATE counts by direction × vehicle_type for a VN calendar day."""
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )

    def _run(clause: str, params: dict[str, Any], day_label: str, note: str | None):
        sql = f"""
SELECT
  if(direction = '', 'UNKNOWN', direction) AS direction,
  if(attrs['vehicle_type'] = '', 'UNKNOWN', attrs['vehicle_type']) AS vehicle_type,
  count() AS n
FROM vms.ai_events
WHERE module = 'PLATE'
  AND {scope_sql}
  AND {clause}
GROUP BY direction, vehicle_type
ORDER BY n DESC
LIMIT 50
"""
        items = query_json(settings, sql, {**scope_params, **params})
        total = sum(int(r.get('n') or 0) for r in items)
        by_dir: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for row in items:
            n = int(row.get('n') or 0)
            d = str(row.get('direction') or 'UNKNOWN')
            vt = str(row.get('vehicle_type') or 'UNKNOWN')
            by_dir[d] = by_dir.get(d, 0) + n
            by_type[vt] = by_type.get(vt, 0) + n

        lines = [f'{_fmt_day_vi(day_label)}: tổng {total} lượt biển số.']
        if note:
            lines.insert(0, note)
        for key in ('IN', 'OUT'):
            if key in by_dir:
                lines.append(f'- {_DIR_VI[key].capitalize()}: {by_dir[key]}')
        for vt, n in sorted(by_type.items(), key=lambda x: -x[1]):
            label = _VEHICLE_TYPE_VI.get(
                vt, vt.lower() if vt != 'UNKNOWN' else 'chưa xác định'
            )
            lines.append(f'- {label}: {n}')
        if items:
            lines.append('Chi tiết:')
            for row in items[:12]:
                d = str(row.get('direction') or '')
                vt = str(row.get('vehicle_type') or '')
                n = int(row.get('n') or 0)
                d_vi = _DIR_VI.get(d, d)
                vt_vi = _VEHICLE_TYPE_VI.get(vt, vt or 'chưa xác định')
                lines.append(f'  · {d_vi} / {vt_vi}: {n}')
        lines.append(
            'Lưu ý: kho hiện chưa có số chỗ (5/7/9/16…) — chỉ có loại xe máy/ô tô/tải.'
        )
        return {
            'ok': True,
            'day': None if day_label == 'today' else day_label,
            'organization_id': scope_params['org_id'],
            'total_n': total,
            'by_direction': by_dir,
            'by_vehicle_type': by_type,
            'items': items,
            'reply_vi': '\n'.join(lines),
            'seats_available': False,
            'fallback_from_today': bool(note),
        }

    clause, params, day_label = _day_clause(day)
    first = _run(clause, params, day_label, None)
    if not _should_fallback_empty_day(day, int(first.get('total_n') or 0)):
        return first
    clause2, params2, label2, note = _day_clause_with_fallback(
        settings,
        day,
        module='PLATE',
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
        empty=True,
    )
    if not note:
        return first
    return _run(clause2, params2, label2, note)


def plate_by_manufacturer(
    settings: Settings,
    *,
    day: str | None = None,
    vehicle_type: str = 'CAR',
    limit: int | None = 20,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    """Ô tô (or type) counts by manufacturer for a VN calendar day."""
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )
    lim = clamp_limit(limit, 20)
    vt = (vehicle_type or 'CAR').strip().upper() or 'CAR'
    if vt not in {'CAR', 'MOTORCYCLE', 'TRUCK', 'BUS', 'ALL'}:
        raise HTTPException(status_code=400, detail='invalid vehicle_type')
    type_filter = '' if vt == 'ALL' else "AND attrs['vehicle_type'] = {vt:String}"

    def _run(clause: str, params: dict[str, Any], day_label: str, note: str | None):
        qparams = {**scope_params, **params, 'lim': lim}
        if vt != 'ALL':
            qparams['vt'] = vt
        sql = f"""
SELECT
  if(attrs['manufacturer'] = '', 'UNKNOWN', upper(attrs['manufacturer'])) AS manufacturer,
  count() AS n
FROM vms.ai_events
WHERE module = 'PLATE'
  AND {scope_sql}
  AND {clause}
  {type_filter}
GROUP BY manufacturer
ORDER BY n DESC
LIMIT {{lim:UInt16}}
"""
        items = query_json(settings, sql, qparams)
        total = sum(int(r.get('n') or 0) for r in items)
        type_vi = _VEHICLE_TYPE_VI.get(vt, 'xe') if vt != 'ALL' else 'xe'
        lines = [
            f'{_fmt_day_vi(day_label)} — {type_vi} theo hãng (tổng {total} lượt có gắn hãng/UNKNOWN):'
        ]
        if note:
            lines.insert(0, note)
        if not items:
            lines.append('- Không có dữ liệu.')
        for row in items:
            mfr = str(row.get('manufacturer') or 'UNKNOWN')
            n = int(row.get('n') or 0)
            lines.append(f'- {mfr}: {n}')
        return {
            'ok': True,
            'day': None if day_label == 'today' else day_label,
            'organization_id': scope_params['org_id'],
            'vehicle_type': vt,
            'total_n': total,
            'items': items,
            'reply_vi': '\n'.join(lines),
            'fallback_from_today': bool(note),
        }

    clause, params, day_label = _day_clause(day)
    first = _run(clause, params, day_label, None)
    if not _should_fallback_empty_day(day, int(first.get('total_n') or 0)):
        return first
    clause2, params2, label2, note = _day_clause_with_fallback(
        settings,
        day,
        module='PLATE',
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
        empty=True,
    )
    if not note:
        return first
    return _run(clause2, params2, label2, note)


def intrusion_peak(
    settings: Settings,
    *,
    day: str | None = None,
    site_id: int | None = None,
    iam_area_id: int | None = None,
    iam_zone_id: int | None = None,
) -> dict[str, Any]:
    """Hour-of-day peak for ANOMALY INTRUSION_DETECTION (VN calendar day)."""
    scope_sql, scope_params = vms_scope_sql(
        settings,
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
    )

    def _run(clause: str, params: dict[str, Any], day_label: str, note: str | None):
        sql = f"""
SELECT
  toHour(event_time, 'Asia/Ho_Chi_Minh') AS hour,
  count() AS n
FROM vms.ai_events
WHERE module = 'ANOMALY'
  AND event_type = 'INTRUSION_DETECTION'
  AND {scope_sql}
  AND {clause}
GROUP BY hour
ORDER BY n DESC
LIMIT 24
"""
        items = query_json(settings, sql, {**scope_params, **params})
        total = sum(int(r.get('n') or 0) for r in items)
        if not items or total == 0:
            reply = f'{_fmt_day_vi(day_label)} không có sự kiện xâm nhập (INTRUSION_DETECTION).'
            if note:
                reply = note + '\n' + reply
            return {
                'ok': True,
                'day': None if day_label == 'today' else day_label,
                'organization_id': scope_params['org_id'],
                'total_n': 0,
                'peak_hour': None,
                'items': [],
                'reply_vi': reply,
                'fallback_from_today': bool(note),
            }
        top = items[0]
        peak_h = int(top.get('hour') or 0)
        peak_n = int(top.get('n') or 0)
        lines = [
            f'{_fmt_day_vi(day_label)} có {total} lượt xâm nhập.',
            f'Khung giờ nhiều nhất: {peak_h:02d}:00–{peak_h:02d}:59 ({peak_n} sự kiện).',
            'Top khung giờ:',
        ]
        if note:
            lines.insert(0, note)
        for row in items[:5]:
            h = int(row.get('hour') or 0)
            n = int(row.get('n') or 0)
            lines.append(f'- {h:02d}h: {n}')
        return {
            'ok': True,
            'day': None if day_label == 'today' else day_label,
            'organization_id': scope_params['org_id'],
            'total_n': total,
            'peak_hour': peak_h,
            'items': items,
            'reply_vi': '\n'.join(lines),
            'fallback_from_today': bool(note),
        }

    clause, params, day_label = _day_clause(day)
    first = _run(clause, params, day_label, None)
    if not _should_fallback_empty_day(day, int(first.get('total_n') or 0)):
        return first
    clause2, params2, label2, note = _day_clause_with_fallback(
        settings,
        day,
        module='ANOMALY',
        event_type='INTRUSION_DETECTION',
        site_id=site_id,
        iam_area_id=iam_area_id,
        iam_zone_id=iam_zone_id,
        empty=True,
    )
    if not note:
        return first
    return _run(clause2, params2, label2, note)
