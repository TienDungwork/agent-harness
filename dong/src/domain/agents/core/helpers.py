"""Helpers dùng chung respond + orchestrator synthesis."""

from __future__ import annotations

import re

from src.domain.agents.state import AgentState

_THINKING_BLOCK = re.compile(r"\x3cthink\x3e.*?\x3c/think\x3e", re.DOTALL | re.IGNORECASE)

_STAT_MEMORY_RE = re.compile(
    r"\d[\d.,]*\s*(?:sự kiện|su kien|lượt|luot|cảnh báo|canh bao|phát hiện|phat hien)",
    re.IGNORECASE,
)


def strip_thinking(text: str) -> str:
    if re.search(r"\x3cthink\x3e", text, re.IGNORECASE) and not re.search(
        r"\x3c/think\x3e", text, re.IGNORECASE
    ):
        return ""
    return _THINKING_BLOCK.sub("", text).strip()


def domains_in_text(text: str) -> set[str]:
    from src.domain.agents.orchestrator.plan import _DOMAIN_PHRASES

    low = (text or "").lower()
    return {tbl for phrases, tbl in _DOMAIN_PHRASES if any(p in low for p in phrases)}


def filter_memories_for_stat(memories: list[str], question: str) -> list[str]:
    q_domains = domains_in_text(question)
    kept: list[str] = []
    for memory in memories:
        if _STAT_MEMORY_RE.search(memory):
            continue
        m_domains = domains_in_text(memory)
        if q_domains and m_domains and not m_domains <= q_domains:
            continue
        kept.append(memory)
    return kept


def rewritten_text(state: AgentState) -> str:
    rewritten = state.get("rewritten")
    if rewritten is None:
        return ""
    if hasattr(rewritten, "text"):
        return (rewritten.text or "").strip()
    if isinstance(rewritten, dict):
        return (rewritten.get("text") or "").strip()
    return ""


def original_question(state: AgentState) -> str:
    return (state.get("original_question") or state.get("question") or "").strip()


def effective_question(state: AgentState) -> str:
    return rewritten_text(state) or (state.get("question") or "").strip()


def respond_event_input(state: AgentState, **extra) -> dict:
    return {
        "question": original_question(state),
        "rewritten_question": effective_question(state),
        **extra,
    }


def memory_context_block(state: AgentState, *, for_stat: bool = False, question: str = "") -> str:
    memories = state.get("recalled_memories") or []
    if for_stat:
        memories = filter_memories_for_stat(memories, question)
    if not memories:
        return ""
    lines = "\n".join(f"- {m}" for m in memories)
    stat_rule = ""
    if for_stat:
        stat_rule = (
            "Chỉ dùng bối cảnh người dùng khi liên quan trực tiếp; "
            "KHÔNG bổ sung số liệu ngoài dữ liệu truy vấn.\n\n"
        )
    return f"Thông tin đã biết về user:\n{lines}\n\n{stat_rule}"
