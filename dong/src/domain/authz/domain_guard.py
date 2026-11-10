"""RBAC guards — A: bảng/lĩnh vực (chính); keyword chỉ lớp phụ sớm."""
from __future__ import annotations

from src.domain.authz.access_context import AccessContext
from src.domain.authz.role_matrix import domain_for_table, infer_domains_from_question

DENY_REPLY = (
    'Bạn không có quyền xem thông tin thuộc lĩnh vực này theo phân quyền bộ phận. '
    'Vui lòng hỏi trong phạm vi dashboard được cấp, hoặc liên hệ quản trị viên.'
)

_DOMAIN_LABELS: dict[str, str] = {
    'traffic': 'Phương tiện / biển số (ITS)',
    'security_events': 'Vùng cấm / bất thường an ninh',
    'fire_smoke': 'Cháy khói (PCCC)',
    'face': 'Nhận diện khuôn mặt',
    'camera': 'Camera / live / registry',
    'iot_env': 'Môi trường / IoT / AQI',
    'energy': 'Điện năng',
    'water': 'Nước',
    'lighting': 'Chiếu sáng',
    'assets': 'Tài sản / thiết bị',
    'maintenance': 'Bảo trì',
    'docs_security': 'Tài liệu an ninh / AIOC',
    'docs_env': 'Tài liệu môi trường',
    'docs_ops': 'Tài liệu vận hành',
}

_CAPABILITY_HINTS = (
    'phân quyền',
    'được hỏi',
    'được xem',
    'có thể hỏi',
    'được phép hỏi',
    'quyền của tôi',
    'phạm vi của tôi',
    'loại event',
    'loại sự kiện',
    'những loại event',
    'những loại sự kiện',
    'hỏi được những',
    'hỏi được gì',
    'hỏi những câu',
    'domain nào',
    'lĩnh vực nào',
    'liên quan đến loại',
)


def is_access_capability_question(question: str) -> bool:
    """Câu meta hỏi 'tôi được hỏi/xem gì' theo role — không phải truy vấn số liệu."""
    q = (question or '').lower()
    if not q:
        return False
    if any(h in q for h in _CAPABILITY_HINTS):
        # Tránh bắt nhầm câu hỏi số liệu thật: "có bao nhiêu event xâm nhập"
        if any(x in q for x in ('bao nhiêu', 'hôm nay', 'thống kê', 'liệt kê theo', 'từ ngày', 'đến ngày')):
            if 'phân quyền' not in q and 'có thể hỏi' not in q and 'được hỏi' not in q and 'được phép' not in q:
                return False
        return True
    return False


def format_access_capability_reply(ctx: AccessContext | None) -> str:
    """Trả lời phạm vi domain theo AccessContext hiện tại."""
    if ctx is None:
        return (
            'Chưa có ngữ cảnh đăng nhập IAM. Hãy đăng nhập tài khoản bộ phận '
            'rồi hỏi lại về phạm vi được phép.'
        )
    if ctx.allows_all_domains():
        return (
            f'Tài khoản **{ctx.user_id}** (nhóm **{ctx.role_group}**) được xem **toàn bộ** '
            'lĩnh vực event/dashboard (Ban lãnh đạo / admin).\n'
            'Bạn có thể hỏi xe, vùng cấm, cháy khói, khuôn mặt, môi trường, điện/nước, camera…'
        )
    labels = [_DOMAIN_LABELS[d] for d in sorted(ctx.allowed_domains) if d in _DOMAIN_LABELS]
    if not labels:
        labels = sorted(ctx.allowed_domains)
    lines = '\n'.join(f'- {x}' for x in labels)
    tabs = ', '.join(ctx.dashboard_tabs) if ctx.dashboard_tabs else '(không có tab)'
    return (
        f'Tài khoản **{ctx.user_id}** thuộc nhóm **{ctx.role_group}** '
        f'(org {ctx.effective_org_id}).\n'
        f'Tab dashboard: {tabs}.\n'
        f'Bạn **được hỏi** các lĩnh vực:\n{lines}\n'
        'Câu hỏi ngoài danh sách trên sẽ bị từ chối quyền (không chạy SQL domain cấm).'
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
