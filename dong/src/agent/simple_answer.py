"""Module try_format_simple_answer — trả lời nhanh số liệu đơn giản không qua LLM (Phase 3d).

Được thiết kế dựa theo pattern duy (agent-harness/duy):
- Khi kết quả SQL trả về 1 dòng aggregate thuần số (COUNT, SUM, AVG...), tự động định dạng
  câu trả lời tiếng Việt tự nhiên chuẩn xác theo ngữ cảnh câu hỏi.
- Tiết kiệm 100% chi phí và thời gian gọi LLM respond cho các câu hỏi số lượng/thống kê đơn giản.
"""

from __future__ import annotations

import re
from typing import Any

_LABELS: dict[str, str] = {
    "car": "ô tô",
    "o_to": "ô tô",
    "oto": "ô tô",
    "motorcycle": "xe máy",
    "xe_may": "xe máy",
    "truck": "xe tải",
    "xe_tai": "xe tải",
    "bus": "xe buýt",
    "xe_buyt": "xe buýt",
    "in": "vào",
    "vao": "vào",
    "out": "ra",
    "ra": "ra",
    "camera": "camera",
    "online": "đang hoạt động",
    "offline": "ngừng hoạt động",
    "crowd": "đám đông",
    "intrusion": "xâm nhập",
    "fire": "cháy",
    "smoke": "khói",
    "fight": "ẩu đả",
    "water": "mực nước",
}


def _fmt_num(v: Any) -> str:
    """Định dạng số nguyên hoặc số thực tiếng Việt gọn gàng."""
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    if isinstance(v, float):
        if v.is_integer():
            return f"{int(v):,}".replace(",", ".")
        return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    try:
        f = float(str(v).replace(",", ""))
        if f.is_integer():
            return f"{int(f):,}".replace(",", ".")
        return f"{f:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    except (ValueError, TypeError):
        return str(v)


def _label(key: str) -> str:
    k = key.lower().strip()
    if k in _LABELS:
        return _LABELS[k]
    for prefix, lbl in _LABELS.items():
        if prefix in k:
            return lbl
    return key.replace("_", " ")


