"""MCP stdio server: expose infra / VMS tools to Creanova agent-server.

Run (from agent-canvas container)::

    uv run --with httpx --with mcp python /opt/infra-mcp/mcp_stdio.py

Env:
  GATEWAY_URL          default http://local-gateway:18110
  INFRA_AGENT_TOKEN    preferred auth (exported by canvas entrypoint)
  INFRA_TOKEN_FILE     fallback path to token file
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

_SUDO_RE = re.compile(r'(^|[;&|]\s*|\n)\s*sudo\b', re.I)
_AUTO_PROBE_CMD = re.compile(
    r'(^|[;&|]\s*)(sudo\b|systemctl\b|nginx\b|ip\s|ls\b|cd\s+/home/ubuntu)',
    re.I,
)
_SUDO_BLOCKED_REPLY_VI = (
    'Đã vào máy rồi — đừng dùng sudo. Bạn muốn chạy lệnh gì (không sudo)?'
)

# After connect-only resolve, block infra_run briefly so the model cannot auto-ls/sudo.
_CONNECT_ONLY_UNTIL: dict[str, tuple[float, str]] = {}
_CONNECT_ONLY_TTL_SEC = 45.0

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://local-gateway:18110').rstrip('/')
DEFAULT_TOKEN_FILES = (
    os.environ.get('INFRA_TOKEN_FILE', '').strip(),
    '/home/openhands/.openhands/agent-canvas/infra-agent-token.txt',
    '/home/openhands/.openhands/infra-agent-token.txt',
)

mcp = FastMCP('creanova-infra')


def _auth_headers() -> dict[str, str]:
    token = os.environ.get('INFRA_AGENT_TOKEN', '').strip()
    if not token:
        for path in DEFAULT_TOKEN_FILES:
            if not path:
                continue
            try:
                with open(path, encoding='utf-8') as f:
                    token = f.read().strip()
            except OSError:
                continue
            if token:
                break
    if not token:
        raise RuntimeError('INFRA_AGENT_TOKEN missing (env or infra-agent-token.txt)')
    return {'X-Creanova-Infra-Token': token}


async def _get(path: str, params: dict[str, Any] | None = None) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f'{GATEWAY_URL}{path}',
            headers=_auth_headers(),
            params=params or {},
        )
    if r.status_code >= 400:
        return json.dumps(
            {'error': r.status_code, 'detail': r.text}, ensure_ascii=False
        )
    try:
        return json.dumps(r.json(), ensure_ascii=False)
    except json.JSONDecodeError:
        return r.text


async def _delete(path: str, timeout: float = 30.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.delete(
            f'{GATEWAY_URL}{path}',
            headers=_auth_headers(),
        )
    if r.status_code >= 400:
        return json.dumps(
            {'error': r.status_code, 'detail': r.text}, ensure_ascii=False
        )
    try:
        return json.dumps(r.json(), ensure_ascii=False)
    except json.JSONDecodeError:
        return r.text


async def _post(path: str, body: dict[str, Any], timeout: float = 120.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f'{GATEWAY_URL}{path}',
            headers={**_auth_headers(), 'Content-Type': 'application/json'},
            json=body,
        )
    if r.status_code >= 400:
        return json.dumps(
            {'error': r.status_code, 'detail': r.text}, ensure_ascii=False
        )
    try:
        return json.dumps(r.json(), ensure_ascii=False)
    except json.JSONDecodeError:
        return r.text


@mcp.tool()
async def vms_count_vehicles(
    day: str | None = None,
    days: int | None = None,
    days_list: str | None = None,
    month: str | None = None,
    summary: str | None = None,
) -> str:
    """Đếm xe / biển số (PLATE). Mọi câu 'số xe', 'đếm biển', 'biểu đồ số lượng'.

    Ngày tháng = kiểu Việt Nam DD/MM/YYYY. Truyền ISO vào tool.
    - Một ngày: day='2026-09-05'
    - Nhiều ngày rời: days_list='2026-09-05,2026-09-06'
    - Cả tháng / tháng đến nay: month='2026-09' (từ ngày 1 → hôm nay VN) → line chart
    - Hôm nay: days=1
    Nếu JSON có reply_vi → trả lời ĐÚNG nội dung đó (tiếng Việt). Không English.
    Không truyền summary. Không truyền vehicle_type trừ khi user hỏi rõ loại xe.
    """
    _ = summary
    month_s = (month or '').strip()
    if month_s:
        if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', month_s):
            return json.dumps(
                {
                    'error': 400,
                    'reply_vi': 'month phải dạng YYYY-MM (vd 2026-09).',
                },
                ensure_ascii=False,
            )
        raw = await _get(
            '/api/infra/analytics/daily',
            {'month': month_s, 'module': 'PLATE'},
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(data, dict) and data.get('error'):
            return raw
        reply = data.get('reply_vi') if isinstance(data, dict) else None
        if not reply:
            return raw
        return _wrap_reply_vi(
            json.dumps(
                {
                    'ok': True,
                    'month': month_s,
                    'days_list': (data or {}).get('days_list'),
                    'module': 'PLATE',
                    'total_n': (data or {}).get('total_n'),
                    'per_day': (data or {}).get('per_day') or [],
                    'reply_vi': reply,
                },
                ensure_ascii=False,
            )
        )

    list_raw = (days_list or '').strip()
    if list_raw:
        raw = await _get(
            '/api/infra/analytics/daily',
            {'days_list': list_raw, 'module': 'PLATE'},
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(data, dict) and data.get('error'):
            return raw
        reply = data.get('reply_vi') if isinstance(data, dict) else None
        if not reply:
            return raw
        # Rebuild full payload then slim via _wrap_reply_vi (adds chart).
        return _wrap_reply_vi(
            json.dumps(
                {
                    'ok': True,
                    'days_list': (data or {}).get('days_list'),
                    'module': 'PLATE',
                    'total_n': (data or {}).get('total_n'),
                    'per_day': (data or {}).get('per_day') or [],
                    'reply_vi': reply,
                },
                ensure_ascii=False,
            )
        )

    day_s = (day or '').strip()
    if day_s:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day_s):
            return json.dumps(
                {
                    'error': 400,
                    'detail': 'day must be YYYY-MM-DD',
                    'reply_vi': 'Ngày không hợp lệ. Hãy dùng dạng YYYY-MM-DD (vd 2026-09-06).',
                },
                ensure_ascii=False,
            )
        raw = await _get(
            '/api/infra/analytics/daily',
            {'day': day_s, 'module': 'PLATE'},
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(data, dict) and data.get('error'):
            return raw
        total = int((data or {}).get('total_n') or 0)
        y, m, d = day_s.split('-')
        reply = f'Ngày {d}/{m}/{y} có {total} lượt biển số.'
        return json.dumps(
            {
                'ok': True,
                'day': day_s,
                'module': 'PLATE',
                'total_n': total,
                'items': (data or {}).get('items') or [],
                'reply_vi': reply,
                'agent_instruction': (
                    'Trả lời ĐÚNG 1 dòng reply_vi bằng tiếng Việt. '
                    'Không viết English. Không gọi thêm tool.'
                ),
            },
            ensure_ascii=False,
        )

    window = 1 if days is None else int(days)
    # "Hôm nay" / days=1 often empty when warehouse lags — fall back to the
    # latest calendar day that still has PLATE rows (ngày gần nhất có dữ liệu).
    if window <= 1:
        raw_daily = await _get(
            '/api/infra/analytics/daily',
            {'days': 90, 'module': 'PLATE'},
        )
        try:
            daily = json.loads(raw_daily)
        except json.JSONDecodeError:
            daily = None
        by_day: dict[str, int] = {}
        if isinstance(daily, dict) and not daily.get('error'):
            for row in daily.get('items') or []:
                if not isinstance(row, dict):
                    continue
                d = str(row.get('day') or '')[:10]
                if d:
                    by_day[d] = by_day.get(d, 0) + int(row.get('n') or 0)
        if by_day:
            latest = max(by_day)
            total = by_day[latest]
            y, m, d = latest.split('-')
            reply = f'Ngày gần nhất có dữ liệu là {d}/{m}/{y}: {total} lượt biển số.'
            return json.dumps(
                {
                    'ok': True,
                    'day': latest,
                    'module': 'PLATE',
                    'total_n': total,
                    'reply_vi': reply,
                    'agent_instruction': (
                        'Trả lời ĐÚNG 1 dòng reply_vi bằng tiếng Việt. '
                        'Không viết English. Không gọi thêm tool.'
                    ),
                },
                ensure_ascii=False,
            )

    raw = await _get(
        '/api/infra/analytics/summary',
        {'days': window, 'module': 'PLATE'},
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict) and data.get('error'):
        return raw
    total = int((data or {}).get('total_n') or 0)
    if window <= 1:
        reply = f'Hôm nay có {total} lượt biển số.'
    else:
        reply = f'{window} ngày gần đây có {total} lượt biển số.'
    return json.dumps(
        {
            'ok': True,
            'days': window,
            'module': 'PLATE',
            'total_n': total,
            'items': (data or {}).get('items') or [],
            'reply_vi': reply,
            'agent_instruction': (
                'Trả lời ĐÚNG 1 dòng reply_vi bằng tiếng Việt. '
                'Không viết English. Không gọi thêm tool.'
            ),
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def vms_summary(days: int = 7, module: str | None = None) -> str:
    """Rolling-window VMS counts (last N days). Read total_n in the JSON.

    For hôm nay / today + xe / biển số: days=1 and module=PLATE.
    For a specific calendar day like 2026-09-06 use vms_daily(day=..., module=PLATE)
    instead — not this tool and not vms_search_plate.
    """
    params: dict[str, Any] = {'days': days}
    if module:
        params['module'] = module
    return await _get('/api/infra/analytics/summary', params)


@mcp.tool()
async def vms_top_cameras(
    days: int = 30,
    module: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> str:
    """Top cameras by event count (climbing / fire / plates / etc.)."""
    params: dict[str, Any] = {'days': days, 'limit': limit}
    if module:
        params['module'] = module
    if event_type:
        params['event_type'] = event_type
    return await _get('/api/infra/analytics/top-cameras', params)


def _build_chart(data: dict[str, Any]) -> dict[str, Any] | None:
    """Compact chart series for UI (kept in slim MCP payload; not for LLM prose)."""
    items = data.get('items') or []
    per_day = data.get('per_day') or []

    # Multi-day counts → line
    if isinstance(per_day, list) and len(per_day) >= 2:
        series = []
        for row in per_day[:31]:
            if not isinstance(row, dict):
                continue
            day = str(row.get('day') or '')
            series.append(
                {
                    'label': day[5:] if len(day) >= 10 else day,  # MM-DD
                    'value': int(row.get('total_n') or 0),
                }
            )
        if series:
            return {
                'type': 'line',
                'title': 'Lượt biển theo ngày',
                'description': f'{len(series)} ngày',
                'footer': f'Tổng: {int(data.get("total_n") or 0)}',
                'data': series,
                'series': {'value': 'Lượt biển'},
            }

    # Manufacturer ranking → mixed bar
    if (
        isinstance(items, list)
        and items
        and isinstance(items[0], dict)
        and 'manufacturer' in items[0]
    ):
        series = []
        for row in items[:12]:
            mfr = str(row.get('manufacturer') or 'UNKNOWN')
            series.append(
                {
                    'label': mfr[:16],
                    'value': int(row.get('n') or 0),
                    'key': re.sub(r'[^a-z0-9]+', '_', mfr.lower()).strip('_')
                    or 'other',
                }
            )
        if series:
            vt = str(data.get('vehicle_type') or 'CAR')
            return {
                'type': 'mixed-bar',
                'title': f'Theo hãng ({vt})',
                'description': data.get('day') or 'hôm nay',
                'footer': f'Tổng: {int(data.get("total_n") or 0)}',
                'data': series,
            }

    # Intrusion by hour → area
    if (
        isinstance(items, list)
        and items
        and isinstance(items[0], dict)
        and 'hour' in items[0]
    ):
        by_hour = {
            int(r.get('hour') or 0): int(r.get('n') or 0)
            for r in items
            if isinstance(r, dict)
        }
        series = [{'label': f'{h:02d}h', 'value': by_hour.get(h, 0)} for h in range(24)]
        if any(p['value'] for p in series):
            peak = data.get('peak_hour')
            return {
                'type': 'area',
                'title': 'Xâm nhập theo giờ',
                'description': data.get('day') or 'hôm nay',
                'footer': (
                    f'Peak {int(peak):02d}h · tổng {int(data.get("total_n") or 0)}'
                    if peak is not None
                    else f'Tổng: {int(data.get("total_n") or 0)}'
                ),
                'data': series,
                'series': {'value': 'Sự kiện'},
            }

    # Plate flow → multiple-bar (IN/OUT) + vehicle mix as pie when few types
    by_dir = data.get('by_direction')
    by_type = data.get('by_vehicle_type')
    if isinstance(by_dir, dict) and by_dir:
        # Prefer cross-tab items when present: category = vehicle_type, value=IN, value2=OUT
        if (
            isinstance(items, list)
            and items
            and isinstance(items[0], dict)
            and 'direction' in items[0]
            and 'vehicle_type' in items[0]
        ):
            buckets: dict[str, dict[str, int]] = {}
            for row in items:
                if not isinstance(row, dict):
                    continue
                vt = str(row.get('vehicle_type') or 'UNKNOWN')
                d = str(row.get('direction') or '')
                n = int(row.get('n') or 0)
                buckets.setdefault(vt, {'IN': 0, 'OUT': 0})
                if d in ('IN', 'OUT'):
                    buckets[vt][d] = buckets[vt].get(d, 0) + n
            series = [
                {
                    'label': vt,
                    'value': vals.get('IN', 0),
                    'value2': vals.get('OUT', 0),
                }
                for vt, vals in sorted(
                    buckets.items(),
                    key=lambda x: -(x[1].get('IN', 0) + x[1].get('OUT', 0)),
                )[:8]
            ]
            if series:
                return {
                    'type': 'multiple-bar',
                    'title': 'Ra / vào theo loại xe',
                    'description': data.get('day') or 'hôm nay',
                    'footer': f'Tổng: {int(data.get("total_n") or 0)}',
                    'data': series,
                    'series': {'value': 'Vào (IN)', 'value2': 'Ra (OUT)'},
                }
        # Fallback: direction totals as pie
        series = [
            {
                'label': k,
                'value': int(v or 0),
                'key': str(k).lower(),
            }
            for k, v in by_dir.items()
        ]
        if series:
            return {
                'type': 'pie',
                'title': 'Tỷ lệ ra / vào',
                'description': data.get('day') or 'hôm nay',
                'footer': f'Tổng: {int(data.get("total_n") or 0)}',
                'data': series,
            }
    if isinstance(by_type, dict) and by_type:
        series = [
            {
                'label': k,
                'value': int(v or 0),
                'key': re.sub(r'[^a-z0-9]+', '_', str(k).lower()).strip('_') or 'other',
            }
            for k, v in sorted(by_type.items(), key=lambda x: -int(x[1] or 0))
        ]
        if series:
            return {
                'type': 'pie',
                'title': 'Tỷ lệ loại xe',
                'description': data.get('day') or 'hôm nay',
                'footer': f'Tổng: {int(data.get("total_n") or 0)}',
                'data': series[:6],
            }
    return None


def _wrap_reply_vi(raw: str) -> str:
    """Keep tool payloads tiny: reply_vi + optional chart (no fat items[])."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(data, dict) or data.get('error'):
        return raw
    reply = data.get('reply_vi')
    if not reply:
        return raw
    slim = {
        'ok': data.get('ok', True),
        'reply_vi': reply,
        'agent_instruction': (
            'Trả lời ĐÚNG nội dung reply_vi bằng tiếng Việt rồi STOP '
            '(FinishTool). Không English. Không gọi thêm tool. '
            'CẤM tham số summary/security_risk.'
        ),
    }
    for key in (
        'day',
        'days',
        'days_list',
        'total_n',
        'items_n',
        'query',
        'peak_hour',
        'seats_available',
    ):
        if key in data:
            slim[key] = data[key]
    chart = _build_chart(data)
    if chart:
        slim['chart'] = chart
    return json.dumps(slim, ensure_ascii=False)


