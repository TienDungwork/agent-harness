from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from fastapi import APIRouter, Depends, Query
from infra.analytics import daily, search_person, search_plate, summary, top_cameras
from storage.users import AuthUser

from routers.infra import get_auth_user

router = APIRouter(prefix='/api/infra/analytics', tags=['infra-analytics'])


@router.get('/summary')
def analytics_summary(
    days: int = Query(default=7, ge=1, le=1095),
    module: str | None = None,
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Counts by module/event_type over the last N days. Agent must not write SQL."""
    return summary(settings, days=days, module=module)


@router.get('/top-cameras')
def analytics_top_cameras(
    days: int = Query(default=30, ge=1, le=1095),
    module: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return top_cameras(
        settings, days=days, module=module, event_type=event_type, limit=limit
    )


@router.get('/search-plate')
def analytics_search_plate(
    q: str,
    days: int = Query(default=180, ge=1, le=1095),
    limit: int = Query(default=50, ge=1, le=100),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return search_plate(settings, q=q, days=days, limit=limit)


@router.get('/search-person')
def analytics_search_person(
    q: str,
    days: int = Query(default=90, ge=1, le=1095),
    limit: int = Query(default=50, ge=1, le=100),
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return search_person(settings, q=q, days=days, limit=limit)


@router.get('/daily')
def analytics_daily(
    days: int = Query(default=30, ge=1, le=1095),
    module: str | None = None,
    _user: AuthUser = Depends(get_auth_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Pre-aggregated daily counts from vms.ai_events_daily."""
    return daily(settings, days=days, module=module)
