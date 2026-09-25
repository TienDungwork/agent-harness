"""Inject organization_id scope into generated SQL when DB_ORGANIZATION_ID is set."""

from __future__ import annotations

import re

from src.config import settings
from src.db.catalog import get_catalog

_TABLE_REF = re.compile(
    r'\b(?:from|join)\s+(?:only\s+)?(?:(?:"?[a-zA-Z_][\w]*"?)\.)?"?([a-zA-Z_][\w]*)"?',
    re.IGNORECASE,
)
_TAIL_CLAUSE = re.compile(
    r"\b(group\s+by|order\s+by|limit|having|offset)\b",
    re.IGNORECASE,
)


def format_org_scope_for_prompt() -> str:
    """Hint for sql_agent when tenant org is configured."""
    oid = settings.db_organization_id
    if oid and oid > 0:
        return (
            f"Lọc theo tổ chức KCN: thêm `organization_id = {oid}` "
            "khi bảng trong schema có cột organization_id."
        )
    return ""


def apply_organization_scope(sql: str) -> str:
    """Append organization_id filter if configured and SQL touches scoped tables."""
    oid = settings.db_organization_id
    if not oid or oid <= 0:
        return sql

    body = (sql or "").strip().rstrip(";")
    if not body or re.search(r"\borganization_id\b", body, re.IGNORECASE):
        return sql

    org_tables = {
        tbl
        for tbl, meta in get_catalog().items()
        if "organization_id" in (meta.get("columns") or {})
    }
    used = {m.group(1).lower() for m in _TABLE_REF.finditer(body)}
    if not used.intersection(org_tables):
        return sql

    tail = _TAIL_CLAUSE.search(body)
    insert_at = tail.start() if tail else len(body)
    clause = f"organization_id = {int(oid)}"
    head = body[:insert_at].rstrip()
    rest = body[insert_at:].lstrip()

    if re.search(r"\bwhere\b", head, re.IGNORECASE):
        scoped = f"{head} AND {clause}"
    else:
        scoped = f"{head} WHERE {clause}"

    return f"{scoped} {rest}".strip() if rest else scoped
