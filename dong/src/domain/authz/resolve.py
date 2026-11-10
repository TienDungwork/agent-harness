"""Resolve AccessContext từ IAM user_ctx + requested org."""
from __future__ import annotations

from typing import Any

from src.domain.authz.access_context import AccessContext, GeoScope
from src.domain.authz.role_matrix import domains_for_role_group, normalize_role_group, tables_for_domains
from src.shared.config import settings


class AccessDenied(Exception):
    """403 — không có quyền tổ chức / thiếu token khi bắt buộc."""

    def __init__(self, message: str, *, status_code: int=403):
        super().__init__(message)
        self.status_code = status_code


def _as_int_list(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _parse_scope(raw: Any) -> GeoScope:
    if not isinstance(raw, dict):
        return GeoScope()
    device_raw = raw['device_ids'] if 'device_ids' in raw else None
    device_ids: list[str] | None
    if device_raw is None:
        device_ids = None
    elif isinstance(device_raw, list):
        device_ids = [str(x) for x in device_raw]
    else:
        device_ids = None
    return GeoScope(
        unrestricted=bool(raw['unrestricted'] if 'unrestricted' in raw else False),
        organization_ids=_as_int_list(raw['organization_ids'] if 'organization_ids' in raw else None),
        site_ids=_as_int_list(raw['site_ids'] if 'site_ids' in raw else None),
        area_ids=_as_int_list(raw['area_ids'] if 'area_ids' in raw else None),
        zone_ids=_as_int_list(raw['zone_ids'] if 'zone_ids' in raw else None),
        device_ids=device_ids,
    )


def _effective_org_id(user_ctx: dict[str, Any], requested_org_id: int | None) -> int | None:
    is_system_admin = bool(user_ctx['is_system_admin'] if 'is_system_admin' in user_ctx else False)
    org_id = user_ctx['organization_id'] if 'organization_id' in user_ctx else None
    allowed_raw = user_ctx['allowed_organization_ids'] if 'allowed_organization_ids' in user_ctx else None
    allowed = set(_as_int_list(allowed_raw))
    if org_id is not None:
        try:
            allowed.add(int(org_id))
        except (TypeError, ValueError):
            pass

    if is_system_admin:
        if requested_org_id and requested_org_id > 0:
            return int(requested_org_id)
        return None

    if requested_org_id and requested_org_id > 0:
        if int(requested_org_id) not in allowed:
            raise AccessDenied('Bạn không có quyền truy cập dữ liệu của tổ chức này')
        return int(requested_org_id)

    if org_id is not None:
        try:
            return int(org_id)
        except (TypeError, ValueError):
            pass
    return None


def _role_group_from_role_details(user_ctx: dict[str, Any]) -> str | None:
    """IAM merge bỏ dashboard_role_group ở top-level — đọc role_details[].permissions."""
    details = user_ctx['role_details'] if 'role_details' in user_ctx else None
    if not isinstance(details, list):
        return None
    for item in details:
        if not isinstance(item, dict):
            continue
        perms = item['permissions'] if 'permissions' in item else None
        if isinstance(perms, dict) and 'dashboard_role_group' in perms and perms['dashboard_role_group']:
            return str(perms['dashboard_role_group'])
        if 'code' in item and item['code']:
            return str(item['code'])
    return None


def _resolve_effective_role_group(user_ctx: dict[str, Any], roles: list[str]) -> str:
    """Giống VMS: admin → full; role_code/roles; role_details.dashboard_role_group."""
    from src.domain.authz.role_matrix import _canon_role

    if bool(user_ctx['is_system_admin'] if 'is_system_admin' in user_ctx else False):
        return 'BOARD_DIRECTOR'
    if bool(user_ctx['is_organization_admin'] if 'is_organization_admin' in user_ctx else False):
        return 'BOARD_DIRECTOR'
    role_code = user_ctx['role_code'] if 'role_code' in user_ctx else None
    if role_code:
        hit = _canon_role(str(role_code))
        if hit:
            return hit
    for r in roles:
        hit = _canon_role(str(r))
        if hit:
            return hit
    detail = _role_group_from_role_details(user_ctx)
    if detail:
        hit = _canon_role(str(detail))
        if hit:
            return hit
    perms = user_ctx['permissions'] if 'permissions' in user_ctx else {}
    if isinstance(perms, dict) and 'dashboard_role_group' in perms and perms['dashboard_role_group']:
        hit = _canon_role(str(perms['dashboard_role_group']))
        if hit:
            return hit
    return 'BOARD_DIRECTOR'


def access_context_from_user_ctx(user_ctx: dict[str, Any], requested_org_id: int | None=None) -> AccessContext:
    """Build AccessContext từ JSON /auth/me (IAM Hưng Phú thực tế)."""
    perms = user_ctx['permissions'] if 'permissions' in user_ctx else {}
    if not isinstance(perms, dict):
        perms = {}
    roles_raw = user_ctx['roles'] if 'roles' in user_ctx else None
    roles = [str(r) for r in roles_raw] if isinstance(roles_raw, list) else []
    role_group = _resolve_effective_role_group(user_ctx, roles)
    domains = domains_for_role_group(role_group)
    tables = tables_for_domains(domains)
    tabs_raw = perms['dashboard_tabs'] if 'dashboard_tabs' in perms else None
    tabs = [str(t) for t in tabs_raw] if isinstance(tabs_raw, list) else []
    uid = user_ctx['id'] if 'id' in user_ctx else None
    user_id = str(uid) if uid is not None else 'default'
    if 'keycloak_username' in user_ctx and user_ctx['keycloak_username']:
        user_id = str(user_ctx['keycloak_username'])
    effective = _effective_org_id(user_ctx, requested_org_id)
    return AccessContext(
        user_id=user_id,
        effective_org_id=effective,
        role_group=role_group,
        roles=roles,
        dashboard_tabs=tabs,
        allowed_domains=domains,
        allowed_tables=tables,
        scope=_parse_scope(user_ctx['scope'] if 'scope' in user_ctx else None),
        is_system_admin=bool(user_ctx['is_system_admin'] if 'is_system_admin' in user_ctx else False),
        is_organization_admin=bool(user_ctx['is_organization_admin'] if 'is_organization_admin' in user_ctx else False),
        bypass=False,
    )


def bypass_access_context(*, user_id: str='default', org_id: int | None=None) -> AccessContext:
    """Local/eval khi IAM_REQUIRED=false."""
    oid = org_id if org_id is not None else (settings.db_organization_id or None)
    if oid is not None and int(oid) <= 0:
        oid = None
    domains = domains_for_role_group('BOARD_DIRECTOR')
    return AccessContext(
        user_id=user_id or 'default',
        effective_org_id=int(oid) if oid else None,
        role_group='BOARD_DIRECTOR',
        roles=['BOARD_DIRECTOR'],
        dashboard_tabs=[],
        allowed_domains=domains,
        allowed_tables=tables_for_domains(domains),
        scope=GeoScope(unrestricted=True, organization_ids=[int(oid)] if oid else []),
        is_system_admin=True,
        is_organization_admin=True,
        bypass=True,
    )


def resolve_access_context(*, token: str | None, requested_org_id: int | None, user_id_fallback: str='default') -> AccessContext:
    """Gate chính: IAM bắt buộc hoặc bypass."""
    if not settings.iam_required:
        if token:
            try:
                from src.infra.auth.iam_client import fetch_auth_me
                # Soft mode: nếu IAM OK thì tin user_id từ IAM, không ghi đè body client.
                return access_context_from_user_ctx(fetch_auth_me(token), requested_org_id)
            except Exception:
                pass
        return bypass_access_context(user_id=user_id_fallback, org_id=requested_org_id)
    if not token:
        raise AccessDenied('Thiếu Authorization Bearer token', status_code=401)
    from src.infra.auth.iam_client import IamError, fetch_auth_me
    try:
        user_ctx = fetch_auth_me(token)
    except IamError as exc:
        raise AccessDenied(str(exc), status_code=exc.status_code) from exc
    return access_context_from_user_ctx(user_ctx, requested_org_id)
