"""RBAC guards — A: bảng/lĩnh vực (chính); keyword chỉ lớp phụ sớm."""
from __future__ import annotations

from src.domain.authz.access_context import AccessContext
from src.domain.authz.role_matrix import domain_for_table, infer_domains_from_question

DENY_REPLY = (
    'Bạn không có quyền xem thông tin thuộc lĩnh vực này theo phân quyền bộ phận. '
    'Vui lòng hỏi trong phạm vi dashboard được cấp, hoặc liên hệ quản trị viên.'
)


def rbac_table_allowlist(ctx: AccessContext | None) -> set[str] | None:
    """None = không siết thêm (dùng catalog). Set = chỉ các bảng role được phép."""
    if ctx is None or ctx.allows_all_domains():
        return None
    return set(ctx.allowed_tables)


def question_domains_allowed(question: str, ctx: AccessContext | None) -> tuple[bool, frozenset[str]]:
    """Lớp phụ: keyword early-deny. Cổng chính vẫn là filter bảng + validate SQL."""
    if ctx is None or ctx.allows_all_domains():
        return True, frozenset()
    inferred = infer_domains_from_question(question)
    if not inferred:
        return True, frozenset()
    forbidden = frozenset(d for d in inferred if d not in ctx.allowed_domains)
    if forbidden and not (inferred - forbidden):
        return False, forbidden
    if forbidden:
        return True, forbidden
    return True, frozenset()


def filter_tables_by_access(tables: list[str], ctx: AccessContext | None) -> list[str]:
    """Cổng chính A: chỉ giữ bảng trong allowlist bộ phận."""
    if ctx is None or ctx.allows_all_domains():
        return list(tables)
    allowed = ctx.allowed_tables
    out: list[str] = []
    for t in tables:
        domain = domain_for_table(t)
        if domain is None:
            continue
        if t in allowed or domain in ctx.allowed_domains:
            out.append(t)
    return out


def docs_domain_allowed(question: str, ctx: AccessContext | None) -> bool:
    if ctx is None or ctx.allows_all_domains():
        return True
    inferred = infer_domains_from_question(question)
    if not inferred:
        return bool(ctx.allowed_domains & {'docs_security', 'docs_ops', 'docs_env', 'camera', '*'})
    if not (inferred & ctx.allowed_domains):
        return False
    return True