def try_format_simple_answer(question: str, rows: list[dict[str, Any]] | None) -> str | None:
    """Trả lời nhanh không gọi LLM khi kết quả là 1 dòng số đếm đơn giản.

    Trả về:
    - `str`: Câu trả lời tiếng Việt tự nhiên nếu định dạng được.
    - `None`: Nếu kết quả không phải 1 dòng aggregate số (cần bảng hoặc LLM respond).
    """
    if not rows or len(rows) != 1:
        return None

    row = rows[0]
    if not isinstance(row, dict) or not row:
        return None

    # Lấy danh sách các cặp (cột, giá trị) là số
    nums: list[tuple[str, Any]] = []
    for k, v in row.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            nums.append((str(k), v))
        elif isinstance(v, str):
            try:
                f = float(v.replace(",", ""))
                nums.append((str(k), f))
            except ValueError:
                pass

    # Phải có số và mọi cột trong dòng đều là số (aggregate thuần)
    if not nums or len(nums) != len(row):
        return None

    q = (question or "").lower()
    has_today = any(kw in q for kw in ("hôm nay", "hom nay", "today"))
    has_yesterday = any(kw in q for kw in ("hôm qua", "hom qua", "yesterday"))
    when = " hôm nay" if has_today else (" hôm qua" if has_yesterday else "")

    # ── Trường hợp 1: Chỉ có 1 cột số duy nhất (COUNT(*), SUM...) ───────────
    if len(nums) == 1:
        n = _fmt_num(nums[0][1])

        # 1. Camera & Thiết bị
        if "camera" in q and any(kw in q for kw in ("phương tiện", "biển số", "plate", "an ninh")):
            return f"Có {n} camera phương tiện."
        if "camera" in q and any(kw in q for kw in ("hoạt động", "online", "trực tuyến", "bình thường")):
            return f"Có {n} camera đang hoạt động."
        if "camera" in q and any(kw in q for kw in ("mất kết nối", "offline", "ngoại tuyến", "bảo trì")):
            return f"Có {n} camera ngoại tuyến/bảo trì."
        if "camera" in q:
            return f"Có {n} camera."

        # 2. Sự kiện bất thường & an ninh (ưu tiên trước phương tiện)
        if any(kw in q for kw in ("đám đông", "dam dong", "crowd")):
            return f"Có {n} lượt phát hiện đám đông{when}."
        if any(kw in q for kw in ("leo trèo", "xâm nhập", "hang rao", "hàng rào", "intrusion")):
            return f"Có {n} phát hiện xâm nhập/leo trèo{when}."
        if any(kw in q for kw in ("cháy", "khói", "chay", "khoi", "fire", "smoke")):
            return f"Có {n} cảnh báo cháy hoặc khói{when}."
        if any(kw in q for kw in ("ẩu đả", "au da", "fight", "đánh nhau")):
            return f"Có {n} vụ ẩu đả{when}."
        if any(kw in q for kw in ("mực nước", "muc nuoc", "water", "ngập")):
            return f"Có {n} cảnh báo mực nước{when}."

        # 3. Phương tiện / Lượt xe — trước nhánh "sự kiện" chung (tránh nhầm anomaly)
        if any(kw in q for kw in ("phương tiện", "biển số", "bien so", "plate", "alpr", "nhận diện")):
            if any(kw in q for kw in ("sự kiện", "su kien")):
                return f"Có {n} sự kiện phương tiện{when}."
        if re.search(r"xe\s*máy|motorcycle|\bmoto\b", q):
            return f"Có {n} lượt xe máy{when}."
        if re.search(r"ô\s*tô|\bcar\b|xe\s*con", q):
            return f"Có {n} lượt ô tô{when}."
        if re.search(r"xe\s*tải|\btruck\b", q):
            return f"Có {n} lượt xe tải{when}."
        if re.search(r"xe\s*buýt|\bbus\b|xe\s*khách", q):
            return f"Có {n} lượt xe buýt{when}."
        if re.search(r"vào\s*cổng|lượt\s*vào|xe\s*vào|\bđi\s*vào\b", q):
            return f"Có {n} lượt xe vào{when}."
        if re.search(r"ra\s*cổng|lượt\s*ra|xe\s*ra|\bđi\s*ra\b", q):
            return f"Có {n} lượt xe ra{when}."
        if any(kw in q for kw in ("lượt xe", "phương tiện", "bao nhiêu xe", "tổng số xe", "số xe")):
            return f"Có {n} lượt xe{when}."

        # 4. Người / Khuôn mặt — trước nhánh "sự kiện" chung
        if any(kw in q for kw in ("người", "khuôn mặt", "khuon mat", "face", "nhân sự")):
            return f"Có {n} lượt người/khuôn mặt ghi nhận{when}."

        # 5. Sự kiện bất thường — chỉ khi không hỏi phương tiện/xe/khuôn mặt
        if any(kw in q for kw in ("bất thường", "anomaly")):
            return f"Có {n} sự kiện bất thường{when}."
        if any(kw in q for kw in ("sự kiện", "su kien", "cảnh báo")) and not any(
            kw in q for kw in ("phương tiện", "xe", "biển số", "bien so", "plate", "lượt xe", "khuôn mặt", "khuon mat", "face")
        ):
            return f"Có {n} sự kiện bất thường{when}."

        return f"Kết quả: {n}."

    # ── Trường hợp 2: Nhiều cột số (phân loại song song trong 1 dòng) ─────────
    parts: list[str] = []
    for key, val in nums:
        lbl = _label(key)
        parts.append(f"{_fmt_num(val)} {lbl}")

    if re.search(r"ô\s*tô|xe\s*máy|car|motorcycle|xe\s*tải|xe\s*buýt", q):
        return f"Có {' và '.join(parts)}{when}."
    if re.search(r"vào|ra|in|out", q):
        return f"Có {' và '.join(parts)}{when}."

    return f"Kết quả: {', '.join(parts)}."
