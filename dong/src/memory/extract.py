"""Memory extraction and store module — trích xuất thông tin người dùng và lưu vào long-term memory."""
from __future__ import annotations

import logging
import re

from src.llm.client import invoke_text, use_offline_tools
from src.memory.longterm import save_to_long_term
from src.prompts import registry

logger = logging.getLogger(__name__)


def _heuristic_extract(question: str) -> list[str]:
    """Heuristic offline trích xuất fact từ câu hỏi của người dùng."""
    facts: list[str] = []
    text = (question or "").strip()

    # Tên người dùng
    m = re.search(r"(?:tên tôi là|tôi tên là)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if name:
            facts.append(f"Tên người dùng là {name}")

    # Vai trò / phụ trách
    m = re.search(r"(?:tôi là|tôi phụ trách|tôi quản lý)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)", text, re.IGNORECASE)
    if m:
        role = m.group(1).strip()
        if role and not any(w in role.lower() for w in ("ai", "gì", "người", "sao")):
            facts.append(f"Người dùng phụ trách {role}")

    # Sở thích / ưu tiên
    m = re.search(r"(?:tôi thích|tôi ưu tiên|tôi quan tâm)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)", text, re.IGNORECASE)
    if m:
        pref = m.group(1).strip()
        if pref and not any(w in pref.lower() for w in ("gì", "sao", "không")):
            facts.append(f"Người dùng quan tâm {pref}")

    # Chỉ định ghi nhớ
    m = re.search(r"(?:nhớ là|ghi nhớ|lưu ý)\s*[:\s]+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)", text, re.IGNORECASE)
    if m:
        note = m.group(1).strip()
        if note:
            facts.append(f"Ghi nhớ: {note}")

    return facts


def memory_detail_includes_answer(detail: str) -> bool:
    """Chỉ dùng câu trả lời khi extract memory — bỏ số liệu thống kê realtime."""
    d = (detail or "").strip().lower()
    if d == "docs":
        return True
    if d in ("query_data", "out_of_scope") or d.startswith("orchestrator"):
        return False
    return False


def extract_memories(
    user_id: str,
    question: str,
    answer: str = "",
    *,
    include_answer: bool | None = None,
    detail: str = "",
) -> list[str]:
    """Trích xuất danh sách các fact cần lưu dài hạn cho user_id từ câu hỏi và câu trả lời."""
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        return []
    if not question or not isinstance(question, str) or not question.strip():
        return []

    heuristics = _heuristic_extract(question)
    use_answer = memory_detail_includes_answer(detail) if include_answer is None else include_answer
    if not use_answer:
        return heuristics

    if use_offline_tools():
        return heuristics

    extracted = list(heuristics)
    try:
        prompt = registry().render("memory_extract")
        user_content = (
            f"Đoạn hội thoại:\n"
            f"Người dùng: {question}\n"
            f"Trợ lý: {answer}\n\n"
            f"Hãy trích xuất các thông tin cần ghi nhớ lâu dài (mỗi thông tin một dòng ngắn gọn). "
            f"Nếu không có thông tin nào cần ghi nhớ, trả về KHONG."
        )
        raw = invoke_text(prompt, user_content)
        for line in raw.splitlines():
            cleaned = line.strip()
            # Bỏ bullet numbering
            cleaned = re.sub(r"^[\d\.\-\*\s]+", "", cleaned).strip()
            if not cleaned or cleaned.upper() in ("KHONG", "NONE", "KHÔNG", "KHÔNG CÓ"):
                continue
            if len(cleaned) > 5 and cleaned not in extracted:
                extracted.append(cleaned)
    except Exception:
        pass  # Fallback to heuristics on LLM error

    return extracted


def extract_and_store_memory(
    user_id: str,
    question: str,
    answer: str = "",
    *,
    include_answer: bool | None = None,
    detail: str = "",
) -> list[str]:
    """Trích xuất và lưu ngay các fact vào long-term memory cho user_id."""
    try:
        facts = extract_memories(
            user_id,
            question,
            answer,
            include_answer=include_answer,
            detail=detail,
        )
        for fact in facts:
            save_to_long_term(user_id, fact)
        return facts
    except Exception as exc:
        logger.warning("extract_and_store_memory failed: %s", exc)
        return []
