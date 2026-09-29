"""Memory extraction and store module — Trích xuất và lưu trữ thông tin dài hạn (v9).

Cung cấp khả năng nhận diện và chắt lọc các sự thật quan trọng về người dùng:
1. _heuristic_extract(question): Regex tiếng Việt thông minh nhận diện Tên, Vai trò,
   Khu vực/Camera phụ trách, Sở thích và Lưu ý quan trọng; tự động lọc bỏ các câu hỏi truy vấn (ai, gì, sao...).
2. memory_detail_includes_answer(detail): Bộ lọc thông minh phân loại luồng thông tin —
   chỉ cho phép trích xuất ngữ cảnh nghiệp vụ (docs/hướng dẫn), ngăn chặn 100% việc lưu trữ
   các số liệu thống kê realtime biến động tạm thời (lượt xe, đếm đối tượng trong query_data).
3. extract_memories(user_id, question, answer, ...): Trích xuất danh sách fact kết hợp
   giữa heuristic và mô hình LLM chuyên biệt qua prompt memory_extract.
4. extract_from_messages(user_id, messages): Trích xuất fact trực tiếp từ danh sách tin nhắn
   gần nhất của hội thoại (theo chuẩn llm-engineer-demo extract_and_store_node).
5. extract_and_store_memory(user_id, question, answer, ...): Trích xuất và lưu trực tiếp
   vào cơ sở dữ liệu PostgreSQL (hoặc fallback in-memory) mà tuyệt đối không ném exception.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.llm.client import invoke_text, use_offline_tools
from src.memory.context import _role_of, _text_of, format_messages
from src.memory.longterm import save_to_long_term

logger = logging.getLogger(__name__)

# Các từ nghi vấn / câu hỏi cần loại trừ khi trích xuất
_IGNORE_QUESTION_WORDS = (
    "ai",
    "gì",
    "người",
    "sao",
    "không",
    "thế nào",
    "bao nhiêu",
    "mấy",
    "đâu",
    "khi nào",
    "chưa",
)


def _heuristic_extract(question: str) -> list[str]:
    """Heuristic offline trích xuất fact từ câu hỏi của người dùng bằng regex tiếng Việt."""
    facts: list[str] = []
    text = (question or "").strip()
    if not text:
        return facts

    # Nếu câu hỏi là dạng truy vấn (bắt đầu bằng từ để hỏi, hoặc kết thúc bằng ? mà không có khẳng định danh tính)
    # Ví dụ: "Ai phụ trách camera cổng 1?", "Tôi là ai?", "Tôi tên là gì?"
    is_pure_question = text.endswith("?") and not any(
        kw in text.lower() for kw in ("tôi tên là", "tên tôi là", "mình tên là", "tôi phụ trách", "nhớ là", "lưu ý")
    )
    if is_pure_question:
        return facts

    # 1. Tên người dùng: "tôi tên là", "tên tôi là", "tên của tôi là", "mình tên là", "gọi tôi là"
    m = re.search(
        r"(?:tên tôi là|tôi tên là|tên của tôi là|mình tên là|gọi tôi là)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)",
        text,
        re.IGNORECASE,
    )
    extracted_name = ""
    if m:
        name = m.group(1).strip()
        if name and not any(w in name.lower() for w in _IGNORE_QUESTION_WORDS):
            facts.append(f"Tên người dùng là {name}")
            extracted_name = name.lower()

    # 2. Vai trò / phụ trách: "tôi là", "tôi phụ trách", "tôi quản lý", "tôi trực ban", "mình phụ trách", "phụ trách"
    # Dùng negative lookbehind (?<!tên\s)(?<!tên của\s) để không match nhầm "tôi là" trong "tên tôi là ..."
    m = re.search(
        r"(?<!tên\s)(?<!tên của\s)(?:\btôi là\b|\btôi phụ trách\b|\bphụ trách\b|\btôi quản lý\b|\btôi trực ban\b|\bmình phụ trách\b|\bmình là\b|\btôi làm ở\b)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        role = m.group(1).strip()
        # Tránh trùng với tên vừa trích xuất và tránh các từ nghi vấn
        if (
            role
            and role.lower() != extracted_name
            and not any(w in role.lower() for w in _IGNORE_QUESTION_WORDS)
            and not re.search(r"^\s*(?:ai|gì|sao|đâu)\b", text, re.IGNORECASE)
        ):
            facts.append(f"Người dùng phụ trách {role}")

    # 3. Camera / Khu vực quan sát: "tôi theo dõi camera", "tôi giám sát camera"
    m = re.search(
        r"(?:tôi theo dõi|tôi giám sát|tôi quan sát)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        cam = m.group(1).strip()
        if cam and not any(w in cam.lower() for w in _IGNORE_QUESTION_WORDS):
            fact_cam = f"Người dùng theo dõi {cam}"
            if fact_cam not in facts:
                facts.append(fact_cam)

    # 4. Sở thích / ưu tiên: "tôi thích", "tôi ưu tiên", "tôi quan tâm", "mình thích"
    m = re.search(
        r"(?:tôi thích|tôi ưu tiên|tôi quan tâm|mình thích)\s+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        pref = m.group(1).strip()
        if pref and not any(w in pref.lower() for w in _IGNORE_QUESTION_WORDS):
            facts.append(f"Người dùng quan tâm {pref}")

    # 5. Chỉ định ghi nhớ: "nhớ là", "ghi nhớ", "lưu ý", "nhớ kỹ", "hãy nhớ"
    m = re.search(
        r"(?:nhớ là|ghi nhớ|lưu ý|nhớ kỹ|hãy nhớ)\s*[:\s]+([A-Za-zÀ-ỹ0-9\s]+?)(?:[.,;!?]|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        note = m.group(1).strip()
        if note and not any(w in note.lower() for w in _IGNORE_QUESTION_WORDS):
            facts.append(f"Ghi nhớ: {note}")

    return facts


def memory_detail_includes_answer(detail: str) -> bool:
    """Lọc thông tin: Chỉ dùng câu trả lời khi là tài liệu/nghiệp vụ; bỏ qua số liệu thống kê realtime.

    Trả về:
        True: nếu nhánh nghiệp vụ tài liệu (docs) có thể chứa chính sách, quy định lâu dài.
        False: nếu nhánh truy vấn số liệu (query_data) chứa các con số tạm thời (lượt xe, đếm xe).
    """
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

    # Nếu không được phép lấy thông tin từ câu trả lời (e.g. query_data) hoặc đang ở offline mode
    if not use_answer or use_offline_tools():
        return heuristics

    extracted = list(heuristics)
    try:
        from src.prompts import registry

        try:
            prompt = registry().render("memory_extract")
        except Exception:
            prompt = (
                "Bạn là trợ lý trích xuất thông tin bộ nhớ dài hạn cho hệ thống KCN Hưng Phú. "
                "Đọc đoạn hội thoại, trích xuất sở thích, thông tin cá nhân, vai trò của người dùng. "
                "Bỏ qua số liệu thời điểm, tạm thời. Trả về mỗi thông tin 1 dòng hoặc 'NONE'."
            )

        user_content = (
            f"Đoạn hội thoại:\n"
            f"Người dùng: {question}\n"
            f"Trợ lý: {answer}\n\n"
            f"Hãy trích xuất các thông tin cần ghi nhớ lâu dài (mỗi thông tin một dòng ngắn gọn). "
            f"Nếu không có thông tin nào cần ghi nhớ, trả về KHONG."
        )
        raw = invoke_text(prompt, user_content, substep="memory_extract")
        for line in raw.splitlines():
            cleaned = line.strip()
            # Bỏ bullet numbering
            cleaned = re.sub(r"^[\d\.\-\*\s]+", "", cleaned).strip()
            if not cleaned or cleaned.upper() in ("KHONG", "NONE", "KHÔNG", "KHÔNG CÓ", "N/A", "NULL"):
                continue
            if len(cleaned) > 5 and cleaned not in extracted:
                extracted.append(cleaned)
    except Exception as exc:
        logger.debug("extract_memories online LLM fallback to heuristics: %s", exc)

    return extracted


def extract_from_messages(user_id: str, messages: list[Any]) -> list[str]:
    """Trích xuất fact từ danh sách tin nhắn hội thoại gần nhất (chuẩn llm-engineer-demo)."""
    if not user_id or not messages:
        return []

    # Tìm câu hỏi người dùng gần nhất
    latest_user_text = ""
    latest_ai_text = ""
    for m in reversed(messages):
        role = _role_of(m)
        if not latest_user_text and role in ("human", "user"):
            latest_user_text = _text_of(m)
        elif not latest_ai_text and role in ("ai", "assistant"):
            latest_ai_text = _text_of(m)
        if latest_user_text and latest_ai_text:
            break

    if not latest_user_text:
        return []

    return extract_memories(user_id, latest_user_text, latest_ai_text, include_answer=False)


def extract_and_store_memory(
    user_id: str,
    question: str,
    answer: str = "",
    *,
    include_answer: bool | None = None,
    detail: str = "",
) -> list[str]:
    """Trích xuất và lưu ngay các fact vào long-term memory cho user_id.

    Bảo đảm Graceful Degradation: Nếu có lỗi xảy ra, chỉ log cảnh báo và trả về danh sách rỗng,
    tuyệt đối không quăng ngoại lệ ra ngoài.
    """
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
