from __future__ import annotations

import base64
import io
import re
from datetime import date, datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


_VEHICLE_LABELS = {
    "CAR": "Ô tô",
    "MOTORCYCLE": "Xe máy",
    "TRUCK": "Xe tải",
    "BUS": "Xe buýt",
    "IN": "Vào",
    "OUT": "Ra",
}


def _label(v: Any) -> str:
    if v is None:
        return "(null)"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v)
    mapped = _VEHICLE_LABELS.get(s.upper())
    if mapped:
        return mapped
    return s if len(s) <= 24 else s[:21] + "…"


def _pick_columns(rows: list[dict]) -> tuple[str, str] | None:
    if not rows:
        return None
    keys = list(rows[0].keys())
    if len(keys) < 2:
        return None
    numeric: list[str] = []
    categorical: list[str] = []
    for k in keys:
        vals = [r.get(k) for r in rows]
        if all(v is None or _is_number(v) for v in vals) and any(_is_number(v) for v in vals):
            numeric.append(k)
        else:
            categorical.append(k)
    if not numeric or not categorical:
        return None
    # Ưu tiên cột số tên count/total/n/sum
    num_col = next(
        (k for k in numeric if re.search(r"count|total|^n$|sum|số", k, re.I)),
        numeric[0],
    )
    cat_col = categorical[0]
    return cat_col, num_col


def _chart_kind(question: str, labels: list[str]) -> str:
    q = (question or "").lower()
    if re.search(r"tỷ\s*lệ|cơ\s*cấu|pie|tròn", q):
        return "pie"
    if re.search(r"theo\s*ngày|theo\s*tháng|time|đường|line", q):
        return "line"
    # nhãn giống ngày → line
    if labels and sum(1 for x in labels if re.match(r"^\d{4}-\d{2}", x)) >= max(1, len(labels) // 2):
        return "line"
    return "bar"


def render_chart_png(
    *,
    question: str,
    rows: list[dict[str, Any]],
    title: str | None = None,
    max_points: int = 30,
) -> tuple[str | None, str]:
    """
    Trả (base64_png, reason).
    base64 không gồm prefix data:image/...
    """
    if len(rows) < 2:
        return None, "Cần ít nhất 2 dòng để vẽ biểu đồ."

    picked = _pick_columns(rows[:max_points])
    if not picked:
        return None, "Kết quả không có cặp cột nhãn + số để vẽ."

    cat_col, num_col = picked
    data = rows[:max_points]
    labels = [_label(r.get(cat_col)) for r in data]
    values = [float(r.get(num_col) or 0) for r in data]
    kind = _chart_kind(question, labels)

    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    fig.patch.set_facecolor("#f3f6f8")
    ax.set_facecolor("#f8fafb")
    color = "#1f5c4f"

    if kind == "pie":
        ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8})
        ax.axis("equal")
    elif kind == "line":
        ax.plot(range(len(values)), values, marker="o", color=color, linewidth=2)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)
    else:
        ax.bar(range(len(values)), values, color=color)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.grid(True, axis="y", alpha=0.3)

    ax.set_title(title or (question[:80] if question else "Biểu đồ"), fontsize=11, color="#16262e")
    if kind != "pie":
        ax.set_ylabel(num_col, fontsize=9, color="#5c6d76")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii"), f"{kind}:{cat_col}/{num_col}"
