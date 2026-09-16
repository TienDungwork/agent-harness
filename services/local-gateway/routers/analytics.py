from __future__ import annotations

from typing import Any, TypedDict

from config import Settings, get_settings
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from infra.analytics import (
    ask_vehicle_count,
    daily,
    daily_multi,
    intrusion_peak,
    is_vehicle_count_question,
    month_days_to_date,
    plate_by_manufacturer,
    plate_flow,
    require_days_list,
    search_person,
    search_plate,
    summary,
    top_cameras,
)
from infra.vms_agent import stream_vms_agent
from pydantic import BaseModel, Field
from storage.users import AuthUser

from routers.infra import get_auth_user

router = APIRouter(prefix='/api/infra/analytics', tags=['infra-analytics'])


class HierarchyFilter(TypedDict):
    site_id: int | None
    iam_area_id: int | None
    iam_zone_id: int | None


def hierarchy_filter(
    site_id: int | None = Query(default=None, ge=0),
    iam_area_id: int | None = Query(default=None, ge=0),
    iam_zone_id: int | None = Query(default=None, ge=0),
) -> HierarchyFilter:
    """Narrow within the server-side organization. organization_id is not a query param."""
    return {
        'site_id': site_id,
        'iam_area_id': iam_area_id,
        'iam_zone_id': iam_zone_id,
    }


class AskBody(BaseModel):
    q: str = Field(default='', description='Natural-language vehicle count question')


class ChatBody(BaseModel):
    message: str
    history: list[dict[str, Any]] | None = None


@router.post('/ask')
def analytics_ask(
    body: AskBody,
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Fast NL vehicle-count → reply_vi. No agent / LLM / MCP."""
    q = (body.q or '').strip()
    if not is_vehicle_count_question(q):
        return {
            'ok': False,
            'error': 'not_vehicle_count',
            'reply_vi': (
                'Câu này không phải đếm xe. Hãy hỏi dạng '
                '"Số xe ngày 06/09/2026" hoặc "Hôm nay có bao nhiêu xe".'
            ),
        }
    return ask_vehicle_count(settings, q=q)


@router.post('/chat')
def analytics_chat(
    body: ChatBody,
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """KCN-style streaming agent for VMS counts (LLM + count_vehicles tool)."""
    import json

    message = (body.message or '').strip()
    if not message:
        raise HTTPException(status_code=400, detail='message is required')

    def gen():
        try:
            for event in stream_vms_agent(settings, message, body.history):
                yield f'data: {json.dumps(event, ensure_ascii=False)}\n\n'
        except Exception as exc:  # noqa: BLE001
            yield f'data: {json.dumps({"error": str(exc)}, ensure_ascii=False)}\n\n'
        yield 'data: [DONE]\n\n'

    return StreamingResponse(gen(), media_type='text/event-stream')


@router.get('/summary')
def analytics_summary(
    days: int = Query(default=7, ge=1, le=1095),
    module: str | None = None,
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Counts by module/event_type over the last N days. Agent must not write SQL."""
    return summary(settings, days=days, module=module, **scope)


@router.get('/top-cameras')
def analytics_top_cameras(
    days: int = Query(default=30, ge=1, le=1095),
    module: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return top_cameras(
        settings,
        days=days,
        module=module,
        event_type=event_type,
        limit=limit,
        **scope,
    )


@router.get('/search-plate')
def analytics_search_plate(
    q: str,
    days: int = Query(default=90, ge=1, le=1095),
    limit: int = Query(default=5, ge=1, le=100),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return search_plate(settings, q=q, days=days, limit=limit, **scope)


@router.get('/search-person')
def analytics_search_person(
    q: str,
    days: int = Query(default=90, ge=1, le=1095),
    limit: int = Query(default=50, ge=1, le=100),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return search_person(settings, q=q, days=days, limit=limit, **scope)


@router.get('/daily')
def analytics_daily(
    days: int = Query(default=30, ge=1, le=1095),
    module: str | None = None,
    day: str | None = Query(
        default=None, description='Calendar day YYYY-MM-DD (overrides rolling days)'
    ),
    days_list: str | None = Query(
        default=None,
        description='Comma-separated YYYY-MM-DD for multi-day plate counts',
    ),
    month: str | None = Query(
        default=None,
        description='YYYY-MM — expand to days 1..(today VN or month-end) for line chart',
    ),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Pre-aggregated daily counts from vms.ai_events_daily."""
    if month:
        return daily_multi(
            settings,
            days_list=month_days_to_date(month),
            module=module or 'PLATE',
            **scope,
        )
    if days_list:
        return daily_multi(
            settings,
            days_list=require_days_list(days_list),
            module=module or 'PLATE',
            **scope,
        )
    return daily(settings, days=days, module=module, day=day, **scope)


@router.get('/plate-flow')
def analytics_plate_flow(
    day: str | None = Query(
        default=None, description='VN calendar day YYYY-MM-DD; default=today VN'
    ),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """PLATE by direction × vehicle_type (IN/OUT, xe máy/ô tô/tải)."""
    return plate_flow(settings, day=day, **scope)


@router.get('/plate-by-manufacturer')
def analytics_plate_by_manufacturer(
    day: str | None = Query(default=None),
    vehicle_type: str = Query(default='CAR'),
    limit: int = Query(default=20, ge=1, le=100),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return plate_by_manufacturer(
        settings, day=day, vehicle_type=vehicle_type, limit=limit, **scope
    )


@router.get('/intrusion-peak')
def analytics_intrusion_peak(
    day: str | None = Query(default=None),
    scope: HierarchyFilter = Depends(hierarchy_filter),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Hour buckets for ANOMALY INTRUSION_DETECTION."""
    return intrusion_peak(settings, day=day, **scope)
