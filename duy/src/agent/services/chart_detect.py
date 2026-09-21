from __future__ import annotations

import re

_CHART_RE = re.compile(
    r"biểu\s*đồ|bieu\s*do|\bchart\b|\bplot\b|vẽ\s*(biểu|đồ|đường|cột)|"
    r"thống\s*kê\s*theo|so\s*sánh\s*theo|theo\s*(ngày|tháng|camera|loại|hãng)|"
    r"phân\s*bố|cơ\s*cấu|tỷ\s*lệ",
    re.IGNORECASE,
)


def wants_chart(question: str) -> bool:
    return bool(_CHART_RE.search(question or ""))
