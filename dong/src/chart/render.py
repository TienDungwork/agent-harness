"""Module vẽ biểu đồ PNG qua matplotlib backend Agg và chuyển đổi sang base64 (dong v5).

Chỉ bao gồm các hàm thuần, độc lập, có thể kiểm thử offline:
- render_chart: vẽ biểu đồ từ danh sách dòng và ChartSpec, trả về chuỗi PNG base64.
- should_render_chart: phát hiện yêu cầu vẽ biểu đồ từ từ khóa hoặc StatAnswer.
- plan_chart: sinh ChartSpec từ rows và câu hỏi (structured LLM hoặc offline heuristic).
"""

from __future__ import annotations

import base64
import io
import re
from datetime import date, datetime
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.llm.client import use_offline_tools
from src.llm.schemas import ChartSpec, StatAnswer, normalize_chart_type
from src.llm.structured import invoke_structured
from src.prompts import registry

_CHART_KEYWORD_RE = re.compile(
    r"biểu\s*đồ|bieu\s*do|\bchart\b|\bplot\b|vẽ\s*(biểu|đồ|đường|cột|thị)?|"
    r"đồ\s*thị|thống\s*kê\s*theo|so\s*sánh\s*theo|phân\s*bố|cơ\s*cấu|tỷ\s*lệ|"
    r"\bvẽ\b",
    re.IGNORECASE,
)

_VEHICLE_LABELS: dict[str, str] = {
    "CAR": "Ô tô",
    "MOTORCYCLE": "Xe máy",
    "TRUCK": "Xe tải",
    "BUS": "Xe buýt",
    "IN": "Vào",
    "OUT": "Ra",
}


def _is_number(v: Any) -> bool:
    if v is None or isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _to_float(v: Any) -> float:
    if v is None or isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _format_label(v: Any) -> str:
    if v is None:
        return "(null)"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    mapped = _VEHICLE_LABELS.get(s.upper())
    if mapped:
        return mapped
    return s if len(s) <= 24 else s[:21] + "…"


