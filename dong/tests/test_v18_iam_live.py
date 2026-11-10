"""Live IAM Hưng Phú — login thật + /auth/me + resolve AccessContext.

Chạy khi IAM_LIVE=1 và IAM_TEST_PASSWORD set (trong .env). Bỏ qua nếu thiếu.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

from src.domain.authz.domain_guard import question_domains_allowed
from src.domain.authz.resolve import AccessDenied, access_context_from_user_ctx
from src.infra.auth.iam_client import fetch_auth_me
from src.shared.config import settings

_LIVE = (os.getenv('IAM_LIVE') or '').strip() in ('1', 'true', 'True', 'yes')
_PASS = (os.getenv('IAM_TEST_PASSWORD') or '').strip()
_BASE = (os.getenv('IAM_BASE_URL') or getattr(settings, 'iam_base_url', '') or '').rstrip('/')

pytestmark = pytest.mark.skipif(
    not _LIVE or not _PASS or not _BASE,
    reason='Set IAM_LIVE=1, IAM_TEST_PASSWORD, IAM_BASE_URL để chạy live',
)

_ACCOUNTS = {
    'hp_anninh': 'SECURITY_DEPT',
    'hp_moitruong': 'ENVIRONMENT_DEPT',
    'hp_vanhanh': 'OPERATIONS_DEPT',
    'hp_banlanhdao': 'BOARD_DIRECTOR',
    'hp_orgadmin': 'BOARD_DIRECTOR',
}


def _login(username: str) -> str:
    req = urllib.request.Request(
        f'{_BASE}/api/v1/auth/login',
        data=json.dumps({'username': username, 'password': _PASS, 'remember': True}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')[:300]
        pytest.fail(f'login {username} HTTP {exc.code}: {body}')
    token = data['access_token'] if 'access_token' in data else None
    assert token, f'login {username} thiếu access_token: {data}'
    return str(token)


@pytest.mark.parametrize('username,expected_group', list(_ACCOUNTS.items()))
def test_live_login_me_role_group(username, expected_group, monkeypatch):
    monkeypatch.setattr(settings, 'iam_base_url', _BASE, raising=False)
    token = _login(username)
    user_ctx = fetch_auth_me(token)
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=103)
    assert ctx.role_group == expected_group
    assert ctx.effective_org_id == 103
    assert ctx.user_id == username


def test_live_security_denies_energy_and_org_106(monkeypatch):
    monkeypatch.setattr(settings, 'iam_base_url', _BASE, raising=False)
    token = _login('hp_anninh')
    user_ctx = fetch_auth_me(token)
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=103)
    ok, forbidden = question_domains_allowed('Hôm nay điện năng tiêu thụ bao nhiêu?', ctx)
    assert ok is False
    assert 'energy' in forbidden
    ok_fire, _ = question_domains_allowed('Có cảnh báo cháy khói không?', ctx)
    assert ok_fire is True
    with pytest.raises(AccessDenied):
        access_context_from_user_ctx(user_ctx, requested_org_id=106)


def test_live_security_scope_site_5(monkeypatch):
    monkeypatch.setattr(settings, 'iam_base_url', _BASE, raising=False)
    token = _login('hp_anninh')
    ctx = access_context_from_user_ctx(fetch_auth_me(token), requested_org_id=103)
    assert 5 in ctx.scope.site_ids
    assert ctx.scope.unrestricted is False
