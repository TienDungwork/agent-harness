"""Classify intent — phân loại ý định câu hỏi sang IntentResult structured."""

from __future__ import annotations

from src.llm.client import use_offline_tools
from src.llm.schemas import IntentResult, RewrittenQuestion
from src.llm.structured import invoke_structured
from src.prompts import registry

STAT_EVENT_DOMAIN_KEYWORDS = (
    "leo trèo",
    "cháy",
    "khói",
    "fire",
    "smoke",
    "mực nước",
    "ngập",
    "water",
    "đám đông",
    "ẩu đả",
    "intrusion",
    "crowd",
    "fight",
    "cảnh báo cháy",
    "cảnh báo khói",
)


def is_stat_event_domain(text: str) -> bool:
    """True nếu câu hỏi thuộc domain thống kê fire/anomaly/water (không phải howto thuần)."""
    low = (text or "").lower()
    if any(k in low for k in STAT_EVENT_DOMAIN_KEYWORDS):
        return True
    return any(k in low for k in ("phát hiện", "cảnh báo")) and any(
        t in low for t in ("hôm nay", "hôm qua", "ngày", "tuần", "tháng", "khoảng", "từ", "đến")
    )


def _offline_classify(text: str) -> IntentResult:
    """Heuristic offline cho intent khi test hoặc không có LLM."""
    low = text.lower()

    # 1. Out of scope
    if any(k in low for k in ("thời tiết", "bóng đá", "tổng thống", "chính trị", "giá vàng", "nấu ăn", "viết một bài thơ", "bài thơ", "cổ phiếu")):
        return IntentResult(intent="out_of_scope", reason="Offline heuristic: câu hỏi ngoài phạm vi")

    # 2. Câu hỏi vẽ sơ đồ / so sánh khái niệm với câu hỏi thống kê (vd: 018, 024) -> how_to / docs
    if ("vẽ sơ đồ" in low or "sơ đồ" in low) and ("khác gì so với" in low or "phân biệt" in low):
        return IntentResult(intent="how_to", reason="Offline heuristic: sơ đồ và phân biệt khái niệm (docs)")

    # 3. Stat/event keywords (leo trèo, cháy, khói, mực nước, đám đông, phát hiện, cảnh báo + time) -> query_data
    # Kể cả khi có AIOC
    has_event_stat = any(k in low for k in (
        "leo trèo", "cháy", "khói", "mực nước", "đám đông", "ẩu đả", "vụ ẩu đả"
    ))
    has_alert_detection_time = any(k in low for k in ("phát hiện", "cảnh báo")) and any(
        t in low for t in ("hôm nay", "ngày", "tuần", "tháng", "khoảng", "từ", "đến")
    )
    has_general_stat = any(k in low for k in (
        "bao nhiêu", "số lượng", "số lượt", "lượt xe", "lượt ra", "lượt vào", "hôm nay có", "vào cổng", "ra cổng"
    ))

    if has_event_stat or has_alert_detection_time:
        return IntentResult(intent="query_data", reason="Offline heuristic: truy vấn sự kiện/thống kê")

    if has_general_stat and not any(k in low for k in ("làm sao", "cách", "hướng dẫn", "vẽ sơ đồ", "sơ đồ", "thêm camera", "quản lý camera")):
        return IntentResult(intent="query_data", reason="Offline heuristic: truy vấn số liệu")

    # 4. Pure AIOC howto/diagram (vẽ sơ đồ, trạng thái trực tuyến, thêm camera) without stat -> how_to
    if any(k in low for k in (
        "vẽ sơ đồ", "sơ đồ", "trạng thái trực tuyến", "trực tuyến", "ngoại tuyến", "bảo trì",
        "thêm camera", "quản lý camera", "làm sao", "cách", "hướng dẫn", "cài đặt", "sử dụng", "xem lại", "đăng nhập", "đăng xuất"
    )):
        return IntentResult(intent="how_to", reason="Offline heuristic: câu hỏi hướng dẫn cách dùng / sơ đồ")

    # 5. Troubleshoot
    if any(k in low for k in ("tại sao", "lỗi", "mất kết nối", "sự cố", "không lên", "hỏng")):
        return IntentResult(intent="troubleshoot", reason="Offline heuristic: câu hỏi sự cố/lỗi")

    # 6. Concept
    if any(k in low for k in ("là gì", "khái niệm", "định nghĩa", "ý nghĩa")):
        return IntentResult(intent="concept", reason="Offline heuristic: câu hỏi khái niệm")

    # 7. Default
    return IntentResult(intent="query_data", reason="Offline heuristic: mặc định truy vấn số liệu")


def classify_intent(question: str | RewrittenQuestion) -> IntentResult:
    """Phân loại ý định câu hỏi thành IntentResult thông qua structured LLM."""
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    cleaned = text.strip()

    if use_offline_tools():
        return _offline_classify(cleaned)

    messages = [
        {"role": "system", "content": registry().render("classify")},
        {"role": "user", "content": f"Câu hỏi: {cleaned}"},
    ]
    return invoke_structured(messages, IntentResult)


def classify_intent_safe(question: str | RewrittenQuestion) -> IntentResult:
    """classify_intent với fallback offline khi LLM lỗi — tránh im lặng/crash."""
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    cleaned = text.strip()
    try:
        return classify_intent(question)
    except Exception:
        return _offline_classify(cleaned)


def classify_intent_str(question: str | RewrittenQuestion) -> str:
    """Helper trả về intent dạng chuỗi ('query_data', 'how_to', ...) cho callers cần str."""
    res = classify_intent(question)
    return res.intent
