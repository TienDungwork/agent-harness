from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from agent.graph.state import AgentState
from agent.llm.provider import get_llm

_LABELS = {
    "car": "ô tô",
    "car_count": "ô tô",
    "xe_o_to": "ô tô",
    "oto": "ô tô",
    "motorcycle": "xe máy",
    "motorcycle_count": "xe máy",
    "xe_may": "xe máy",
    "moto": "xe máy",
    "truck": "xe tải",
    "bus": "xe buýt",
    "count": "bản ghi",
}


def _result_is_empty(query_result: dict[str, Any] | None) -> bool:
    qr = query_result or {}
    if int(qr.get("row_count") or 0) == 0:
        return True
    rows = qr.get("rows") or []
    if not rows:
        return True
    if len(rows) == 1:
        values = [v for v in rows[0].values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if values and all(v == 0 for v in values):
            return True
    return False


def _fmt_num(v: int | float) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, int):
        return str(v)
    return str(v)


def _label(key: str) -> str:
    k = key.lower()
    if k in _LABELS:
        return _LABELS[k]
    for prefix, label in _LABELS.items():
        if prefix in k:
            return label
    return key.replace("_", " ")


def try_format_simple_answer(question: str, query_result: dict[str, Any] | None) -> str | None:
    """Trả lời nhanh không gọi LLM khi kết quả là 1 dòng số đếm đơn giản."""
    qr = query_result or {}
    rows = qr.get("rows") or []
    if len(rows) != 1:
        return None
    row = rows[0]
    nums = [
        (str(k), v)
        for k, v in row.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    if not nums:
        return None
    # Chỉ format khi mọi cột đều số (aggregate).
    if len(nums) != len(row):
        return None

    q = (question or "").lower()
    if len(nums) == 1:
        n = _fmt_num(nums[0][1])
        if "camera" in q and "phương tiện" in q:
            return f"Có {n} camera phương tiện."
        if "camera" in q and ("hoạt động" in q or "online" in q):
            return f"Có {n} camera đang hoạt động."
        if "camera" in q:
            return f"Có {n} camera."
        if re.search(r"xe\s*máy|motorcycle", q):
            when = " hôm nay" if "hôm nay" in q else ""
            return f"Có {n} lượt xe máy{when}."
        if re.search(r"ô\s*tô|\bcar\b", q):
            when = " hôm nay" if "hôm nay" in q else ""
            return f"Có {n} lượt ô tô{when}."
        if "bất thường" in q or "anomaly" in q:
            return f"Có {n} sự kiện bất thường."
        return f"Kết quả: {n}."

    # Nhiều cột số: ô tô / xe máy…
    parts: list[str] = []
    for key, val in nums:
        parts.append(f"{_fmt_num(val)} {_label(key)}")
    if re.search(r"ô\s*tô|xe\s*máy|car|motorcycle", q):
        return "Có " + " và ".join(parts) + "."
    return "Kết quả: " + ", ".join(parts) + "."


def respond(state: AgentState) -> dict:
    if state.get("error"):
        reason = state.get("sql_validation", {}).get("reason") or state.get("error")
        return {"answer": f"Không trả lời được từ dữ liệu. {reason}"}

    datasets = state.get("relevant_datasets") or []
    table = ""
    if datasets:
        table = str(datasets[0].get("table") or datasets[0].get("id") or "")

    qr = state.get("query_result")
    empty = _result_is_empty(qr)

    simple = try_format_simple_answer(str(state.get("question") or ""), qr)
    if simple is not None:
        if empty and table and "bảng" not in simple.lower():
            simple = f"{simple} (Nguồn: bảng {table}.)"
        if (state.get("chart_png_base64") or "").strip():
            simple = f"{simple} Biểu đồ đã tạo từ kết quả truy vấn."
        return {"answer": simple}

    caveat = ""
    if empty:
        caveat = (
            f" Kết quả rỗng trên bảng `{table or '?'}`. "
            "Nói rõ không có bản ghi khớp truy vấn; nhắc có thể sai nguồn nếu câu hỏi thuộc miền khác. "
            "Không khẳng định chắc chắn ngoài phạm vi bảng đã query."
        )

    user = (
        f"Câu hỏi: {state.get('question')}\n"
        f"SQL: {state.get('sql')}\n"
        f"Bảng: {table or '(không rõ)'}\n"
        f"Kết quả JSON:\n{json.dumps(qr or {}, ensure_ascii=False, default=str)}\n\n"
        "Trả lời ngắn bằng tiếng Việt, chỉ dựa trên kết quả trên. Không bịa số. Tối đa 2 câu."
        f"{caveat}"
    )
    resp = get_llm(max_tokens=160).invoke(
        [
            SystemMessage(content="Bạn là trợ lý dữ liệu. Chỉ tóm tắt kết quả query thật."),
            HumanMessage(content=user),
        ]
    )
    answer = str(resp.content).strip()
    if empty and table and table not in answer:
        answer = f"{answer} (Nguồn: bảng {table}.)"
    if (state.get("chart_png_base64") or "").strip():
        answer = f"{answer} Biểu đồ đã tạo từ kết quả truy vấn."
    return {"answer": answer}
