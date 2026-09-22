"""Rewrite question — chuẩn hóa câu hỏi và trích xuất filters, time_range."""

from __future__ import annotations

from src.llm.client import use_offline_tools
from src.llm.schemas import RewrittenQuestion
from src.llm.structured import invoke_structured

REWRITE_SYSTEM_PROMPT = """Bạn là trợ lý chuẩn hóa câu hỏi cho hệ thống giám sát và vận hành VMS KCN Hưng Phú.
Nhiệm vụ của bạn:
1. Giữ nguyên ý đồ người dùng, chuẩn hóa câu hỏi rõ ràng, chính xác.
2. Trích xuất các bộ lọc (filters) có trong câu (vd: biển số, loại xe, hướng di chuyển IN/OUT, cổng, làn xe).
3. Trích xuất khoảng thời gian (time_range) nếu có (vd: hôm nay, hôm qua, tháng này, khoảng ngày giờ cụ thể).
4. Gợi ý ý định (intent_hint): query_data, how_to, troubleshoot, concept, hoặc out_of_scope nếu nhận diện rõ.
"""


def _offline_rewrite(raw: str) -> RewrittenQuestion:
    """Fallback offline trả về RewrittenQuestion hợp lệ không gọi LAN."""
    raw_str = (raw or "").strip()
    filters: list[str] = []
    time_range = None
    intent_hint = None
    low = raw_str.lower()

    if "hôm nay" in low:
        time_range = "today"
    elif "hôm qua" in low:
        time_range = "yesterday"
    elif "tháng này" in low:
        time_range = "this_month"

    if "xe vào" in low or " hướng in" in low or low.endswith(" in"):
        filters.append("direction=IN")
    elif "xe ra" in low or " hướng out" in low or low.endswith(" out"):
        filters.append("direction=OUT")

    if any(k in low for k in ("làm sao", "cách", "hướng dẫn")):
        intent_hint = "how_to"
    elif any(k in low for k in ("lỗi", "mất kết nối", "sự cố")):
        intent_hint = "troubleshoot"
    elif any(k in low for k in ("bao nhiêu", "đếm", "thống kê", "liệt kê")):
        intent_hint = "query_data"

    return RewrittenQuestion(
        text=raw_str,
        filters=filters,
        time_range=time_range,
        intent_hint=intent_hint,
    )


def rewrite_question(raw: str) -> RewrittenQuestion:
    """Chuẩn hóa câu hỏi tiếng Việt sang RewrittenQuestion qua structured LLM."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return RewrittenQuestion(text="")

    if use_offline_tools():
        return _offline_rewrite(cleaned)

    messages = [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Câu hỏi gốc: {cleaned}"},
    ]
    return invoke_structured(messages, RewrittenQuestion)
