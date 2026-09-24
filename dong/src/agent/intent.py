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
    "vi phạm",
    "vi pham",
)


def is_stat_event_domain(text: str) -> bool:
    """True nếu câu hỏi thuộc domain thống kê fire/anomaly/water (không phải howto thuần)."""
    low = (text or "").lower()
    if any(k in low for k in STAT_EVENT_DOMAIN_KEYWORDS):
        return True
    return any(k in low for k in ("phát hiện", "cảnh báo")) and any(
        t in low for t in ("hôm nay", "hôm qua", "ngày", "tuần", "tháng", "khoảng", "từ", "đến")
    )


from src.guardrails import CHAT_GREETING_KEYWORDS, is_chat_greeting

is_chat_like = is_chat_greeting


def _offline_classify(text: str) -> IntentResult:
    """Heuristic offline cho intent khi test hoặc không có LLM."""
    low = text.lower()
    cleaned = text.strip()

    # 0. Greetings / Chat
    if is_chat_greeting(cleaned):
        return IntentResult(
            intent="chat",
            reason="Offline heuristic: chào hỏi, giao tiếp cơ bản",
            answer="Chào bạn, tôi là trợ lý ảo AIOC. Bạn cần tôi giúp gì về hệ thống camera và sự kiện?",
        )
        
    # 0.1 Clarify for vague empty-ish
    if not cleaned or len(cleaned) < 3:
        return IntentResult(
            intent="clarify",
            reason="Offline heuristic: câu quá ngắn hoặc rỗng",
            answer="Bạn có thể nói rõ hơn yêu cầu của mình được không?"
        )

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


_NEEDS_PIPELINE = frozenset(
    {
        "query_data",
        "how_to",
        "troubleshoot",
        "concept",
        "out_of_scope",
    }
)


def sanitize_intent_result(res: IntentResult) -> IntentResult:
    """Xóa answer với các intent pipeline để chống fake inline skip."""
    if res.intent in _NEEDS_PIPELINE:
        res.answer = ""
    return res


def classify_intent(question: str | RewrittenQuestion) -> IntentResult:
    """Phân loại ý định câu hỏi thành IntentResult thông qua structured LLM."""
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    cleaned = text.strip()

    if use_offline_tools():
        return sanitize_intent_result(_offline_classify(cleaned))

    messages = [
        {"role": "system", "content": registry().render("classify")},
        {"role": "user", "content": f"Câu hỏi: {cleaned}"},
    ]
    raw = invoke_structured(messages, IntentResult, substep="classify")
    return sanitize_intent_result(raw)


_HOW_TO_OVERRIDE_KEYWORDS = (
    "vẽ sơ đồ",
    "sơ đồ",
    "quản lý camera",
    "aioc.atin.vn",
    "aioc",
    "/devices",
    "devices",
    "đăng nhập",
    "thêm camera",
    "trực tuyến",
    "ngoại tuyến",
)


def _is_how_to_override(text: str) -> bool:
    """True nếu câu hỏi chứa từ khóa rõ ràng thuộc how_to — không thể là clarify."""
    low = (text or "").lower()
    return any(k in low for k in _HOW_TO_OVERRIDE_KEYWORDS)


def classify_intent_safe(question: str | RewrittenQuestion) -> IntentResult:
    """classify_intent với fallback offline khi LLM lỗi — tránh im lặng/crash."""
    if hasattr(question, "text"):
        cleaned = (question.text or "").strip()
    elif isinstance(question, dict):
        cleaned = (question.get("text") or "").strip()
    else:
        cleaned = str(question).strip()

    try:
        result = classify_intent(question)
        low = cleaned.lower()
        # Override 1: nếu LLM trả clarify cho câu hỏi rõ ràng là how_to → sửa lại
        if result.intent == "clarify" and _is_how_to_override(cleaned):
            return sanitize_intent_result(IntentResult(
                intent="how_to",
                reason="Override: câu hỏi rõ ràng là how_to (vẽ sơ đồ / AIOC / devices)",
            ))
        # Override 2: nếu LLM trả query_data cho câu hỏi vẽ sơ đồ AIOC / so sánh khái niệm
        if result.intent == "query_data" and ("vẽ sơ đồ" in low or "sơ đồ" in low) and any(k in low for k in ("devices", "aioc", "phân biệt", "khác gì")):
            return sanitize_intent_result(IntentResult(
                intent="how_to",
                reason="Override: câu hỏi sơ đồ phân biệt khái niệm / AIOC",
            ))
        return result
    except Exception:
        return sanitize_intent_result(_offline_classify(cleaned))



def classify_intent_str(question: str | RewrittenQuestion) -> str:
    """Helper trả về intent dạng chuỗi ('query_data', 'how_to', ...) cho callers cần str."""
    res = classify_intent(question)
    return res.intent
