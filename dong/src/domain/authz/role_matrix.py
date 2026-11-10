"""Ma trận dashboard_role_group → domains → tables (catalog dong)."""
from __future__ import annotations

DOMAIN_TABLES: dict[str, frozenset[str]] = {
    'traffic': frozenset({'plate_event', 'plate_blacklist', 'plate_whitelist', 'plate_violation_case'}),
    'security_events': frozenset({'zone_event', 'restricted_zones', 'zone_access_policy', 'zone_incident', 'anomaly_event'}),
    'fire_smoke': frozenset({'fire_smoke_event'}),
    'face': frozenset({'smf_face_events', 'smf_employees', 'smf_departments', 'view_face_events'}),
    'camera': frozenset({'camera_registry'}),
    'iot_env': frozenset(),
    'energy': frozenset(),
    'water': frozenset(),
    'lighting': frozenset(),
    'assets': frozenset({'camera_registry'}),
    'maintenance': frozenset(),
    'docs_security': frozenset(),
    'docs_env': frozenset(),
    'docs_ops': frozenset(),
}

ROLE_GROUP_DOMAINS: dict[str, frozenset[str]] = {
    'BOARD_DIRECTOR': frozenset({'*'}),
    'SECURITY_DEPT': frozenset({'traffic', 'security_events', 'fire_smoke', 'face', 'camera', 'docs_security'}),
    'ENVIRONMENT_DEPT': frozenset({'iot_env', 'energy', 'water', 'lighting', 'docs_env'}),
    'OPERATIONS_DEPT': frozenset({'camera', 'assets', 'maintenance', 'lighting', 'energy', 'water', 'docs_ops'}),
}

TABLE_TO_DOMAIN: dict[str, str] = {}
for _domain, _tables in DOMAIN_TABLES.items():
    for _t in _tables:
        TABLE_TO_DOMAIN[_t] = _domain

# Keyword heuristics → domain (câu hỏi tiếng Việt)
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    'traffic': ('biển số', 'xe cộ', 'xe vào', 'xe ra', 'phương tiện', 'anpr', 'plate', 'giao thông', 'lưu lượng'),
    'security_events': ('xâm nhập', 'hàng rào', 'vùng cấm', 'anomaly', 'bất thường', 'đám đông', 'ẩu đả', 'leo trèo'),
    'fire_smoke': ('cháy', 'khói', 'hỏa hoạn', 'fire', 'smoke'),
    'face': ('khuôn mặt', 'chấm công', 'nhân viên', 'face', 'nhận diện mặt'),
    'camera': ('camera', 'trực tuyến', 'ngoại tuyến', 'live', 'playback'),
    'iot_env': ('môi trường', 'aqi', 'khí thải', 'cảm biến', 'iot'),
    'energy': ('điện năng', 'năng lượng', 'tiêu thụ điện', 'kwh'),
    'water': ('nước thải', 'cấp nước', 'thoát nước', 'lưu lượng nước'),
    'lighting': ('chiếu sáng', 'đèn đường', 'đèn led'),
    'assets': ('tài sản', 'thiết bị'),
    'maintenance': ('bảo trì', 'phiếu công việc', 'sửa chữa'),
    'docs_security': ('hướng dẫn camera', 'quy trình an ninh'),
    'docs_env': ('hướng dẫn môi trường', 'hướng dẫn iot'),
    'docs_ops': ('hướng dẫn bảo trì', 'quản lý thiết bị'),
}


# Alias IAM thực tế (role_code / dashboard_role_group chữ thường / mã cũ HP)
_ROLE_ALIASES: dict[str, str] = {
    'SECURITY': 'SECURITY_DEPT',
    'ENVIRONMENT': 'ENVIRONMENT_DEPT',
    'OPERATIONS': 'OPERATIONS_DEPT',
    'LEADERSHIP': 'BOARD_DIRECTOR',
    'BLD_HP': 'BOARD_DIRECTOR',
    'VH_HP': 'OPERATIONS_DEPT',
    'ORG_ADMIN': 'BOARD_DIRECTOR',
    'SITE_ADMIN': 'BOARD_DIRECTOR',
    'AREA_ADMIN': 'BOARD_DIRECTOR',  # domain full; geo hẹp ở scope
    'ZONE_ADMIN': 'BOARD_DIRECTOR',
    'SUPER_ADMIN': 'BOARD_DIRECTOR',
    'SYSTEM_ADMIN': 'BOARD_DIRECTOR',
    'KCN_SITE_MANAGER': 'BOARD_DIRECTOR',
    'KCN_BOARD_DIRECTOR': 'BOARD_DIRECTOR',
}


def _canon_role(raw: str) -> str | None:
    key = raw.strip().upper()
    if not key:
        return None
    if key in ROLE_GROUP_DOMAINS:
        return key
    if key.startswith('KCN_'):
        stripped = key[4:]
        if stripped in ROLE_GROUP_DOMAINS:
            return stripped
        if stripped in _ROLE_ALIASES:
            return _ROLE_ALIASES[stripped]
    if key in _ROLE_ALIASES:
        return _ROLE_ALIASES[key]
    return None


def normalize_role_group(raw: str | None, roles: list[str] | None=None) -> str:
    """Chuẩn hoá mã nhóm IOC từ role_code / roles / dashboard_role_group."""
    if raw:
        hit = _canon_role(raw)
        if hit:
            return hit
    for role in roles or []:
        hit = _canon_role(str(role))
        if hit:
            return hit
    return 'BOARD_DIRECTOR'


def domains_for_role_group(role_group: str) -> frozenset[str]:
    if role_group in ROLE_GROUP_DOMAINS:
        return ROLE_GROUP_DOMAINS[role_group]
    return ROLE_GROUP_DOMAINS['BOARD_DIRECTOR']


def tables_for_domains(domains: frozenset[str]) -> frozenset[str]:
    if '*' in domains:
        out: set[str] = set()
        for tables in DOMAIN_TABLES.values():
            out.update(tables)
        return frozenset(out)
    out = set()
    for d in domains:
        if d in DOMAIN_TABLES:
            out.update(DOMAIN_TABLES[d])
    return frozenset(out)


def infer_domains_from_question(question: str) -> frozenset[str]:
    """Suy domain từ keyword câu hỏi (có thể nhiều domain)."""
    low = (question or '').lower()
    hit: set[str] = set()
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in low for kw in kws):
            hit.add(domain)
    return frozenset(hit)


def domain_for_table(table: str) -> str | None:
    t = (table or '').lower()
    if t in TABLE_TO_DOMAIN:
        return TABLE_TO_DOMAIN[t]
    return None