@mcp.tool()
async def vms_search_plate(
    q: str,
    days: int = 90,
    limit: int = 5,
    summary: str | None = None,
) -> str:
    """Lookup ONE concrete plate string only (q like 30A-12345 / 14H03464).

    ONLY pass q= (optional days/limit). Never pass summary/security_risk.
    Default: 90 ngày, top 5 mốc gần nhất. NEVER use for 'số xe ngày …'.
    """
    _ = summary  # agent often invents this; ignore so the call does not fail
    q_stripped = (q or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', q_stripped) or q_stripped.lower() in {
        'xe',
        'biển số',
        'bien so',
        'plate',
        'vehicle',
        'count',
        'today',
        'hôm nay',
        'hom nay',
    }:
        return json.dumps(
            {
                'error': 400,
                'detail': (
                    'Wrong tool. Call vms_count_vehicles(day="YYYY-MM-DD") '
                    'for vehicle counts, then reply with reply_vi.'
                ),
                'hint_vi': (
                    'Sai tool. Đếm xe → vms_count_vehicles(day=…), đọc reply_vi.'
                ),
                'use_instead': 'vms_count_vehicles',
            },
            ensure_ascii=False,
        )
    raw = await _get(
        '/api/infra/analytics/search-plate',
        {'q': q, 'days': days, 'limit': limit},
    )
    return _wrap_reply_vi(raw)


