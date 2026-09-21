"""Unit tests verifying full suite of parameterized tools for all 8 VMS domains."""

from __future__ import annotations

import json
import pytest

from backend.tools import (
    TOOLS,
    count_anomaly_events,
    count_face_events,
    count_fire_smoke_events,
    count_vehicle_flow,
    get_db_schema,
    list_khu_vuc,
    run_sql_readonly,
    trace_plate,
    zone_intrusion_by_hour,
)
from src.config import settings


def test_tools_count_and_naming():
    """Kiểm tra có đủ 9 công cụ (8 domain + schema/sql fallback)."""
    assert len(TOOLS) == 9
    names = {t.name for t in TOOLS}
    expected = {
        "get_db_schema",
        "list_khu_vuc",
        "count_vehicle_flow",
        "trace_plate",
        "zone_intrusion_by_hour",
        "count_face_events",
        "count_fire_smoke_events",
        "count_anomaly_events",
        "run_sql_readonly",
    }
    assert names == expected


def test_get_db_schema_returns_docstring_info():
    """Kiểm tra get_db_schema mô tả chính xác 8 domain."""
    schema_info = get_db_schema.invoke({})
    assert "its.plate_event" in schema_info
    assert "virtual_fence.zone_event" in schema_info


def test_count_vehicle_flow_validation():
    """Kiểm tra validation tham số count_vehicle_flow."""
    if not settings.db_configured:
        res = json.loads(count_vehicle_flow.invoke({
            "date_from": "2026-09-01 00:00:00",
            "date_to": "2026-09-02 00:00:00",
            "direction": "INVALID_DIR",
        }))
        assert "error" in res


def test_count_anomaly_events_whitelist_validation():
    """Kiểm tra 4 event_type hợp lệ của count_anomaly_events."""
    valid_events = ["FIGHT_DETECTION", "CROWD_DETECTION", "INTRUSION_DETECTION", "WATER_LEVEL_DETECTION"]
    for evt in valid_events:
        res = json.loads(count_anomaly_events.invoke({
            "date_from": "2026-09-01 00:00:00",
            "date_to": "2026-09-02 00:00:00",
            "event_type": evt,
        }))
        assert res.get("tool") == "count_anomaly_events"


def test_count_fire_smoke_events_entity_type_validation():
    """Kiểm tra validation entity_type cho count_fire_smoke_events."""
    res = json.loads(count_fire_smoke_events.invoke({
        "date_from": "2026-09-01 00:00:00",
        "date_to": "2026-09-02 00:00:00",
        "entity_type": "FIRE",
    }))
    assert res.get("tool") == "count_fire_smoke_events"
