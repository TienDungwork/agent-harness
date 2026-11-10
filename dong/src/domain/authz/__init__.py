"""Authorization domain — AccessContext, role matrix, resolve, domain guard."""
from src.domain.authz.access_context import AccessContext, GeoScope, bind_access_context, get_bound_access_context, reset_access_context
from src.domain.authz.domain_guard import (
    DENY_REPLY,
    docs_domain_allowed,
    filter_tables_by_access,
    question_domains_allowed,
    rbac_table_allowlist,
)
from src.domain.authz.resolve import AccessDenied, access_context_from_user_ctx, bypass_access_context, resolve_access_context

__all__ = [
    'AccessContext',
    'GeoScope',
    'AccessDenied',
    'DENY_REPLY',
    'access_context_from_user_ctx',
    'bind_access_context',
    'bypass_access_context',
    'get_bound_access_context',
    'reset_access_context',
    'resolve_access_context',
    'docs_domain_allowed',
    'filter_tables_by_access',
    'question_domains_allowed',
    'rbac_table_allowlist',
]