@mcp.tool()
async def vms_trace_plate(
    q: str,
    days: int = 90,
    limit: int = 5,
    summary: str | None = None,
) -> str:
    """Truy vết / lịch sử di chuyển một biển số. CHỈ truyền q=biển số.

    Mặc định top 5 mốc gần nhất trong 90 ngày. Ví dụ: q='14H03464'.
    Đọc reply_vi → trả lời → Finish. Không summary.
    """
    return await vms_search_plate(q=q, days=days, limit=limit, summary=summary)


@mcp.tool()
async def vms_search_person(q: str, days: int = 90, limit: int = 50) -> str:
    """Find face/zone events matching a person name."""
    return await _get(
        '/api/infra/analytics/search-person',
        {'q': q, 'days': days, 'limit': limit},
    )


@mcp.tool()
async def vms_daily(
    days: int = 30,
    module: str | None = None,
    day: str | None = None,
) -> str:
    """Daily plate/event counts. Prefer vms_count_vehicles for 'đếm xe'.

    For a calendar day: day='YYYY-MM-DD', module='PLATE'.
    Có reply_vi → copy. Không summary.
    """
    mod = (module or 'PLATE').strip() or 'PLATE'
    day_s = (day or '').strip()
    if day_s:
        return await vms_count_vehicles(day=day_s)
    # Rolling window — wrap with a short Vietnamese line.
    raw = await _get(
        '/api/infra/analytics/daily',
        {'days': days, 'module': mod},
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict) and data.get('error'):
        return raw
    total = int((data or {}).get('total_n') or 0)
    items = (data or {}).get('items') or []
    # "Ngày gần nhất có dữ liệu" when rolling window has rows.
    latest = ''
    latest_n = 0
    by_day: dict[str, int] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        d = str(row.get('day') or '')[:10]
        if not d:
            continue
        by_day[d] = by_day.get(d, 0) + int(row.get('n') or 0)
    if by_day:
        latest = max(by_day)
        latest_n = by_day[latest]
    if latest:
        y, m, d = latest.split('-')
        reply = f'Ngày gần nhất có dữ liệu là {d}/{m}/{y}: {latest_n} lượt biển số.'
    else:
        reply = f'{int(days)} ngày gần đây có {total} lượt biển số.'
    return json.dumps(
        {
            'ok': True,
            'days': days,
            'module': mod,
            'total_n': total,
            'latest_day': latest or None,
            'latest_n': latest_n,
            'reply_vi': reply,
            'agent_instruction': (
                'Trả lời ĐÚNG 1 dòng reply_vi bằng tiếng Việt. '
                'Không viết English. Không gọi thêm tool.'
            ),
        },
        ensure_ascii=False,
    )


