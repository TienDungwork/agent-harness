from __future__ import annotations

import re

from agent.tools.postgres.query import query

_DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
_VEHICLE_RE = re.compile(
    r"phương\s*tiện|\bxe\b|vehicle|loại\s*xe|theo\s*loại",
    re.IGNORECASE,
)
_DIRECTION_GROUP_RE = re.compile(
    r"group\s+by\s+(?:\d+\s*,\s*)?(?:direction|\d+\s*\)?\s*,?\s*direction)",
    re.IGNORECASE,
)


def _date_filter(question: str, sql: str) -> str | None:
    m = _DATE_RE.search(question or "")
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"event_time::date = DATE '{y}-{mo:02d}-{d:02d}'"

    sql_date = re.search(
        r"event_time\s*::\s*date\s*=\s*DATE\s+'(\d{4}-\d{2}-\d{2})'",
        sql or "",
        re.IGNORECASE,
    )
    if sql_date:
        return f"event_time::date = DATE '{sql_date.group(1)}'"

    if re.search(r"hôm\s*nay", question or "", re.IGNORECASE):
        return "event_time::date = CURRENT_DATE"
    return None


def should_retry_vehicle_chart(*, question: str, sql: str, rows: list[dict]) -> bool:
    if len(rows) >= 2:
        return False
    if not _VEHICLE_RE.search(question or ""):
        return False
    sql_l = (sql or "").lower()
    if "plate_event" not in sql_l:
        return False
    if _DIRECTION_GROUP_RE.search(sql or ""):
        return True
    if len(rows) == 1:
        keys = {k.lower() for k in rows[0].keys()}
        if "direction" in keys and "vehicle_type" not in keys:
            return True
    return len(rows) < 2


def fallback_vehicle_type_chart(
    *,
    question: str,
    sql: str,
    rows: list[dict],
    dbname: str = "its",
) -> dict | None:
    """Chạy lại query GROUP BY vehicle_type khi SQL gốc không đủ dòng cho biểu đồ."""
    if not should_retry_vehicle_chart(question=question, sql=sql, rows=rows):
        return None

    date_clause = _date_filter(question, sql)
    where = f"WHERE {date_clause}" if date_clause else ""
    fallback_sql = (
        f"SELECT vehicle_type, COUNT(*) AS n FROM plate_event {where} "
        "GROUP BY 1 ORDER BY n DESC LIMIT 30"
    ).strip()

    try:
        result = query(dbname, fallback_sql)
    except Exception:
        return None

    fallback_rows = result.get("rows") or []
    if len(fallback_rows) < 2:
        return None
    return {"query_result": result, "sql": fallback_sql}
