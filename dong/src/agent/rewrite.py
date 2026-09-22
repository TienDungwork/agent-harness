"""Rewrite question — chuẩn hóa câu hỏi và trích xuất filters, time_range."""

from __future__ import annotations

from src.llm.client import use_offline_tools
from src.llm.schemas import RewrittenQuestion
from src.llm.structured import invoke_structured
from src.prompts import registry



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
        {"role": "system", "content": registry().render("rewrite")},
        {"role": "user", "content": f"Câu hỏi gốc: {cleaned}"},
    ]
    return invoke_structured(messages, RewrittenQuestion)


def rewrite_question_safe(raw: str) -> RewrittenQuestion:
    """Rewrite với fallback offline khi LLM lỗi/timeout."""
    try:
        return rewrite_question(raw)
    except Exception:
        return _offline_rewrite(raw)
