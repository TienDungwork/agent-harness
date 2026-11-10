"""v18 IAM RBAC — resolve, matrix, domain guard, SQL scope."""
from __future__ import annotations

import pytest

from src.domain.authz.access_context import AccessContext, GeoScope
from src.domain.authz.domain_guard import DENY_REPLY, filter_tables_by_access, question_domains_allowed
from src.domain.authz.resolve import AccessDenied, access_context_from_user_ctx, bypass_access_context
from src.domain.authz.role_matrix import domains_for_role_group, normalize_role_group, tables_for_domains
from src.domain.agents.analytics.sql_agent.tools.scope import apply_access_scope


def test_normalize_role_group_kcn_prefix():
    assert normalize_role_group('KCN_SECURITY_DEPT') == 'SECURITY_DEPT'
    assert normalize_role_group(None, ['KCN_ENVIRONMENT_DEPT']) == 'ENVIRONMENT_DEPT'
    assert normalize_role_group(None, ['ORG_ADMIN']) == 'BOARD_DIRECTOR'
    assert normalize_role_group('security') == 'SECURITY_DEPT'
    assert normalize_role_group('BLD_HP') == 'BOARD_DIRECTOR'
    assert normalize_role_group('VH_HP') == 'OPERATIONS_DEPT'


def test_access_context_from_real_iam_hp_anninh_shape():
    """IAM bỏ dashboard_role_group ở top-level permissions — dùng role_code + role_details."""
    user_ctx = {
        'id': 341,
        'keycloak_username': 'hp_anninh',
        'organization_id': 103,
        'allowed_organization_ids': [103],
        'is_system_admin': False,
        'is_organization_admin': False,
        'role_code': 'SECURITY_DEPT',
        'roles': ['SECURITY_DEPT'],
        'role_details': [
            {
                'code': 'SECURITY_DEPT',
                'permissions': {
                    'dashboard_role_group': 'security',
                    'dashboard_tabs': ['tongquan', 'anninh', 'giaothong', 'pccc'],
                },
            }
        ],
        'permissions': {
            'dashboard_tabs': ['tongquan', 'anninh', 'giaothong', 'pccc'],
            'events': ['read', 'update'],
        },
        'scope': {
            'unrestricted': False,
            'organization_ids': [103],
            'site_ids': [5],
            'area_ids': [18, 19, 20, 32, 76],
            'zone_ids': [23, 24, 25, 40, 51],
            'device_ids': None,
        },
    }
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=103)
    assert ctx.role_group == 'SECURITY_DEPT'
    assert ctx.user_id == 'hp_anninh'
    assert ctx.scope.site_ids == [5]
    assert 'fire_smoke_event' in ctx.allowed_tables
    with pytest.raises(AccessDenied):
        access_context_from_user_ctx(user_ctx, requested_org_id=106)


def test_org_admin_maps_to_board():
    user_ctx = {
        'id': 336,
        'keycloak_username': 'hp_orgadmin',
        'organization_id': 103,
        'allowed_organization_ids': [103],
        'is_system_admin': False,
        'is_organization_admin': True,
        'role_code': 'ORG_ADMIN',
        'roles': ['ORG_ADMIN'],
        'permissions': {'dashboard_tabs': ['tongquan']},
        'scope': {'unrestricted': True, 'organization_ids': [103]},
    }
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=103)
    assert ctx.role_group == 'BOARD_DIRECTOR'


def test_security_tables_include_fire_and_plate():
    domains = domains_for_role_group('SECURITY_DEPT')
    tables = tables_for_domains(domains)
    assert 'fire_smoke_event' in tables
    assert 'plate_event' in tables
    assert 'smf_face_events' in tables


def test_operations_excludes_face():
    tables = tables_for_domains(domains_for_role_group('OPERATIONS_DEPT'))
    assert 'smf_face_events' not in tables
    assert 'camera_registry' in tables


def test_access_context_org_forbidden():
    user_ctx = {
        'id': 1,
        'organization_id': 103,
        'allowed_organization_ids': [103],
        'is_system_admin': False,
        'roles': ['SECURITY_DEPT'],
        'permissions': {'dashboard_role_group': 'SECURITY_DEPT'},
        'scope': {'unrestricted': False, 'organization_ids': [103], 'site_ids': [], 'area_ids': [], 'zone_ids': []},
    }
    with pytest.raises(AccessDenied):
        access_context_from_user_ctx(user_ctx, requested_org_id=999)


