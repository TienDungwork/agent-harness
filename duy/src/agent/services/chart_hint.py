from __future__ import annotations

import re

from agent.services.chart_detect import wants_chart

_VEHICLE_CHART_RE = re.compile(
    r"phương\s*tiện|\bxe\b|vehicle|loại\s*xe|theo\s*loại",
    re.IGNORECASE,
)
_DIRECTION_CHART_RE = re.compile(
    r"hướng|direction|ra\s*vào|vào\s*ra|\bra\b|\bvào\b",
    re.IGNORECASE,
)


def build_chart_sql_hint(question: str) -> str:
    """Gợi ý sinh SQL phù hợp khi câu hỏi yêu cầu biểu đồ."""
    if not wants_chart(question):
        return ""

    q = question or ""
    if _VEHICLE_CHART_RE.search(q) and not _DIRECTION_CHART_RE.search(q):
        return (
            "Yêu cầu biểu đồ số lượng phương tiện/xe: SELECT vehicle_type, COUNT(*) AS n "
            "FROM plate_event, lọc ngày nếu câu hỏi có ngày, GROUP BY vehicle_type "
            "(KHÔNG GROUP BY direction trừ khi câu hỏi nói rõ hướng ra/vào), "
            "ORDER BY n DESC, LIMIT 30.\n\n"
        )

    return (
        "Yêu cầu biểu đồ: trả về nhiều dòng (GROUP BY nhãn), 2 cột nhãn+COUNT, "
        "ORDER BY count DESC, LIMIT 30.\n\n"
    )
