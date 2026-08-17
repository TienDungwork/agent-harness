from __future__ import annotations

import time

from auth.session import SessionManager, SessionPayload
from config import Settings


def test_session_roundtrip():
    settings = Settings(session_secret='test-secret-please-change')
    mgr = SessionManager(settings)
    token = mgr.issue(
        SessionPayload(
            user_id='u1',
            username='demo',
            is_admin=False,
            access_token='atk',
            refresh_token='rtk',
            issued_at=int(time.time()),
        )
    )
    loaded = mgr.load(token)
    assert loaded.user_id == 'u1'
    assert loaded.username == 'demo'
    assert loaded.access_token == 'atk'


def test_session_tamper_rejected():
    settings = Settings(session_secret='test-secret-please-change')
    mgr = SessionManager(settings)
    token = mgr.issue(
        SessionPayload(
            user_id='u1',
            username='demo',
            is_admin=False,
            access_token='atk',
            refresh_token=None,
            issued_at=int(time.time()),
        )
    )
    try:
        mgr.load(token + 'x')
        raise AssertionError('expected PermissionError')
    except PermissionError:
        pass
