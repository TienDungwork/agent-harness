"""Pre-SQL helpers: time_range hints, chart hints, prompt context injection (dong v7 Phase 3b)."""

from __future__ import annotations

import re

from src.db.catalog import get_catalog

# ── Chart hint helpers ────────────────────────────────────────────────────────

_VEHICLE_CHART_RE = re.compile(
    r"phương\s*tiện|\bxe\b|vehicle|loại\s*xe|theo\s*loại",
    re.IGNORECASE,
)
_DIRECTION_CHART_RE = re.compile(
    r"hướng|direction|ra\s*vào|vào\s*ra|\bra\b|\bvào\b",
    re.IGNORECASE,
)


def normalize_time_range(raw: str | None) -> str | None:
    """Normalize raw/VI time range string into canonical: 'today' | 'yesterday' | 'this_month'."""
    if not raw or not isinstance(raw, str):
        return None
    val = raw.strip().lower()
    if val in ("today", "hôm nay", "hom nay", "ngày hôm nay", "ngay hom nay"):
        return "today"
    if val in ("yesterday", "hôm qua", "hom qua", "ngày hôm qua", "ngay hom qua"):
        return "yesterday"
    if val in (
        "this_month",
        "tháng này",
        "thang nay",
        "tháng",
        "thang",
        "trong tháng",
        "trong thang",
        "tháng hiện tại",
        "thang hien tai",
    ):
        return "this_month"
    return None


def format_time_range_for_prompt(time_range: str | None) -> str:
    """Tạo hướng dẫn tiếng Việt ngắn gọn cho LLM khi có khoảng thời gian."""
    canon = normalize_time_range(time_range)
    if not canon:
        return ""
    if canon == "today":
        return (
            "Khoảng thời gian (time_range): today\n"
            "Hướng dẫn: Lọc theo ngày hiện tại: time_column::date = CURRENT_DATE."
        )
    if canon == "yesterday":
        return (
            "Khoảng thời gian (time_range): yesterday\n"
            "Hướng dẫn: Lọc theo ngày hôm qua: time_column::date = CURRENT_DATE - 1."
        )
    if canon == "this_month":
        return (
            "Khoảng thời gian (time_range): this_month\n"
            "Hướng dẫn: Lọc theo tháng hiện tại: time_column >= date_trunc('month', CURRENT_DATE)."
        )
    return ""


def get_time_column_for_table(table: str | None) -> str:
    """Lấy tên cột thời gian theo catalog của bảng (mặc định 'event_time', smf_face_events dùng 'access_time')."""
    if not table:
        return "event_time"
    tbl = table.lower().strip()
    catalog = get_catalog()
    if tbl in catalog:
        info = catalog[tbl]
        if isinstance(info, dict) and info.get("time_column"):
            return str(info["time_column"]).strip()
    return "event_time"


def time_range_to_filter(time_range: str | None, time_column: str = "event_time") -> str | None:
    """Chuyển đổi time_range thành biểu thức lọc SQL an toàn cho QueryPlan filters."""
    canon = normalize_time_range(time_range)
    if not canon:
        return None
    col = (time_column or "event_time").strip()
    if canon == "today":
        return f"{col} >= CURRENT_DATE"
    if canon == "yesterday":
        return f"{col} >= CURRENT_DATE - INTERVAL '1 day' AND {col} < CURRENT_DATE"
    if canon == "this_month":
        return f"{col} >= date_trunc('month', CURRENT_DATE)"
    return None


def build_chart_sql_hint(question: str) -> str:
    """Gợi ý cấu trúc SQL phù hợp khi câu hỏi yêu cầu biểu đồ.

    Trả về "" nếu câu hỏi không có từ khóa biểu đồ.
    Nếu có loại xe cụ thể + hướng ra/vào → gợi ý WHERE vehicle_type = '...' GROUP BY direction.
    Nếu có từ khóa xe/phương tiện chung → gợi ý GROUP BY vehicle_type.
    Ngược lại → gợi ý generic GROUP BY nhãn.
    """
    # Lazy import to avoid circular dependency
    from src.chart.render import should_render_chart  # noqa: PLC0415

    if not should_render_chart(question):
        return ""

    q = question or ""
    q_low = q.lower()

    # Kiểm tra loại xe cụ thể
    vtype = None
    if any(k in q_low for k in ("ô tô", "o to", "xe hơi", "car", "xe con")):
        vtype = "CAR"
    elif any(k in q_low for k in ("xe máy", "xe may", "motorcycle", "moto")):
        vtype = "MOTORCYCLE"
    elif any(k in q_low for k in ("xe tải", "xe tai", "truck")):
        vtype = "TRUCK"
    elif any(k in q_low for k in ("xe buýt", "xe buyt", "bus")):
        vtype = "BUS"

    if vtype and _DIRECTION_CHART_RE.search(q):
        return (
            f"Yêu cầu biểu đồ ra/vào cho loại xe cụ thể ({vtype}): "
            f"SELECT direction, COUNT(*) AS n FROM plate_event "
            f"WHERE vehicle_type = '{vtype}' (và lọc ngày nếu có), "
            f"GROUP BY direction ORDER BY n DESC, LIMIT 30."
        )

    if _VEHICLE_CHART_RE.search(q) and not _DIRECTION_CHART_RE.search(q):
        return (
            "Yêu cầu biểu đồ số lượng phương tiện/xe: SELECT vehicle_type, COUNT(*) AS n "
            "FROM plate_event, lọc ngày nếu câu hỏi có ngày, GROUP BY vehicle_type "
            "(KHÔNG GROUP BY direction trừ khi câu hỏi nói rõ hướng ra/vào), "
            "ORDER BY n DESC, LIMIT 30."
        )

    return (
        "Yêu cầu biểu đồ: trả về nhiều dòng (GROUP BY nhãn), 2 cột nhãn+COUNT, "
        "ORDER BY count DESC, LIMIT 30."
    )

