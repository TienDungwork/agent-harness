"""Classify intent — phân loại ý định câu hỏi sang IntentResult structured."""

from __future__ import annotations

from src.llm.client import use_offline_tools
from src.llm.schemas import IntentResult, RewrittenQuestion
from src.llm.structured import invoke_structured

INTENT_SYSTEM_PROMPT = """Bạn là trợ lý phân loại ý định câu hỏi cho hệ thống VMS/camera/an ninh KCN Hưng Phú.
Phân loại câu hỏi của người dùng vào đúng 1 trong 5 loại sau:
- query_data: hỏi về số liệu, đếm số lượng, thống kê, danh sách xe, biển số, sự kiện ra vào.
- how_to: hỏi về cách sử dụng, thao tác, quy trình trên phần mềm VMS/camera (vd: làm sao để thêm camera, cách xem lại video).
- troubleshoot: hỏi cách xử lý sự cố, lỗi kỹ thuật (vd: tại sao camera mất kết nối, cảnh báo lỗi thiết bị).
- concept: hỏi về khái niệm, định nghĩa, thuật ngữ (vd: AIOC là gì, hàng rào ảo là gì).
- out_of_scope: câu hỏi không liên quan đến hệ thống VMS, giao thông, an ninh KCN (vd: thời tiết, nấu ăn, chính trị).

Cung cấp lý do ngắn gọn bằng tiếng Việt trong trường reason.
"""


def _offline_classify(text: str) -> IntentResult:
    """Heuristic offline cho intent khi test hoặc không có LLM."""
    low = text.lower()
    if any(k in low for k in ("làm sao", "cách", "hướng dẫn", "thêm camera", "cài đặt", "sử dụng", "xem lại")):
        return IntentResult(intent="how_to", reason="Offline heuristic: câu hỏi hướng dẫn cách dùng")
    if any(k in low for k in ("tại sao", "lỗi", "mất kết nối", "sự cố", "không lên", "hỏng")):
        return IntentResult(intent="troubleshoot", reason="Offline heuristic: câu hỏi sự cố/lỗi")
    if any(k in low for k in ("là gì", "khái niệm", "định nghĩa", "ý nghĩa")):
        return IntentResult(intent="concept", reason="Offline heuristic: câu hỏi khái niệm")
    if any(k in low for k in ("thời tiết", "bóng đá", "tổng thống", "chính trị", "giá vàng", "nấu ăn")):
        return IntentResult(intent="out_of_scope", reason="Offline heuristic: câu hỏi ngoài phạm vi")
    return IntentResult(intent="query_data", reason="Offline heuristic: mặc định truy vấn số liệu")


def classify_intent(question: str | RewrittenQuestion) -> IntentResult:
    """Phân loại ý định câu hỏi thành IntentResult thông qua structured LLM."""
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    cleaned = text.strip()

    if use_offline_tools():
        return _offline_classify(cleaned)

    messages = [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Câu hỏi: {cleaned}"},
    ]
    return invoke_structured(messages, IntentResult)


def classify_intent_str(question: str | RewrittenQuestion) -> str:
    """Helper trả về intent dạng chuỗi ('query_data', 'how_to', ...) cho callers cần str."""
    res = classify_intent(question)
    return res.intent
