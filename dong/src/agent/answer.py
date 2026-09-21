"""Answer — diễn giải (các) QueryResult thành câu trả lời tiếng Việt tự
nhiên. 1 lời gọi LLM NGẮN, không tool — chỉ viết văn từ số liệu đã có sẵn
trong prompt (chặn hallucination: model không tự tính toán số mới, chỉ diễn
giải số liệu đã truy vấn).

Tắt qua ANSWER_USE_LLM=false trong .env để luôn dùng template dựng sẵn
(latency thấp, không cần chờ LLM — hữu ích khi model local chậm trên 4GB
VRAM). Offline mode (pytest/không key) và trường hợp lỗi/rỗng cũng rơi về
template — không gọi LLM khi không cần.
"""

from __future__ import annotations

from src.config import settings
from src.prompts import registry


def _get_system_prompt() -> str:
    return registry().render("agent_answer", version="production")


# DB chỉ có vehicle_type ∈ {BUS, CAR, MOTORCYCLE, TRUCK} — KHÔNG phân loại ô
# tô theo số chỗ ngồi (5/7/9/16/29/40 chỗ), xem src/db/queries.py::
# count_vehicle_flow. Acceptance criteria (test-plan.md, câu hỏi mẫu #2) yêu
# cầu giới hạn này phải được nêu rõ trong câu trả lời — thêm cứng vào
# template fallback vì đó là đường không qua LLM, không thể trông cậy model
# tự nhắc.
_SEAT_LIMIT_NOTE = (
    "Lưu ý: dữ liệu chỉ phân loại xe theo BUS/CAR/MOTORCYCLE/TRUCK, "
    "không có thông tin số chỗ ngồi (5/7/9/16/29/40 chỗ)."
)


def _mentions_seat_count(question: str) -> bool:
    return "chỗ" in question.lower()


def _with_seat_limit_note(question: str, queries: list, answer: str) -> str:
    has_vehicle_type_col = any("vehicle_type" in q.columns for q in queries)
    if _mentions_seat_count(question) and has_vehicle_type_col and _SEAT_LIMIT_NOTE not in answer:
        return f"{answer}\n\n{_SEAT_LIMIT_NOTE}"
    return answer


def build_answer(question: str, queries: list, template_answer: str) -> str:
    """`queries`: list[QueryResult] đã lấy được (không rỗng). `template_answer`:
    câu trả lời template đã dựng sẵn (từ src/agent/graph.py) — dùng làm
    fallback khi tắt LLM, offline, hoặc lời gọi LLM lỗi."""
    if not settings.answer_use_llm:
        return _with_seat_limit_note(question, queries, template_answer)

    from src.llm import invoke_text, use_offline_tools

    if use_offline_tools():
        return template_answer

    has_rows = any(not q.error and q.rows for q in queries)
    if not has_rows:
        return template_answer

    data_blocks = []
    for q in queries:
        if q.error or not q.rows:
            continue
        lines = [", ".join(f"{c}={v}" for c, v in zip(q.columns, row)) for row in q.rows[:30]]
        data_blocks.append(f"[{q.tool}] ({q.row_count} dòng, cột: {q.columns}):\n" + "\n".join(lines))

    user_prompt = f"Câu hỏi: {question}\n\nDữ liệu:\n" + "\n\n".join(data_blocks)
    try:
        text = invoke_text(_get_system_prompt(), user_prompt).strip()
        answer = text or template_answer
    except Exception:
        answer = template_answer
    return _with_seat_limit_note(question, queries, answer)
