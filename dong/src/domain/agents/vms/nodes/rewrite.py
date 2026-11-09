"""Rewrite question — chuẩn hóa, tách sub_questions (decompose gom trong rewrite)."""

from __future__ import annotations

from typing import Any

from src.domain.agents.vms.nodes.intent import is_chat_greeting
from src.infra.chart.render import should_render_chart
from src.shared.config import settings
from src.infra.llm.schemas import RewrittenQuestion
from src.infra.llm.structured import invoke_structured
from src.infra.prompts import registry


def _needs_rewrite_llm(cleaned: str) -> bool:
    """Câu ngắn/đơn — passthrough, không gọi LLM (giống decompose_query min_chars)."""
    from src.domain.agents.multi_agent.plan import _multi_question_heuristics

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


def _message_role_and_content(m: Any) -> tuple[str, str]:
    if isinstance(m, dict):
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
    else:
        role = str(getattr(m, "type", "") or getattr(m, "role", "") or "")
        content = str(getattr(m, "content", "") or "")
    if role in ("human", "HumanMessage"):
        role = "user"
    elif role in ("ai", "assistant", "AIMessage"):
        role = "assistant"
    return role, content.strip()


def _history_had_chart_intent(history: list[Any] | None) -> bool:
    """User đã yêu cầu vẽ biểu đồ trong các lượt trước (theo lịch sử session/checkpoint)."""
    if not history:
        return False
    for m in history:
        role, content = _message_role_and_content(m)
        if role == "user" and content and should_render_chart(content):
            return True
        if isinstance(m, dict) and m.get("chart"):
            return True
        detail = m.get("detail") if isinstance(m, dict) else getattr(m, "detail", None)
        if isinstance(detail, dict) and detail.get("chart_spec"):
            return True
    return False


def _inject_chart_wording(text: str) -> str:
    s = (text or "").strip()
    if not s or should_render_chart(s):
        return s
    if s.lower().startswith("thống kê"):
        return "Vẽ biểu đồ " + s[0].lower() + s[1:]
    return f"Vẽ biểu đồ — {s}"


def _apply_chart_followup_inheritance(
    cleaned: str,
    history: list[Any] | None,
    result: RewrittenQuestion,
) -> RewrittenQuestion:
    """Follow-up sau câu vẽ biểu đồ: đảm bảo text/sub_questions giữ ý visualization."""
    if not _is_followup_question(cleaned):
        return result
    if should_render_chart(cleaned):
        return result
    if not _history_had_chart_intent(history):
        return result
    text = (result.text or "").strip()
    if text and not should_render_chart(text):
        text = _inject_chart_wording(text)
    subs = [
        _inject_chart_wording(s) if s else s
        for s in (result.sub_questions or [])
    ]
    subs = [s for s in subs if (s or "").strip()]
    if not subs and text:
        subs = [text]
    return result.model_copy(update={"text": text or result.text, "sub_questions": subs or result.sub_questions})


def _format_history_for_rewrite(history: list[Any] | None, max_turns: int = 4) -> str:
    if not history:
        return ""
    lines = []
    recent = history[-max_turns:]
    for m in recent:
        role, content = _message_role_and_content(m)
        if not content:
            continue
        role_label = "User" if role == "user" else "Assistant"
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
    inherit_chart = is_followup and _history_had_chart_intent(history)

    if not _needs_rewrite_llm(cleaned) and not is_followup:
        out = _passthrough_rewrite(cleaned)
        return _apply_chart_followup_inheritance(cleaned, history, out)

    user_content = f"Câu hỏi gốc: {cleaned}"
    if has_history:
        chart_note = ""
        if inherit_chart:
            chart_note = (
                "\nQUAN TRỌNG — KẾ THỪA VẼ BIỂU ĐỒ:\n"
                "- Lượt trước user đã yêu cầu vẽ biểu đồ/chart/đồ thị.\n"
                "- Câu hiện tại là nối tiếp cùng kiểu số liệu → `text` và MỖI `sub_questions` "
                "PHẢI bắt đầu bằng cụm 'Vẽ biểu đồ' (vd: 'Vẽ biểu đồ thống kê sự kiện vùng cấm hôm nay').\n"
                "- Không đổi sang câu chỉ 'Thống kê...' nếu làm mất yêu cầu visualization.\n"
            )
        user_content = (
            f"Lịch sử hội thoại gần nhất:\n{history_text}\n\n"
            f"Câu hỏi hiện tại: {cleaned}\n"
            f"{chart_note}"
            f"HƯỚNG DẪN KHI CÂU HỎI LÀ NỐI TIẾP / RÚT GỌN (ví dụ: 'vậy còn...', 'thế còn...', 'còn... thì sao'):\n"
            f"1. Kế thừa linh hoạt ngữ cảnh câu trước (thời gian, địa điểm, cấu trúc câu hỏi: có bao nhiêu / danh sách / thống kê / vẽ biểu đồ...; "
            f"nếu lượt trước có vẽ biểu đồ/chart/đồ thị, BẮT BUỘC giữ 'Vẽ biểu đồ' trong `text` và sub_questions).\n"
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
        out = _normalize_rewritten(invoke_structured(messages, RewrittenQuestion, substep="rewrite"))
        return _apply_chart_followup_inheritance(cleaned, history, out)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("rewrite_question failed, falling back to passthrough: %s", exc)
        out = _passthrough_rewrite(cleaned)
        return _apply_chart_followup_inheritance(cleaned, history, out)


def rewrite_question_safe(raw: str, history: list[Any] | None = None) -> RewrittenQuestion:
    """Alias — hỗ trợ truyền history."""
    return rewrite_question(raw, history=history)