def _with_reply_vi(raw: str) -> str:
    return _wrap_reply_vi(raw)


@mcp.tool()
async def vms_plate_flow(day: str | None = None, summary: str | None = None) -> str:
    """Biểu đồ / thống kê lượt xe RA–VÀO + phân loại xe máy / ô tô / xe tải.

    Dùng khi user hỏi: ra vào, IN/OUT, xe máy, oto, xe tải, phân loại loại xe.
    day=YYYY-MM-DD hoặc bỏ trống = hôm nay (giờ VN). Có reply_vi → copy.
    Số chỗ (5/7/9…) hiện chưa có trong kho — tool sẽ nói rõ trong reply_vi.
    """
    _ = summary
    params: dict[str, Any] = {}
    if day:
        params['day'] = day
    return _with_reply_vi(await _get('/api/infra/analytics/plate-flow', params))


@mcp.tool()
async def vms_plate_by_manufacturer(
    day: str | None = None,
    vehicle_type: str = 'CAR',
    limit: int = 20,
    summary: str | None = None,
) -> str:
    """Số liệu ô tô (hoặc loại xe) theo hãng / manufacturer trong một ngày.

    Ví dụ: 'Số liệu oto theo hãng xe trong hôm nay' → day bỏ trống, vehicle_type=CAR.
    Có reply_vi → copy nguyên.
    """
    _ = summary
    params: dict[str, Any] = {
        'vehicle_type': vehicle_type or 'CAR',
        'limit': limit,
    }
    if day:
        params['day'] = day
    return _with_reply_vi(
        await _get('/api/infra/analytics/plate-by-manufacturer', params)
    )