def test_access_context_security_ok():
    user_ctx = {
        'id': 42,
        'keycloak_username': 'an_ninh',
        'organization_id': 103,
        'allowed_organization_ids': [103],
        'is_system_admin': False,
        'roles': ['SECURITY_DEPT'],
        'permissions': {'dashboard_role_group': 'SECURITY_DEPT', 'dashboard_tabs': ['security']},
        'scope': {
            'unrestricted': False,
            'organization_ids': [103],
            'site_ids': [5],
            'area_ids': [18],
            'zone_ids': [],
            'device_ids': None,
        },
    }
    ctx = access_context_from_user_ctx(user_ctx, requested_org_id=103)
    assert ctx.role_group == 'SECURITY_DEPT'
    assert ctx.effective_org_id == 103
    assert ctx.user_id == 'an_ninh'
    assert ctx.scope.site_ids == [5]


def test_domain_guard_security_denies_energy():
    ctx = AccessContext(
        user_id='u',
        effective_org_id=103,
        role_group='SECURITY_DEPT',
        allowed_domains=domains_for_role_group('SECURITY_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('SECURITY_DEPT')),
    )
    ok, forbidden = question_domains_allowed('Hôm nay điện năng tiêu thụ bao nhiêu?', ctx)
    assert ok is False
    assert 'energy' in forbidden


def test_domain_guard_security_allows_fire():
    ctx = AccessContext(
        user_id='u',
        effective_org_id=103,
        role_group='SECURITY_DEPT',
        allowed_domains=domains_for_role_group('SECURITY_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('SECURITY_DEPT')),
    )
    ok, _ = question_domains_allowed('Có bao nhiêu cảnh báo cháy khói hôm nay?', ctx)
    assert ok is True


def test_filter_tables_environment_blocks_plate():
    ctx = AccessContext(
        user_id='u',
        effective_org_id=103,
        role_group='ENVIRONMENT_DEPT',
        allowed_domains=domains_for_role_group('ENVIRONMENT_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('ENVIRONMENT_DEPT')),
    )
    assert filter_tables_by_access(['plate_event', 'fire_smoke_event'], ctx) == []


def test_bypass_board_director(monkeypatch):
    monkeypatch.setattr('src.domain.authz.resolve.settings.db_organization_id', 103)
    ctx = bypass_access_context(user_id='dev')
    assert ctx.bypass is True
    assert ctx.role_group == 'BOARD_DIRECTOR'
    assert ctx.effective_org_id == 103


def test_apply_access_scope_org_and_site(monkeypatch):
    monkeypatch.setattr(
        'src.domain.agents.analytics.sql_agent.tools.scope.get_catalog',
        lambda: {
            'plate_event': {
                'columns': {
                    'organization_id': 'int',
                    'site_id': 'int',
                    'event_time': 'timestamptz',
                }
            }
        },
    )
    ctx = AccessContext(
        user_id='u',
        effective_org_id=103,
        role_group='SECURITY_DEPT',
        allowed_domains=domains_for_role_group('SECURITY_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('SECURITY_DEPT')),
        scope=GeoScope(unrestricted=False, site_ids=[5], area_ids=[], zone_ids=[]),
    )
    sql = apply_access_scope('SELECT count(*) FROM plate_event', ctx)
    assert 'organization_id = 103' in sql
    assert 'site_id = ANY' in sql
    assert '5' in sql


def test_deny_reply_nonempty():
    assert 'không có quyền' in DENY_REPLY.lower() or 'không có quyền' in DENY_REPLY


def test_validate_sql_blocks_table_outside_role():
    from src.domain.authz.access_context import bind_access_context, reset_access_context
    from src.infra.db.validator import validate_sql

    ctx = AccessContext(
        user_id='env',
        effective_org_id=103,
        role_group='ENVIRONMENT_DEPT',
        allowed_domains=domains_for_role_group('ENVIRONMENT_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('ENVIRONMENT_DEPT')),
    )
    tok = bind_access_context(ctx)
    try:
        val = validate_sql('SELECT count(*) FROM plate_event')
        assert val.ok is False
        assert 'plate_event' in val.reason.lower() or 'không nằm' in val.reason.lower()
    finally:
        reset_access_context(tok)


def test_validate_sql_allows_security_fire_table():
    from src.domain.authz.access_context import bind_access_context, reset_access_context
    from src.infra.db.validator import validate_sql

    ctx = AccessContext(
        user_id='sec',
        effective_org_id=103,
        role_group='SECURITY_DEPT',
        allowed_domains=domains_for_role_group('SECURITY_DEPT'),
        allowed_tables=tables_for_domains(domains_for_role_group('SECURITY_DEPT')),
    )
    tok = bind_access_context(ctx)
    try:
        val = validate_sql('SELECT count(*) FROM fire_smoke_event')
        assert val.ok is True
    finally:
        reset_access_context(tok)