def _pick_columns(rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Chọn cặp cột (category_col, numeric_col) từ danh sách rows."""
    if not rows:
        return "", ""
    keys = list(rows[0].keys())
    if not keys:
        return "", ""
    if len(keys) == 1:
        return keys[0], keys[0]

    numeric: list[str] = []
    categorical: list[str] = []
    for k in keys:
        vals = [r.get(k) for r in rows[:30]]
        if all(v is None or _is_number(v) for v in vals) and any(_is_number(v) for v in vals):
            numeric.append(k)
        else:
            categorical.append(k)

    if numeric and categorical:
        num_col = next(
            (k for k in numeric if re.search(r"count|total|^n$|sum|số|luot|so_luong|value", k, re.I)),
            numeric[0],
        )
        return categorical[0], num_col
    elif len(keys) >= 2:
        return keys[0], keys[1]
    return keys[0], keys[0]


def _detect_chart_type(question: str) -> Literal["bar", "pie", "line"]:
    q = (question or "").lower()
    if re.search(r"cột|\bbar\b", q) and not re.search(r"tròn|pie|đường|line|xu\s*hướng|tỷ\s*lệ|cơ\s*cấu", q):
        return "bar"
    if re.search(r"tỷ\s*lệ|tỉ\s*lệ|cơ\s*cấu|phần\s*trăm|pie|tròn|bánh", q):
        return "pie"
    if re.search(r"theo\s*(ngày|tháng|năm|giờ|tuần|time|thời\s*gian)|đường|line|xu\s*hướng|biến\s*động|diễn\s*biến|lịch\s*trình", q):
        return "line"
    return "bar"


def should_render_chart(question: str, stat_answer: StatAnswer | None = None) -> bool:
    """Xác định có cần vẽ biểu đồ hay không từ câu hỏi hoặc StatAnswer.

    True nếu câu hỏi chứa từ khóa biểu đồ (biểu đồ, chart, vẽ, plot, ...)
    HOẶC stat_answer.chart_requested là True.
    """
    if stat_answer is not None and getattr(stat_answer, "chart_requested", False):
        return True
    if not question:
        return False
    return bool(_CHART_KEYWORD_RE.search(question))


def _offline_plan_chart(rows: list[dict[str, Any]], question: str) -> ChartSpec:
    cat_col, num_col = _pick_columns(rows)
    chart_type = _detect_chart_type(question)
    cleaned_q = (question or "").strip()
    title_vi = cleaned_q if cleaned_q and len(cleaned_q) <= 80 else (
        f"Thống kê {num_col} theo {cat_col}" if num_col and cat_col else "Biểu đồ thống kê"
    )
    return ChartSpec(
        chart_type=chart_type,
        x_column=cat_col,
        y_column=num_col,
        title_vi=title_vi,
    )


def plan_chart(rows: list[dict[str, Any]], question: str) -> ChartSpec:
    """Xác định ChartSpec từ danh sách dòng kết quả và câu hỏi.

    Khi offline (`use_offline_tools()`): trích xuất cặp cột danh mục + số liệu theo heuristic.
    Khi online: gọi `invoke_structured` để LLM lựa chọn ChartSpec tối ưu, tự động fallback nếu lỗi.
    """
    if not rows:
        return ChartSpec(
            chart_type=_detect_chart_type(question),
            x_column="",
            y_column="",
            title_vi=(question or "").strip() or "Biểu đồ",
        )

    if use_offline_tools():
        return _offline_plan_chart(rows, question)

    keys = list(rows[0].keys())
    sample_rows = rows[:3]
    user_prompt = (
        f"Câu hỏi của người dùng:\n{question}\n\n"
        f"Các cột dữ liệu có sẵn:\n{keys}\n\n"
        f"Dữ liệu mẫu (3 dòng đầu):\n{sample_rows}"
    )
    messages = [
        {"role": "system", "content": registry().render("plan_chart")},
        {"role": "user", "content": user_prompt},
    ]

    try:
        spec = invoke_structured(messages, ChartSpec)
        if isinstance(spec, ChartSpec):
            return spec
        return _offline_plan_chart(rows, question)
    except Exception:
        return _offline_plan_chart(rows, question)


def render_chart(rows: list[dict[str, Any]], spec: ChartSpec) -> str:
    """Vẽ biểu đồ bằng matplotlib Agg và trả về chuỗi PNG mã hóa base64.

    Chuỗi base64 trả về là chuỗi thuần (không bao gồm tiền tố 'data:image/png;base64,').
    Nếu `rows` rỗng hoặc `spec` không hợp lệ, trả về chuỗi rỗng `""`.
    Hỗ trợ các kiểu biểu đồ: 'bar', 'line', 'pie' (mặc định là 'bar').
    """
    if not rows or spec is None:
        return ""

    x_col = spec.x_column
    y_col = spec.y_column

    # Fallback chọn cột nếu spec để trống hoặc không tồn tại trong rows
    if not x_col or not y_col or x_col not in rows[0] or y_col not in rows[0]:
        picked_x, picked_y = _pick_columns(rows)
        x_col = x_col if (x_col and x_col in rows[0]) else picked_x
        y_col = y_col if (y_col and y_col in rows[0]) else picked_y

    if not x_col or not y_col:
        return ""

    # Giới hạn tối đa 50 điểm vẽ để đảm bảo biểu đồ rõ ràng
    data = rows[:50]
    labels = [_format_label(r.get(x_col)) for r in data]
    values = [_to_float(r.get(y_col)) for r in data]

    chart_type = normalize_chart_type(getattr(spec, "chart_type", "bar"))
    color = "#1f5c4f"

    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    try:
        fig.patch.set_facecolor("#f3f6f8")
        ax.set_facecolor("#f8fafb")

        if chart_type == "pie":
            valid_pairs = [(lbl, v) for lbl, v in zip(labels, values) if v > 0]
            if valid_pairs:
                pie_labels, pie_vals = zip(*valid_pairs)
                ax.pie(pie_vals, labels=pie_labels, autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8})
                ax.axis("equal")
            else:
                ax.text(0.5, 0.5, "Không có dữ liệu hợp lệ", ha="center", va="center")
        elif chart_type == "line":
            ax.plot(range(len(values)), values, marker="o", color=color, linewidth=2)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
            ax.grid(True, axis="y", alpha=0.3)
            ax.set_ylabel(y_col, fontsize=9, color="#5c6d76")
            ax.set_xlabel(x_col, fontsize=9, color="#5c6d76")
        else:  # bar hoặc fallback
            ax.bar(range(len(values)), values, color=color)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
            ax.grid(True, axis="y", alpha=0.3)
            ax.set_ylabel(y_col, fontsize=9, color="#5c6d76")
            ax.set_xlabel(x_col, fontsize=9, color="#5c6d76")

        title = spec.title_vi or "Biểu đồ"
        ax.set_title(title, fontsize=11, color="#16262e")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    finally:
        plt.close(fig)