@mcp.tool()
async def vms_intrusion_peak(day: str | None = None, summary: str | None = None) -> str:
    """Khung giờ xâm nhập (ANOMALY INTRUSION_DETECTION) nhiều nhất trong ngày.

    Ví dụ: 'Khung thời gian xảy ra xâm nhập nhiều nhất hôm nay'.
    day=YYYY-MM-DD hoặc trống = hôm nay VN. Có reply_vi → copy.
    """
    _ = summary
    params: dict[str, Any] = {}
    if day:
        params['day'] = day
    return _with_reply_vi(await _get('/api/infra/analytics/intrusion-peak', params))


@mcp.tool()
async def vms_query(
    action: str,
    day: str | None = None,
    days: int | None = None,
    days_list: str | None = None,
    month: str | None = None,
    q: str | None = None,
    vehicle_type: str | None = None,
    limit: int | None = None,
) -> str:
    """ClickHouse VMS — ONE tool for all analytics. Copy reply_vi; no English.

    action (required):
      count — đếm tổng biển.
             day=YYYY-MM-DD | days_list=CSV | month=YYYY-MM (tháng đến nay, line chart)
             omit day/month = ngày gần nhất
             + vehicle_type=CAR|MOTORCYCLE|TRUCK CHỈ khi user hỏi rõ loại xe
      flow — ra/vào + breakdown loại xe. day?
      manufacturer — theo hãng. day?, vehicle_type=CAR
      trace — truy vết biển. q=biển (bắt buộc)
      intrusion — khung giờ xâm nhập peak. day?
    "tháng 9 đến nay" / "biểu đồ số lượng xe trong tháng" → action=count month=YYYY-MM
    Dates = ISO. Never invent numbers. Never use MOTORBIKE (dùng MOTORCYCLE).
    """
    act = (action or '').strip().lower()
    vt = _norm_vehicle_type(vehicle_type)

    if act in ('count', 'dem', 'đếm', 'daily'):
        # Month / multi-day chart wins over a mistaken vehicle_type.
        if (month or '').strip() or (days_list or '').strip():
            return await vms_count_vehicles(
                day=day, days=days, days_list=days_list, month=month
            )
        if vt:
            return await _count_by_vehicle_type(day=day, vehicle_type=vt)
        return await vms_count_vehicles(
            day=day, days=days, days_list=days_list, month=month
        )
    if act in ('flow', 'plate_flow', 'ra_vao', 'in_out'):
        return await vms_plate_flow(day=day)
    if act in ('manufacturer', 'hang', 'hãng', 'brand'):
        return await vms_plate_by_manufacturer(
            day=day,
            vehicle_type=vt or 'CAR',
            limit=int(limit) if limit is not None else 20,
        )
    if act in ('trace', 'plate', 'bien', 'biển'):
        plate = (q or '').strip()
        if not plate:
            return json.dumps(
                {
                    'error': 400,
                    'reply_vi': 'Thiếu biển số. Gọi lại vms_query(action=trace, q="<biển>").',
                },
                ensure_ascii=False,
            )
        return await vms_trace_plate(
            q=plate,
            days=int(days) if days is not None else 90,
            limit=int(limit) if limit is not None else 5,
        )
    if act in ('intrusion', 'xam_nhap', 'xâm nhập', 'peak'):
        return await vms_intrusion_peak(day=day)
    return json.dumps(
        {
            'error': 400,
            'reply_vi': (
                'action không hợp lệ. Dùng: count | flow | manufacturer | '
                'trace | intrusion.'
            ),
            'got': action,
        },
        ensure_ascii=False,
    )


