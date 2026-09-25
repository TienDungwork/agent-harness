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


def rewrite_question(raw: str) -> RewrittenQuestion:
    """Chuẩn hóa câu hỏi — decompose sub_questions khi câu đủ phức tạp."""
    cleaned = (raw or "").strip()
    if not cleaned:
        return RewrittenQuestion(text="")

    if is_chat_greeting(cleaned):
        return RewrittenQuestion(text=cleaned, sub_questions=[cleaned], intent_hint="chat")

    if not _needs_rewrite_llm(cleaned):
        return _passthrough_rewrite(cleaned)

    messages = [
        {"role": "system", "content": registry().render("rewrite")},
        {"role": "user", "content": f"Câu hỏi gốc: {cleaned}"},
    ]
    return _normalize_rewritten(invoke_structured(messages, RewrittenQuestion, substep="rewrite"))


def rewrite_question_safe(raw: str) -> RewrittenQuestion:
    """Alias — lỗi propagate lên caller."""
    return rewrite_question(raw)
