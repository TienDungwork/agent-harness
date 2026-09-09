from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from infra.analytics import (
    clamp_days,
    require_event_type,
    require_module,
    require_person,
    require_plate,
    summary,
)


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


def test_summary_503_when_unconfigured():
    settings = SimpleNamespace(
        ch_url='', ch_user='vms_ro', ch_password='', ch_database='vms'
    )
    with pytest.raises(HTTPException) as ei:
        summary(settings, days=7, module='ANOMALY')  # type: ignore[arg-type]
    assert ei.value.status_code == 503
