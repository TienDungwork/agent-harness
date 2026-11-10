"""Inject organization + geo scope into generated SQL from AccessContext."""
from __future__ import annotations

import re
from typing import Any

from src.domain.authz.access_context import AccessContext, get_bound_access_context
from src.infra.db.catalog import get_catalog
from src.shared.config import settings


_TABLE_REF = re.compile(
    r'\b(?:from|join)\s+(?:only\s+)?(?:(?:"?[a-zA-Z_][\w]*"?)\.)?"?([a-zA-Z_][\w]*)"?',
    re.IGNORECASE,
)
_TAIL_CLAUSE = re.compile(r'\b(group\s+by|order\s+by|limit|having|offset)\b', re.IGNORECASE)

# Cột geo theo tên thường gặp trên catalog dong / vms
_ORG_COLS = ('organization_id',)
_SITE_COLS = ('site_id',)
_AREA_COLS = ('area_id', 'iam_area_id')
_ZONE_COLS = ('zone_id', 'iam_zone_id')
_DEVICE_COLS = ('camera_id', 'device_id', 'id')


def _ctx_org_id(ctx: AccessContext | None) -> int | None:
    if ctx is not None and ctx.effective_org_id is not None and int(ctx.effective_org_id) > 0:
        return int(ctx.effective_org_id)
    oid = settings.db_organization_id
    if oid and oid > 0:
        return int(oid)
    return None


def format_org_scope_for_prompt(ctx: AccessContext | None=None) -> str:
    """Hint for sql_agent when tenant org / geo is configured."""
    return format_access_scope_for_prompt(ctx)


def format_access_scope_for_prompt(ctx: AccessContext | None=None) -> str:
    if ctx is None:
        ctx = get_bound_access_context()
    oid = _ctx_org_id(ctx)
    parts: list[str] = []
    if oid:
        parts.append(f'Thêm `organization_id = {oid}` khi bảng có cột organization_id.')
    if ctx is not None and not ctx.scope.unrestricted:
        if ctx.scope.site_ids:
            parts.append(f'Lọc site_id IN ({", ".join(str(x) for x in ctx.scope.site_ids)}).')
        if ctx.scope.area_ids:
            parts.append(f'Lọc area_id/iam_area_id IN ({", ".join(str(x) for x in ctx.scope.area_ids)}).')
        if ctx.scope.zone_ids:
            parts.append(f'Lọc zone_id/iam_zone_id IN ({", ".join(str(x) for x in ctx.scope.zone_ids)}).')
        if ctx.scope.device_ids:
            parts.append('Chỉ thiết bị/camera trong danh sách được cấp (device_ids).')
    return ' '.join(parts)


def _table_columns(table: str) -> set[str]:
    meta = get_catalog()
    t = table.lower()
    if t not in meta:
        return set()
    cols = meta[t]['columns'] if 'columns' in meta[t] else None
    if isinstance(cols, dict):
        return {str(k).lower() for k in cols}
    if isinstance(cols, list):
        return {str(c).lower() for c in cols}
    return set()


def _pick_col(available: set[str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in available:
            return c
    return None


def _append_clause(sql: str, clause: str) -> str:
    body = (sql or '').strip().rstrip(';')
    if not body or not clause:
        return sql
    # already present (simple)
    if re.search(re.escape(clause.split('=')[0].strip()) if '=' in clause else clause[:20], body, re.IGNORECASE):
        # still append geo; only skip exact org if already filtered
        pass
    tail = _TAIL_CLAUSE.search(body)
    insert_at = tail.start() if tail else len(body)
    head = body[:insert_at].rstrip()
    rest = body[insert_at:].lstrip()
    if re.search(r'\bwhere\b', head, re.IGNORECASE):
        scoped = f'{head} AND {clause}'
    else:
        scoped = f'{head} WHERE {clause}'
    return f'{scoped} {rest}'.strip() if rest else scoped


def _sql_int_array(ids: list[int]) -> str:
    return 'ARRAY[' + ', '.join(str(int(x)) for x in ids) + ']::int[]'


def _sql_text_array(ids: list[str]) -> str:
    escaped = ', '.join("'" + str(x).replace("'", "''") + "'" for x in ids)
    return 'ARRAY[' + escaped + ']::text[]'


def apply_organization_scope(sql: str, ctx: AccessContext | None=None) -> str:
    """Backward-compatible wrapper → apply_access_scope."""
    return apply_access_scope(sql, ctx)


def apply_access_scope(sql: str, ctx: AccessContext | None=None) -> str:
    """Append org + geo filters when catalog columns exist on used tables."""
    if ctx is None:
        ctx = get_bound_access_context()
    body = (sql or '').strip().rstrip(';')
    if not body:
        return sql
    used = {m.group(1).lower() for m in _TABLE_REF.finditer(body)}
    if not used:
        return sql

    oid = _ctx_org_id(ctx)
    catalog = get_catalog()
    org_tables = {
        tbl for tbl, meta in catalog.items()
        if 'organization_id' in {str(k).lower() for k in ((meta['columns'] if 'columns' in meta else None) or {})}
    }
    out = body

    if oid and used.intersection(org_tables) and not re.search(r'\borganization_id\b', out, re.IGNORECASE):
        out = _append_clause(out, f'organization_id = {int(oid)}')

    if ctx is None or ctx.scope.unrestricted:
        return out

    # Geo: apply if ANY used table has the column
    def _any_col(candidates: tuple[str, ...]) -> str | None:
        for tbl in used:
            col = _pick_col(_table_columns(tbl), candidates)
            if col:
                return col
        return None

    # shortcut: catalog event dong hiện chỉ có organization_id — site/area/zone
    # chỉ inject khi cột thật sự có trong catalog; bổ sung cột rồi bỏ comment này.
    if ctx.scope.site_ids:
        col = _any_col(_SITE_COLS)
        if col and not re.search(rf'\b{col}\b', out, re.IGNORECASE):
            out = _append_clause(out, f'{col} = ANY({_sql_int_array(ctx.scope.site_ids)})')
    if ctx.scope.area_ids:
        col = _any_col(_AREA_COLS)
        if col and not re.search(rf'\b{col}\b', out, re.IGNORECASE):
            out = _append_clause(out, f'{col} = ANY({_sql_int_array(ctx.scope.area_ids)})')
    if ctx.scope.zone_ids:
        col = _any_col(_ZONE_COLS)
        if col and not re.search(rf'\b{col}\b', out, re.IGNORECASE):
            out = _append_clause(out, f'{col} = ANY({_sql_int_array(ctx.scope.zone_ids)})')
    if ctx.scope.device_ids:
        col = _any_col(_DEVICE_COLS)
        if col and col != 'id' and not re.search(rf'\b{col}\b', out, re.IGNORECASE):
            out = _append_clause(out, f'{col}::text = ANY({_sql_text_array(ctx.scope.device_ids)})')

    return out
