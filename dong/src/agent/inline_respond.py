"""Phản hồi chào hỏi (chat) và câu hỏi ngoài phạm vi (out_of_scope) có gợi ý dẫn dắt."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta

from src.config import settings
from src.llm.client import invoke_text, use_offline_tools
from src.prompts import registry

logger = logging.getLogger(__name__)

_DAYS_VN = {
    0: "Thứ Hai",
    1: "Thứ Ba",
    2: "Thứ Tư",
    3: "Thứ Năm",
    4: "Thứ Sáu",
    5: "Thứ Bảy",
    6: "Chủ Nhật",
}


def get_system_time_vietnam() -> str:
    """Lấy thời gian hiện tại theo múi giờ Việt Nam (UTC+7)."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
        now = datetime.now(tz)
    except Exception:
        now = datetime.now(timezone(timedelta(hours=7)))
    day_name = _DAYS_VN.get(now.weekday(), "")
    return f"{day_name}, ngày {now.strftime('%d/%m/%Y, %H:%M:%S')} (Giờ Việt Nam)"


def generate_inline_response(question: str, intent: str = "chat") -> str:
    """Tạo phản hồi thân thiện, trả lời ngắn gọn và chủ động gợi ý về VMS KCN Hưng Phú."""
    q_clean = (question or "").strip()
    current_time = get_system_time_vietnam()

    # 1. Chế độ offline hoặc fallback
    if use_offline_tools():
        q_low = q_clean.lower()
        if intent == "chat":
            return (
                "Chào bạn! Tôi là trợ lý AI giám sát camera VMS KCN Hưng Phú. "
                "Tôi có thể hỗ trợ bạn tra cứu lượt xe ra/vào hôm nay, kiểm tra các sự kiện an ninh "
                "hoặc hướng dẫn thao tác trên hệ thống AIOC."
            )
        if intent == "out_of_scope":
            if any(k in q_low for k in ("ngày", "thứ", "mấy giờ", "thời gian", "hôm nay là")):
                return (
                    f"Hôm nay là {current_time}. "
                    "Tôi là trợ lý AI chuyên về giám sát VMS KCN Hưng Phú. "
                    "Hôm nay bạn có muốn xem thống kê lượng xe ra/vào hoặc kiểm tra cảnh báo an ninh nào trong KCN không?"
                )
            return (
                "Tôi là trợ lý AI chuyên về giám sát camera VMS và phân tích dữ liệu KCN Hưng Phú. "
                "Bạn có thể hỏi tôi về thống kê phương tiện ra/vào, cảnh báo xâm nhập vùng cấm, "
                "nhận diện khuôn mặt hoặc hướng dẫn sử dụng AIOC."
            )
        return "Chào bạn, bạn cần tôi hỗ trợ gì về hệ thống camera và sự kiện tại KCN Hưng Phú?"

    # 2. Chế độ online (Gọi LLM sinh phản hồi ngữ cảnh)
    try:
        system_prompt = registry().render("respond_inline", current_time=current_time)
        user_prompt = f"Ý định người dùng: {intent}\nCâu hỏi: {q_clean}"
        if settings.llm_backend == "self_hosted" or "qwen" in settings.model_name.lower():
            user_prompt = f"/nothink\n{user_prompt}"

        raw = invoke_text(
            system_prompt,
            user_prompt,
            max_tokens=settings.sql_respond_max_tokens or 256,
            substep="respond_inline",
        )
        cleaned = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
        if cleaned:
            return cleaned
    except Exception as e:
        logger.warning(f"Lỗi khi gọi LLM cho respond_inline: {e}")

    # Fallback nếu LLM gặp lỗi
    if intent == "out_of_scope":
        return (
            f"Hôm nay là {current_time}. "
            "Tôi là trợ lý AI chuyên về giám sát VMS KCN Hưng Phú. "
            "Bạn có thể hỏi tôi về thống kê lượng xe ra/vào hôm nay, kiểm tra cảnh báo an ninh hoặc hướng dẫn dùng AIOC."
        )
    return (
        "Chào bạn! Tôi là trợ lý AI giám sát camera VMS KCN Hưng Phú. "
        "Tôi có thể hỗ trợ gì cho bạn về dữ liệu camera, sự kiện hoặc hướng dẫn sử dụng hệ thống?"
    )
