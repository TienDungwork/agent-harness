"""Rewrite question — chuẩn hóa, tách sub_questions (decompose gom trong rewrite)."""

from __future__ import annotations

from src.agent.intent import is_chat_greeting
from src.config import settings
from src.llm.schemas import RewrittenQuestion
from src.llm.structured import invoke_structured
from src.prompts import registry


def _needs_rewrite_llm(cleaned: str) -> bool:
    """Câu ngắn/đơn — passthrough, không gọi LLM (giống decompose_query min_chars)."""
    from src.agent.orchestrator import _multi_question_heuristics

    if _multi_question_heuristics(cleaned):
        return True
    return len(cleaned) >= settings.agent_decompose_min_chars


def _passthrough_rewrite(cleaned: str) -> RewrittenQuestion:
    return RewrittenQuestion(text=cleaned, sub_questions=[cleaned])


def _normalize_rewritten(result: RewrittenQuestion) -> RewrittenQuestion:
    text = (result.text or "").strip()
    subs = [s.strip() for s in (result.sub_questions or []) if (s or "").strip()]
    max_n = max(1, settings.agent_max_sub_questions)
    if len(subs) > max_n:
        subs = subs[:max_n]
    if not subs and text:
        subs = [text]
    if not text and subs:
        text = subs[0]
    return result.model_copy(update={"text": text, "sub_questions": subs})


def _is_followup_question(cleaned: str) -> bool:
    low = cleaned.lower()
    return any(
        low.startswith(p) or f" {p}" in low
        for p in ("vậy còn", "thế còn", "còn ", "thì sao", "thì như thế nào", "đối với")
    )


def _format_history_for_rewrite(history: list[Any] | None, max_turns: int = 4) -> str:
    if not history:
        return ""
    lines = []
    recent = history[-max_turns:]
    for m in recent:
        if isinstance(m, dict):
            role = m.get("role", "")
            content = m.get("content", "")
        else:
            role = getattr(m, "type", "") or getattr(m, "role", "")
            content = getattr(m, "content", "")
        if not content:
            continue
        role_label = "User" if role in ("user", "human") else "Assistant"
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def rewrite_question(raw: str, history: list[Any] | None = None) -> RewrittenQuestion:
    """Chuẩn hóa câu hỏi — decompose sub_questions khi câu đủ phức tạp, kết hợp ngữ cảnh nếu có."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return RewrittenQuestion(text="")

    if is_chat_greeting(cleaned):
        return RewrittenQuestion(text=cleaned, sub_questions=[cleaned], intent_hint="chat")

    history_text = _format_history_for_rewrite(history)
    has_history = bool(history_text.strip())
    is_followup = has_history and _is_followup_question(cleaned)

    if not _needs_rewrite_llm(cleaned) and not is_followup:
        return _passthrough_rewrite(cleaned)

    user_content = f"Câu hỏi gốc: {cleaned}"
    if has_history:
        user_content = (
            f"Lịch sử hội thoại gần nhất:\n{history_text}\n\n"
            f"Câu hỏi hiện tại: {cleaned}\n"
            f"HƯỚNG DẪN KHI CÂU HỎI LÀ NỐI TIẾP / RÚT GỌN (ví dụ: 'vậy còn...', 'thế còn...', 'còn... thì sao'):\n"
            f"1. Kế thừa linh hoạt ngữ cảnh câu trước (thời gian, địa điểm, cấu trúc câu hỏi: có bao nhiêu / danh sách / thống kê...).\n"
            f"2. CHUYỂN ĐỔI CHÍNH XÁC ĐỐI TƯỢNG VÀ HÀNH ĐỘNG THEO DOMAIN MỚI:\n"
            f"   - Nếu câu mới hỏi về 'vùng cấm / hàng rào / xâm nhập / leo trèo' (ZONE): hành động là 'sự kiện/phát hiện xâm nhập hoặc leo trèo vùng cấm', TUYỆT ĐỐI KHÔNG tự tiện gắn thêm từ 'xe' hay 'phương tiện' nếu câu hỏi hiện tại không yêu cầu.\n"
            f"   - Nếu câu mới hỏi về 'khuôn mặt / nhận diện' (FACE): hành động là 'sự kiện nhận diện khuôn mặt / người lạ'.\n"
            f"   - Nếu câu mới hỏi về 'ẩu đả' (FIGHT) / 'đám đông' (CROWD) / 'cháy khói' (FIRE) / 'ngập lụt / mực nước' (WATER): dùng đúng hành động/sự kiện của domain đó.\n"
            f"   - Chỉ giữ đối tượng phương tiện/xe khi câu mới thực sự nói về xe hoặc biển số.\n"
            f"3. Viết lại thành một câu hỏi độc lập, mạch lạc, tự nhiên và đầy đủ thông tin (domain + hành động + thời gian)."
        )

    messages = [
        {"role": "system", "content": registry().render("rewrite")},
        {"role": "user", "content": user_content},
    ]
    try:
        return _normalize_rewritten(invoke_structured(messages, RewrittenQuestion, substep="rewrite"))
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("rewrite_question failed, falling back to passthrough: %s", exc)
        return _passthrough_rewrite(cleaned)


def rewrite_question_safe(raw: str, history: list[Any] | None = None) -> RewrittenQuestion:
    """Alias — hỗ trợ truyền history."""
    return rewrite_question(raw, history=history)

