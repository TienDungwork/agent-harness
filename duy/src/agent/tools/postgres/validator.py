from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_START_OK = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_STRINGS = re.compile(r"('([^']|'')*')|(\"([^\"]|\"\")*\")", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TABLE_REF = re.compile(
    r"\b(?:from|join)\s+(?:only\s+)?(?:[a-zA-Z_][\w]*\.)?([a-zA-Z_][\w]*)",
    re.IGNORECASE,
)
_CTE_NAME = re.compile(r"\b([a-zA-Z_][\w]*)\s+as\s*\(", re.IGNORECASE)
_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")
_FN_FROM = re.compile(
    r"\b(extract|substring|overlay|trim)\s*\([^)]*\)",
    re.IGNORECASE,
)

_BLOCKED = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|truncate|create|grant|revoke|"
    r"copy|execute|call|do|lock|vacuum|comment|security|listen|notify|"
    r"into|for\s+update|pg_sleep"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason}


def _strip_noise(sql: str) -> str:
    sql = _BLOCK_COMMENT.sub(" ", sql)
    sql = _LINE_COMMENT.sub(" ", sql)
    sql = _STRINGS.sub("''", sql)
    return sql


def _table_columns(ds: dict[str, Any]) -> set[str]:
    schema = ds.get("schema") or {}
    cols = schema.get("columns") or []
    names: set[str] = set()
    for col in cols:
        if isinstance(col, dict) and col.get("column_name"):
            names.add(str(col["column_name"]).lower())
        elif isinstance(col, str):
            names.add(col.lower())
    return names


def _schema_check(cleaned: str, datasets: list[dict[str, Any]]) -> ValidationResult | None:
    allowed = {str(ds.get("table") or "").lower() for ds in datasets if ds.get("table")}
    if not allowed:
        return None
    scan = _FN_FROM.sub(" ", cleaned)
    cte = {m.group(1).lower() for m in _CTE_NAME.finditer(scan)}
    referenced = [m.group(1).lower() for m in _TABLE_REF.finditer(scan)]
    unknown = [t for t in referenced if t not in allowed and t not in cte]
    if unknown:
        return ValidationResult(
            False,
            f"Bảng không có trong schema: {unknown[0]}. Chỉ dùng: {', '.join(sorted(allowed))}",
        )

    by_table = {str(ds.get("table") or "").lower(): _table_columns(ds) for ds in datasets}
    if not any(by_table.values()):
        return None
    used_tables = [t for t in referenced if t in by_table]
    if not used_tables:
        return None
    own_cols: set[str] = set()
    for t in used_tables:
        own_cols |= by_table.get(t) or set()
    other_cols: set[str] = set()
    for name, cols in by_table.items():
        if name not in used_tables:
            other_cols |= cols
    mixed = (other_cols - own_cols) & {m.group(1).lower() for m in _IDENT.finditer(cleaned)}
    if mixed:
        col = sorted(mixed)[0]
        return ValidationResult(
            False,
            f"Cột {col} không thuộc bảng {', '.join(used_tables)}. Không trộn cột giữa các bảng.",
        )
    return None


def validate_sql(sql: str, datasets: list[dict[str, Any]] | None = None) -> ValidationResult:
    if not sql or not sql.strip():
        return ValidationResult(False, "SQL rỗng")

    raw = sql.strip()
    if not _START_OK.match(raw):
        return ValidationResult(False, "Chỉ cho phép câu bắt đầu bằng SELECT hoặc WITH")

    body = raw.rstrip().rstrip(";")
    if ";" in body:
        return ValidationResult(False, "Không cho phép multi-statement")

    cleaned = _strip_noise(body)
    hit = _BLOCKED.search(cleaned)
    if hit:
        return ValidationResult(False, f"Cấm token: {hit.group(0).upper()}")

    if datasets:
        schema_err = _schema_check(cleaned, datasets)
        if schema_err is not None:
            return schema_err

    return ValidationResult(True)
