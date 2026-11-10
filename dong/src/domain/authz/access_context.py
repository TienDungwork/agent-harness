"""AccessContext — quyền user sau IAM /auth/me."""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field


@dataclass
class GeoScope:
    """Phạm vi địa lý từ IAM scope."""

    unrestricted: bool = False
    organization_ids: list[int] = field(default_factory=list)
    site_ids: list[int] = field(default_factory=list)
    area_ids: list[int] = field(default_factory=list)
    zone_ids: list[int] = field(default_factory=list)
    device_ids: list[str] | None = None


@dataclass
class AccessContext:
    """Ngữ cảnh phân quyền gắn vào mỗi lượt chat."""

    user_id: str
    effective_org_id: int | None
    role_group: str
    roles: list[str] = field(default_factory=list)
    dashboard_tabs: list[str] = field(default_factory=list)
    allowed_domains: frozenset[str] = field(default_factory=frozenset)
    allowed_tables: frozenset[str] = field(default_factory=frozenset)
    scope: GeoScope = field(default_factory=GeoScope)
    is_system_admin: bool = False
    is_organization_admin: bool = False
    bypass: bool = False

    def allows_all_domains(self) -> bool:
        return self.bypass or self.role_group == 'BOARD_DIRECTOR' or '*' in self.allowed_domains


_current_access: ContextVar[AccessContext | None] = ContextVar('access_context', default=None)


def bind_access_context(ctx: AccessContext | None) -> Token:
    return _current_access.set(ctx)


def reset_access_context(token: Token) -> None:
    _current_access.reset(token)


def get_bound_access_context() -> AccessContext | None:
    return _current_access.get()
