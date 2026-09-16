from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from infra.analytics import (
    clamp_days,
    require_day,
    require_event_type,
    require_module,
    require_org_id,
    require_person,
    require_plate,
    summary,
    vms_scope_sql,
)


def _ch_settings(**kwargs):
    data = {
        'ch_url': '',
        'ch_user': 'vms_ro',
        'ch_password': '',
        'ch_database': 'vms',
        'vms_organization_id': 106,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_require_module_allowlist():
    assert require_module('anomaly') == 'ANOMALY'
    assert require_module('ppe') == 'PPE'
    assert require_module('') == ''
    try:
        require_module("ANOMALY'; DROP")
        raise AssertionError('expected HTTPException')
    except HTTPException as exc:
        assert exc.status_code == 400


def test_require_plate_rejects_sql():
    assert require_plate('30a-123.45') == '30A-123.45'
    try:
        require_plate("x' OR 1=1")
        raise AssertionError('expected HTTPException')
    except HTTPException as exc:
        assert exc.status_code == 400


def test_require_plate_rejects_calendar_day():
    with pytest.raises(HTTPException) as ei:
        require_plate('2026-09-06')
    assert ei.value.status_code == 400
    assert 'vms_daily' in str(ei.value.detail)


def test_require_person_and_event_type():
    assert require_person('Nguyen Van A')
    try:
        require_person('a;{}')
        raise AssertionError('expected HTTPException')
    except HTTPException as exc:
        assert exc.status_code == 400
    assert require_event_type('INTRUSION_DETECTION') == 'INTRUSION_DETECTION'
    try:
        require_event_type('INTRUSION_DETECTION;select')
        raise AssertionError('expected HTTPException')
    except HTTPException as exc:
        assert exc.status_code == 400


def test_clamp_days():
    assert clamp_days(None) == 7
    assert clamp_days(0) == 1
    assert clamp_days(9999) == 1095


def test_require_day():
    assert require_day(None) == ''
    assert require_day('2026-09-06') == '2026-09-06'
    with pytest.raises(HTTPException) as ei:
        require_day('09/06/2026')
    assert ei.value.status_code == 400


def test_summary_503_when_unconfigured():
    settings = _ch_settings(ch_url='', ch_password='')
    with pytest.raises(HTTPException) as ei:
        summary(settings, days=7, module='ANOMALY')  # type: ignore[arg-type]
    assert ei.value.status_code == 503


def test_require_org_id():
    assert require_org_id(_ch_settings()) == 106
    with pytest.raises(HTTPException) as ei:
        require_org_id(_ch_settings(vms_organization_id=0))
    assert ei.value.status_code == 503


def test_vms_scope_sql_org_and_hierarchy():
    sql, params = vms_scope_sql(_ch_settings())
    assert 'organization_id = {org_id:Int64}' in sql
    assert params == {'org_id': 106}
    sql, params = vms_scope_sql(_ch_settings(), site_id=7, iam_area_id=2)
    assert 'site_id = {site_id:Int64}' in sql
    assert 'iam_area_id = {iam_area_id:Int64}' in sql
    assert 'iam_zone_id' not in sql
    assert params == {'org_id': 106, 'site_id': 7, 'iam_area_id': 2}


def test_summary_sql_includes_org(monkeypatch):
    from infra import analytics as mod

    captured: dict = {}

    def fake_query_json(settings, sql, params):
        captured['sql'] = sql
        captured['params'] = params
        return [{'module': 'PLATE', 'event_type': 'PLATE', 'n': 4}]

    monkeypatch.setattr(mod, 'query_json', fake_query_json)
    out = mod.summary(_ch_settings(), days=7, module='PLATE')
    assert 'organization_id = {org_id:Int64}' in captured['sql']
    assert captured['params']['org_id'] == 106
    assert out['organization_id'] == 106
    assert out['total_n'] == 4


def test_is_vehicle_count_question():
    from infra.analytics import is_vehicle_count_question

    assert is_vehicle_count_question('đếm số lượng ô tô ngày 05 09 2026')
    assert is_vehicle_count_question('Count vehicles on 2026-09-06')
    assert is_vehicle_count_question('Hôm nay có bao nhiêu xe')
    assert not is_vehicle_count_question('ssh vào server 1')


def test_ask_vehicle_count_parses_dmy(monkeypatch):
    from infra import analytics as mod

    captured = {}

    def fake_daily(settings, *, days, module, day=None):
        captured['day'] = day
        return {'total_n': 125458, 'items': []}

    monkeypatch.setattr(mod, 'daily', fake_daily)
    out = mod.ask_vehicle_count(_ch_settings(), q='đếm số lương ô tô ngày 05 09 2026')
    assert captured['day'] == '2026-09-05'
    assert out['total_n'] == 125458
    assert out['reply_vi'] == 'Ngày 05/09/2026 có 125458 lượt biển số.'


def test_plate_flow_builds_reply(monkeypatch):
    from infra import analytics as mod

    captured: dict = {}

    def fake_query_json(settings, sql, params):
        captured['sql'] = sql
        captured['params'] = params
        return [
            {'direction': 'IN', 'vehicle_type': 'MOTORCYCLE', 'n': 10},
            {'direction': 'OUT', 'vehicle_type': 'CAR', 'n': 5},
        ]

    monkeypatch.setattr(mod, 'query_json', fake_query_json)
    out = mod.plate_flow(_ch_settings(), day='2026-09-06')
    assert out['total_n'] == 15
    assert out['organization_id'] == 106
    assert 'xe máy' in out['reply_vi']
    assert out['seats_available'] is False
    assert 'organization_id = {org_id:Int64}' in captured['sql']
    assert captured['params']['org_id'] == 106


def test_plate_flow_narrows_site(monkeypatch):
    from infra import analytics as mod

    captured: dict = {}

    def fake_query_json(settings, sql, params):
        captured['sql'] = sql
        captured['params'] = params
        return []

    monkeypatch.setattr(mod, 'query_json', fake_query_json)
    mod.plate_flow(_ch_settings(), day='2026-09-06', site_id=12)
    assert 'site_id = {site_id:Int64}' in captured['sql']
    assert captured['params']['site_id'] == 12


def test_intrusion_peak_empty(monkeypatch):
    from infra import analytics as mod

    monkeypatch.setattr(mod, 'query_json', lambda *a, **k: [])
    out = mod.intrusion_peak(_ch_settings(), day='2026-09-15')
    assert out['total_n'] == 0
    assert out['organization_id'] == 106
    assert 'không có' in out['reply_vi'].lower()