def _norm_vehicle_type(raw: str | None) -> str | None:
    if not raw:
        return None
    t = raw.strip().upper().replace(' ', '_')
    aliases = {
        'MOTORBIKE': 'MOTORCYCLE',
        'BIKE': 'MOTORCYCLE',
        'XE_MAY': 'MOTORCYCLE',
        'MOTO': 'MOTORCYCLE',
        'OTO': 'CAR',
        'O_TO': 'CAR',
        'CAR': 'CAR',
        'MOTORCYCLE': 'MOTORCYCLE',
        'TRUCK': 'TRUCK',
        'BUS': 'BUS',
        'ALL': 'ALL',
    }
    return aliases.get(
        t, t if t in {'CAR', 'MOTORCYCLE', 'TRUCK', 'BUS', 'ALL'} else None
    )


async def _count_by_vehicle_type(*, day: str | None, vehicle_type: str) -> str:
    """Focused count for one vehicle_type via plate-flow breakdown."""
    params: dict[str, Any] = {}
    if day:
        params['day'] = day
    raw = await _get('/api/infra/analytics/plate-flow', params)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if not isinstance(data, dict) or data.get('error'):
        return raw
    by_type = data.get('by_vehicle_type') or {}
    n = int(by_type.get(vehicle_type) or 0)
    day_s = (data.get('day') or day or '').strip()
    labels = {
        'CAR': 'ô tô',
        'MOTORCYCLE': 'xe máy',
        'TRUCK': 'xe tải',
        'BUS': 'xe buýt',
    }
    label = labels.get(vehicle_type, vehicle_type.lower())
    if day_s and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day_s):
        y, m, d = day_s.split('-')
        reply = f'Ngày {d}/{m}/{y} có {n} lượt {label}.'
    else:
        reply = f'Hôm nay có {n} lượt {label}.'
    return json.dumps(
        {
            'ok': True,
            'day': day_s or None,
            'vehicle_type': vehicle_type,
            'total_n': n,
            'by_vehicle_type': by_type,
            'reply_vi': reply,
            'agent_instruction': (
                'Trả lời ĐÚNG 1 dòng reply_vi bằng tiếng Việt. '
                'Không viết English. Không gọi thêm tool.'
            ),
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def infra_resolve_server(q: str, limit: int = 10) -> str:
    """Resolve a host by IP, name, tag, or last IPv4 octet.

    On \"ssh vào 250\" call with q=\"250\", confirm name/IP/user/id in one line,
    then STOP. Do not invent follow-up commands. Only infra_run after the user
    gives an explicit command. Prefer this over the local ssh binary.
    """
    raw = await _get('/api/infra/servers/resolve', {'q': q, 'limit': limit})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if (
        data.get('do_not_call_infra_run')
        and data.get('count') == 1
        and data.get('items')
    ):
        sid = str(data['items'][0].get('id') or '')
        reply = str(
            data.get('assistant_reply_vi')
            or 'Đã SSH tới host. Gõ lệnh tiếp theo nếu cần (không sudo).'
        )
        if sid:
            _CONNECT_ONLY_UNTIL[sid] = (
                time.time() + _CONNECT_ONLY_TTL_SEC,
                reply,
            )
    return raw


@mcp.tool()
async def infra_clear_connect_gate(server_id: str) -> str:
    """Clear connect-only gate before infra_run when the user sent a new shell command."""
    return await _delete(f'/api/infra/servers/{server_id}/connect-only-gate')


@mcp.tool()
async def infra_run(
    server_id: str,
    command: str,
    confirm_destructive: bool = False,
    timeout_sec: int = 120,
) -> str:
    """Run a shell command on a resolved infra host via gateway SSH credentials.

    Never use local `ssh user@host`. Pass server_id UUID from infra_resolve_server
    (never a last octet like \"250\"). Only call when the user explicitly gave the
    command — do not invent ip/sudo/nginx/ls. Do not narrate or tutorialize the
    stdout unless asked. Destructive commands need confirm_destructive=true after
    the user agrees. Never call with sudo — host login password is not sudo.
    """
    now = time.time()
    gate = _CONNECT_ONLY_UNTIL.get(server_id)
    if gate is not None:
        expires, reply_vi = gate
        if now < expires:
            return json.dumps(
                {
                    'ok': False,
                    'connect_only': True,
                    'ssh_ok': True,
                    'assistant_reply_vi': reply_vi,
                    'agent_instruction': (
                        'User chỉ yêu cầu ssh vào host. Trả lời đúng 1 dòng '
                        'assistant_reply_vi. Không gọi infra_run lại.'
                    ),
                    'server_id': server_id,
                },
                ensure_ascii=False,
            )
        _CONNECT_ONLY_UNTIL.pop(server_id, None)

    if _SUDO_RE.search(command or ''):
        return json.dumps(
            {
                'ok': False,
                'sudo_blocked': True,
                'ssh_ok': True,
                'assistant_reply_vi': _SUDO_BLOCKED_REPLY_VI,
                'agent_instruction': (
                    'Trả lời đúng 1 dòng assistant_reply_vi. '
                    'Không giải thích harness/sudo/askpass bằng tiếng Anh.'
                ),
                'server_id': server_id,
            },
            ensure_ascii=False,
        )

    return await _post(
        f'/api/infra/servers/{server_id}/run',
        {
            'command': command,
            'confirm_destructive': confirm_destructive,
            'timeout_sec': timeout_sec,
        },
        timeout=float(timeout_sec) + 30.0,
    )


def main() -> None:
    _apply_mcp_tool_filter()
    mcp.run(transport='stdio')


def _apply_mcp_tool_filter() -> None:
    """Shrink tool schemas so the LLM picks tools faster (less TTFT).

    MCP_VMS_ONLY=1 (default for Agent Canvas): expose only ``vms_query``.
    ClickHouse covers count/flow/manufacturer/trace/intrusion via ``action=``.
    No SSH tools on the lean path.
    """
    flag = os.getenv('MCP_VMS_ONLY', '').lower() in ('1', 'true')
    if flag:
        keep = {'vms_query'}
    else:
        # Full catalog for non-lean deployments (legacy + SSH).
        keep = set(mcp._tool_manager._tools.keys())  # noqa: SLF001
    names = list(mcp._tool_manager._tools.keys())  # noqa: SLF001
    for name in names:
        if name not in keep:
            try:
                mcp.remove_tool(name)
            except Exception:  # noqa: BLE001
                mcp._tool_manager._tools.pop(name, None)  # noqa: SLF001


if __name__ == '__main__':
    main()
