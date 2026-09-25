"""SQL validator — kiểm tra câu lệnh SELECT-only, an toàn và đúng schema (dong v5).

Chặn toàn bộ DML/DDL (DELETE, INSERT, UPDATE, DROP, ALTER, TRUNCATE,...), multi-statement,
kiểm tra whitelist bảng và cột từ catalog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from src.db.catalog import get_allowed_columns, get_allowed_tables

_START_OK = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_STRINGS = re.compile(r"('([^']|'')*')|(\"([^\"]|\"\")*\")", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TABLE_REF = re.compile(
    r'\b(?:from|join)\s+(?:only\s+)?(?:(?:"?[a-zA-Z_][\w]*"?)\.)?"?([a-zA-Z_][\w]*)"?',
    re.IGNORECASE,
)
_CTE_NAME = re.compile(r"\b([a-zA-Z_][\w]*)\s+as\s*\(", re.IGNORECASE)
_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")
_FN_FROM = re.compile(r"\b(extract|substring|overlay|trim)\s*\([^)]*\)", re.IGNORECASE)

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

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "reason": self.reason}


def _strip_noise(sql: str) -> str:
    """Loại bỏ comment và string literals để tránh false positives khi validate."""
    sql = _BLOCK_COMMENT.sub(" ", sql)
    sql = _LINE_COMMENT.sub(" ", sql)
    sql = _STRINGS.sub("''", sql)
    return sql


def validate_sql(
    sql: str,
    allowed_tables: set[str] | None = None,
) -> ValidationResult:
    """Kiểm tra câu SQL đọc-only và hợp lệ schema.

    - Bắt buộc bắt đầu bằng SELECT hoặc WITH.
    - Không cho phép multi-statement (;).
    - Chặn từ khóa DML/DDL (DELETE, INSERT, UPDATE, DROP, ALTER, TRUNCATE,...).
    - Whitelist bảng theo catalog.
    - Chặn trộn cột giữa các bảng không liên quan.
    """
    if not sql or not sql.strip():
        return ValidationResult(False, "SQL rỗng.")

    raw = sql.strip()
    if not _START_OK.match(raw):
        return ValidationResult(False, "Chỉ cho phép câu lệnh bắt đầu bằng SELECT hoặc WITH.")

    body = raw.rstrip().rstrip(";")
    if ";" in body:
        return ValidationResult(False, "Không cho phép multi-statement (;).")

    cleaned = _strip_noise(body)
    hit = _BLOCKED.search(cleaned)
    if hit:
        return ValidationResult(False, f"Cấm từ khóa ghi/DDL: {hit.group(0).upper()}.")

    # Kiểm tra bảng
    allowed = allowed_tables if allowed_tables is not None else get_allowed_tables()
    scan = _FN_FROM.sub(" ", cleaned)
    ctes = {m.group(1).lower() for m in _CTE_NAME.finditer(scan)}
    referenced = [m.group(1).lower() for m in _TABLE_REF.finditer(scan)]

    if not referenced:
        return ValidationResult(False, "Không tìm thấy bảng nguồn (FROM) trong câu SQL.")

    unknown_tables = [t for t in referenced if t not in allowed and t not in ctes]
    if unknown_tables:
        return ValidationResult(
            False,
            f"Bảng '{unknown_tables[0]}' không nằm trong danh mục cho phép. Chỉ dùng: {', '.join(sorted(allowed))}.",
        )

    # Kiểm tra đa database trong cùng một câu SQL (Cross-database query isolation)
    used_tables = [t for t in referenced if t in allowed]
    if len(used_tables) > 1:
        from src.db.catalog import get_database_for_table
        dbs = {get_database_for_table(t) for t in used_tables}
        if len(dbs) > 1:
            tbl_db_map = ", ".join(f"'{t}' (db {get_database_for_table(t)})" for t in used_tables)
            return ValidationResult(
                False,
                f"Không thể truy vấn đồng thời bảng từ nhiều database khác nhau trong cùng một câu SQL ({tbl_db_map}). Hãy chỉ truy vấn trên một bảng/database duy nhất.",
            )

    # Kiểm tra cột lẫn giữa các bảng
    if used_tables:
        own_cols: set[str] = set()
        for t in used_tables:
            own_cols |= get_allowed_columns(t)

        other_cols: set[str] = set()
        for t in allowed:
            if t not in used_tables:
                other_cols |= get_allowed_columns(t)

        idents = {m.group(1).lower() for m in _IDENT.finditer(cleaned)}
        mixed = (other_cols - own_cols) & idents
        if mixed:
            bad_col = sorted(mixed)[0]
            return ValidationResult(
                False,
                f"Cột '{bad_col}' không thuộc bảng {', '.join(used_tables)}. Không dùng lẫn cột giữa các bảng.",
            )

    return ValidationResult(True)
