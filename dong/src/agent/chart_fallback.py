"""Module chart_fallback — tự động truy vấn bổ sung/sửa đổi SQL khi cần vẽ biểu đồ (Phase 3d).

Được thiết kế dựa theo pattern duy (agent-harness/duy):
- Khi người dùng yêu cầu vẽ biểu đồ nhưng câu SQL gốc trả về < 2 dòng (hoặc GROUP BY thiếu/sai chiều),
  hệ thống tự động phát hiện và thực thi câu truy vấn fallback để có đủ số dòng (≥2) cho biểu đồ.
"""

from __future__ import annotations

import re
from typing import Any

from src.db.executor import execute_sql
from src.llm.client import use_offline_tools

_DATE_RE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")
_VEHICLE_RE = re.compile(
    r"phương\s*tiện|\bxe\b|vehicle|loại\s*xe|theo\s*loại|ô\s*tô|xe\s*máy|xe\s*tải|xe\s*buýt",
    re.IGNORECASE,
)
_CAMERA_RE = re.compile(
    r"camera|theo\s*camera|từng\s*camera|thiết\s*bị",
    re.IGNORECASE,
)
_DIRECTION_GROUP_RE = re.compile(
    r"group\s+by\s+(?:\d+\s*,\s*)?(?:direction|\d+\s*\)?\s*,?\s*direction)",
    re.IGNORECASE,
)


def _date_filter(question: str, sql: str) -> str | None:
    """Trích xuất mệnh đề lọc ngày từ câu hỏi hoặc câu SQL gốc."""
    m = _DATE_RE.search(question or "")
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"event_time >= DATE '{y}-{mo:02d}-{d:02d}' AND event_time < DATE '{y}-{mo:02d}-{d:02d}' + INTERVAL '1 day'"

    sql_date = re.search(
        r"event_time\s*(?:>=|::date\s*=)\s*(?:DATE\s*)?'(\d{4}-\d{2}-\d{2})'",
        sql or "",
        re.IGNORECASE,
    )
    if sql_date:
        return f"event_time >= DATE '{sql_date.group(1)}' AND event_time < DATE '{sql_date.group(1)}' + INTERVAL '1 day'"

    if re.search(r"hôm\s*nay|hom\s*nay|today", question or "", re.IGNORECASE):
        return "event_time >= CURRENT_DATE"
    if re.search(r"hôm\s*qua|hom\s*qua|yesterday", question or "", re.IGNORECASE):
        return "event_time >= CURRENT_DATE - INTERVAL '1 day' AND event_time < CURRENT_DATE"
    return None


def should_retry_chart_query(*, question: str, sql: str, rows: list[dict[str, Any]]) -> bool:
    """Xác định xem có cần chạy truy vấn fallback cho biểu đồ hay không."""
    if len(rows) >= 2:
        return False
    q = question or ""
    sql_l = (sql or "").lower()

    if _VEHICLE_RE.search(q):
        if "plate_event" in sql_l:
            return True
    if _CAMERA_RE.search(q):
        if any(tbl in sql_l for tbl in ("plate_event", "camera_info", "aioc_camera")):
            return True

    return len(rows) < 2


def fallback_chart_query(
    *,
    question: str,
    sql: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Tạo và thực thi câu SQL fallback khi dữ liệu ban đầu không đủ để vẽ biểu đồ."""
    if not should_retry_chart_query(question=question, sql=sql, rows=rows):
        return None

    # Offline mock fallback
    if use_offline_tools():
        if _CAMERA_RE.search(question):
            mock_rows = [
                {"camera_name": "Cổng 1", "so_luot": 120},
                {"camera_name": "Cổng 2", "so_luot": 85},
                {"camera_name": "Cổng 3", "so_luot": 45},
            ]
        else:
            mock_rows = [
                {"vehicle_type": "CAR", "so_luot": 50},
                {"vehicle_type": "MOTORCYCLE", "so_luot": 120},
                {"vehicle_type": "TRUCK", "so_luot": 30},
                {"vehicle_type": "BUS", "so_luot": 10},
            ]
        return {
            "rows": mock_rows,
            "columns": list(mock_rows[0].keys()),
            "sql": "SELECT vehicle_type, count(*) AS so_luot FROM plate_event GROUP BY vehicle_type",
            "fallback": True,
        }

    date_clause = _date_filter(question, sql)
    where = f"WHERE {date_clause}" if date_clause else ""

    if _CAMERA_RE.search(question):
        fallback_sql = (
            f"SELECT camera_name, count(*) AS so_luot FROM plate_event {where} "
            "GROUP BY camera_name ORDER BY so_luot DESC LIMIT 20"
        ).strip()
    else:
        fallback_sql = (
            f"SELECT vehicle_type, count(*) AS so_luot FROM plate_event {where} "
            "GROUP BY vehicle_type ORDER BY so_luot DESC LIMIT 20"
        ).strip()

    try:
        fallback_rows = execute_sql(fallback_sql)
        if fallback_rows and len(fallback_rows) >= 2:
            return {
                "rows": fallback_rows,
                "columns": list(fallback_rows[0].keys()),
                "sql": fallback_sql,
                "fallback": True,
            }
    except Exception:
        return None

    return None
