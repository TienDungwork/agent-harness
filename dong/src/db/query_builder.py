"""QueryPlan -> parameterized SQL builder (dong v5).

Chuyển đổi QueryPlan (structured LLM) thành câu SQL tham số hoá với placeholder %s
(chuẩn psycopg2), kiểm tra whitelist bảng và bảo vệ chống SQL injection.
"""

from __future__ import annotations

import re
from typing import Any

from src.config import settings
from src.db.catalog import get_allowed_columns, get_allowed_tables
from src.llm.schemas import QueryPlan

_QUOTED_STR = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_EQ_NUM = re.compile(
    r"^(\s*[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?\s*(?:=|!=|<>|<=|>=|<|>)\s*)(\d+(?:\.\d+)?)\s*$"
)
_EQ_IDENT = re.compile(
    r"^(\s*[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?\s*(?:=|!=|<>|LIKE|ILIKE)\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*$",
    re.IGNORECASE,
)
_EQ_COL_VAL = re.compile(
    r"^([a-zA-Z_]\w*)=([a-zA-Z0-9_]+)$"
)


def _parameterize_filter(cond: str) -> tuple[str, list[Any]]:
    """Tách literal values từ 1 điều kiện lọc thành %s và danh sách params."""
    raw = cond.strip()
    params: list[Any] = []

    # 1. Hỗ trợ dạng ngắn gọn col=val (vd: direction=IN từ rewrite filter)
    m_col_val = _EQ_COL_VAL.match(raw)
    if m_col_val:
        col, val = m_col_val.group(1), m_col_val.group(2)
        if val.upper() not in ("NULL", "TRUE", "FALSE"):
            return f"{col} = %s", [val]

    # 2. Thay thế chuỗi đặt trong nháy đơn hoặc nháy kép 'val' / "val"
    if "'" in raw or '"' in raw:
        def _repl(match: re.Match) -> str:
            val = match.group(1) if match.group(1) is not None else match.group(2)
            params.append(val)
            return "%s"

        new_cond = _QUOTED_STR.sub(_repl, raw)
        return new_cond, params

    # 3. So sánh với số: col = 123, col >= 45.6
    m_num = _EQ_NUM.match(raw)
    if m_num:
        lhs, num_str = m_num.group(1), m_num.group(2)
        num_val = float(num_str) if "." in num_str else int(num_str)
        return f"{lhs}%s", [num_val]

    # 4. So sánh với định danh chưa bọc nháy: direction = IN, vehicle_type = CAR
    m_ident = _EQ_IDENT.match(raw)
    if m_ident:
        lhs, rhs = m_ident.group(1), m_ident.group(2)
        if rhs.upper() not in ("NULL", "TRUE", "FALSE"):
            return f"{lhs}%s", [rhs]

    # 5. Các biểu thức khác như IS NOT NULL, IS NULL, hoặc đã có %s
    return raw, params


def build_sql(plan: QueryPlan) -> tuple[str, list[Any]]:
    """Chuyển QueryPlan thành (sql_string, params_list).

    Tham số hóa giá trị WHERE, áp dụng whitelist table và giới hạn LIMIT tối đa.
    """
    if not plan.tables:
        raise ValueError("QueryPlan thiếu bảng nguồn (tables rỗng).")

    allowed_tables = get_allowed_tables()
    for tbl in plan.tables:
        tbl_clean = tbl.lower().strip()
        if tbl_clean not in allowed_tables:
            raise ValueError(
                f"Bảng '{tbl}' không nằm trong whitelist cho phép. Chỉ chấp nhận: {sorted(allowed_tables)}"
            )

    select_clause = ", ".join(plan.selects) if plan.selects else "*"
    from_clause = ", ".join(plan.tables)

    where_clauses: list[str] = []
    params: list[Any] = []

    # Áp dụng organization_id nếu có trong config và bảng có hỗ trợ
    primary_tbl = plan.tables[0].lower().strip()
    tbl_cols = get_allowed_columns(primary_tbl)
    if settings.db_organization_id and "organization_id" in tbl_cols:
        has_org_filter = any("organization_id" in f.lower() for f in plan.filters)
        if not has_org_filter:
            where_clauses.append("organization_id = %s")
            params.append(settings.db_organization_id)

    # Xử lý các filters từ plan
    for f in plan.filters:
        if not f or not f.strip():
            continue
        cond_sql, cond_params = _parameterize_filter(f)
        where_clauses.append(cond_sql)
        params.extend(cond_params)

    parts = [f"SELECT {select_clause} FROM {from_clause}"]
    if where_clauses:
        parts.append(f"WHERE {' AND '.join(where_clauses)}")

    if plan.group_by:
        parts.append(f"GROUP BY {', '.join(plan.group_by)}")

    if plan.order_by:
        parts.append(f"ORDER BY {plan.order_by}")

    # Áp dụng limit (không vượt quá db_max_rows)
    if plan.limit is not None and plan.limit > 0:
        limit_val = min(int(plan.limit), settings.db_max_rows)
    else:
        limit_val = settings.db_max_rows

    parts.append("LIMIT %s;")
    params.append(limit_val)

    sql = " ".join(parts)
    return sql, params
