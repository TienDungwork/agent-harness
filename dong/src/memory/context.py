"""Context engineering engine — Quản lý cửa sổ ngữ cảnh cho multi-agent theo kiến trúc v9.

Dựa trên các chiến lược chuẩn từ llm-engineer-demo (Module II):
- Sliding Window (Section 2): Giữ N message gần nhất, luôn bảo tồn system message khởi tạo.
- Ước lượng Token & Nguyên tắc 40-60% (Section 4): Giám sát tỷ lệ lấp đầy context, kích hoạt
  nén CHỦ ĐỘNG khi vượt ngưỡng 40% để ngăn chặn hiện tượng suy giảm chất lượng (context rot).
- Summarization (Section 2): Tóm tắt hội thoại cũ thành 3-5 câu mang tiền tố [Tóm tắt hội thoại trước]: ...
- Tool-Output Compression (Section 3): Nén kết quả tool (SQL bảng dài, docs) trước khi nạp vào context.
- Instruction Re-injection (Section 4): Tái chèn quy tắc cốt lõi ở cuối prompt chống instruction fade-out.
- Latest Human Query Scanning: Quét ngược tìm tin nhắn người dùng gần nhất cho tool retrieval / memory recall.
- Loop Termination & Repetition Guard: Phát hiện agent bị lặp lại cùng tool call để ngắt vòng lặp vô tận.
- Compaction State Persisting: Tạo diff RemoveMessage để ghi đè state trong LangGraph (nén 1 lần, dùng nhiều lần).
- Conditional Edge Route: Điều hướng 'compact' vs 'continue' dựa trên ngưỡng nén 40%.
"""
from __future__ import annotations

import logging
from typing import Any

from src.llm.client import invoke_text, use_offline_tools

logger = logging.getLogger(__name__)

# Ước lượng thô 1 token ≈ 4 ký tự
_CHARS_PER_TOKEN = 4

SUMMARY_PREFIX = "[Tóm tắt hội thoại trước]:"
REINJECT_PREFIX = "[Nhắc lại chỉ dẫn]:"
REPETITION_WARNING = "Bạn đang lặp lại cùng 1 hành động. Hãy thử cách tiếp cận hoàn toàn khác."


def _text_of(m: Any) -> str:
    """Lấy nội dung text từ message (hỗ trợ cả dict và LangChain BaseMessage)."""
    if isinstance(m, dict):
        return str(m.get("content", ""))
    return str(getattr(m, "content", ""))


def _role_of(m: Any) -> str:
    """Lấy role/type chuẩn từ message (hỗ trợ cả dict và LangChain BaseMessage)."""
    if isinstance(m, dict):
        return str(m.get("role", ""))
    return str(getattr(m, "type", ""))


def format_messages(messages: list[Any]) -> str:
    """Chuyển danh sách message thành dạng text có format role: content."""
    return "\n".join(f"{_role_of(m)}: {_text_of(m)}" for m in messages)


# ── Section 1: Sliding Window ──────────────────────────────────────────────────

def sliding_window(messages: list[Any], max_messages: int = 20) -> list[Any]:
    """Giữ N message gần nhất, luôn bảo tồn system message gốc ở đầu nếu có."""
    if len(messages) <= max_messages:
        return list(messages)

    system_msgs = [m for m in messages if _role_of(m) in ("system",)]
    recent = list(messages[-max_messages:])
    recent_ids = {id(m) for m in recent}

    # Giữ các system message chưa lọt vào danh sách recent
    return [m for m in system_msgs if id(m) not in recent_ids] + recent


# ── Section 2: Token Estimation & 40-60% Rule ──────────────────────────────────

def estimate_tokens(messages: list[Any]) -> int:
    """Ước lượng số token của danh sách messages theo ký tự (4 ký tự/token)."""
    return sum(len(_text_of(m)) for m in messages) // _CHARS_PER_TOKEN


def context_usage(messages: list[Any], window_tokens: int) -> float:
    """Tính tỷ lệ sử dụng context [0.0 - 1.0+] so với dung lượng window."""
    if window_tokens <= 0:
        return 0.0
    return estimate_tokens(messages) / float(window_tokens)


def should_compact(messages: list[Any], window_tokens: int, threshold: float = 0.40) -> bool:
    """Kiểm tra điều kiện kích hoạt nén chủ động theo nguyên tắc 40-60%.

    Chủ động tóm tắt sớm ở ngưỡng 40% để ngăn chặn hiện tượng context rot
    khiến chất lượng suy giảm trước khi window đầy.
    """
    return context_usage(messages, window_tokens) > threshold


def should_compact_route(messages_or_state: Any, window_tokens: int, threshold: float = 0.40) -> str:
    """Conditional edge cho LangGraph: history vượt ngưỡng 40% -> 'compact', ngược lại -> 'continue'."""
    messages = messages_or_state
    if isinstance(messages_or_state, dict) and "messages" in messages_or_state:
        messages = messages_or_state["messages"]

    if not isinstance(messages, (list, tuple)):
        return "continue"

    if should_compact(messages, window_tokens, threshold=threshold):
        return "compact"
    return "continue"


# ── Section 3: Summarization ──────────────────────────────────────────────────

def summarize_text(old_messages: list[Any]) -> str:
    """Gọi LLM tóm tắt đoạn hội thoại cũ thành 3-5 câu (giữ số liệu, tên, camera, quyết định)."""
    if not old_messages:
        return ""

    formatted = format_messages(old_messages)
    system_prompt = "Bạn là trợ lý AI chuyên tóm tắt ngữ cảnh hội thoại camera an ninh KCN."
    user_prompt = (
        "Tóm tắt cuộc hội thoại sau thành 3-5 câu ngắn gọn, súc tích, giữ lại các thông tin quan trọng "
        "(tên người dùng, vai trò, camera quan tâm, các mốc thời gian và số liệu đã thống kê):\n\n"
        f"{formatted}"
    )

    try:
        if use_offline_tools():
            return "Hội thoại trước đó trao đổi về thông tin người dùng và các sự kiện giám sát camera."
        return invoke_text(system_prompt, user_prompt, substep="context_summarize").strip()
    except Exception as exc:
        logger.warning("summarize_text LLM call failed, using fallback: %s", exc)
        return "Hội thoại trước đó trao đổi về thông tin người dùng và các sự kiện giám sát camera."


def summarize_old_messages(messages: list[Any], keep_recent: int = 6) -> list[Any]:
    """Tóm tắt phần hội thoại cũ thành 1 system message, giữ nguyên keep_recent message gần nhất.
    
    Bản thuần (ephemeral) trả về list mới, tiện minh hoạ và kiểm thử nhanh.
    """
    if len(messages) <= keep_recent + 1:
        return list(messages)

    old_messages = messages[:-keep_recent]
    recent_messages = list(messages[-keep_recent:])
    summary = summarize_text(old_messages)
    summary_text = f"{SUMMARY_PREFIX} {summary}"

    first_msg = messages[0] if messages else None
    if first_msg and hasattr(first_msg, "__class__") and not isinstance(first_msg, dict):
        try:
            from langchain_core.messages import SystemMessage
            summary_msg = SystemMessage(content=summary_text)
        except Exception:
            summary_msg = {"role": "system", "content": summary_text}
    else:
        summary_msg = {"role": "system", "content": summary_text}

    return [summary_msg] + recent_messages


def create_compaction_diff(messages: list[Any], keep_recent: int = 6) -> dict[str, list[Any]]:
    """Tạo diff nén history để persist vào LangGraph state (thay vì nén tạm mỗi lượt).

    Trả về:
        {"messages": [RemoveMessage(id=...) cho các message cũ] + [summary_msg]}
    được sử dụng bởi reducer add_messages của LangGraph để ghi đè lịch sử gọn gàng,
    giúp các vòng lặp sau kế thừa bản nén mà không phải gọi LLM tóm tắt lại từ đầu.
    """
    if len(messages) <= keep_recent + 1:
        return {}

    old_messages = messages[:-keep_recent]
    summary = summarize_text(old_messages)
    summary_text = f"{SUMMARY_PREFIX} {summary}"

    removals = []
    try:
        from langchain_core.messages import RemoveMessage, SystemMessage
        for m in old_messages:
            mid = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
            if mid:
                removals.append(RemoveMessage(id=mid))
        summary_msg = SystemMessage(content=summary_text)
    except Exception:
        for m in old_messages:
            mid = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
            if mid:
                removals.append({"id": mid, "action": "remove"})
        summary_msg = {"role": "system", "content": summary_text}

    return {"messages": removals + [summary_msg]}


# ── Section 4: Tool-Output Compression ────────────────────────────────────────

def compress_tool_result(raw_result: str, query: str, max_tokens: int = 300) -> str:
    """Nén kết quả tool (bảng SQL/Docs) trước khi đưa vào context, chỉ nén khi quá dài.

    Giữ số liệu, tên riêng chính xác; bỏ các hàng/cột không liên quan tới query.
    """
    if not raw_result or len(raw_result) < max_tokens * _CHARS_PER_TOKEN:
        return raw_result

    system_prompt = "Bạn là chuyên gia trích xuất thông tin và nén bảng số liệu/tài liệu cho AI agent."
    user_prompt = (
        "Trích xuất thông tin liên quan trực tiếp đến câu hỏi từ kết quả thô sau. "
        "Giữ số liệu, tên riêng chính xác. Bỏ phần không liên quan.\n\n"
        f"Câu hỏi: {query}\n"
        f"Kết quả thô:\n{raw_result[:4000]}\n\n"
        "Thông tin liên quan (ngắn gọn, súc tích):"
    )

    try:
        if use_offline_tools():
            return raw_result[: max_tokens * _CHARS_PER_TOKEN] + "... [đã nén]"
        compressed = invoke_text(system_prompt, user_prompt, substep="tool_compress")
        return compressed.strip() if compressed else raw_result
    except Exception as exc:
        logger.warning("compress_tool_result LLM call failed: %s", exc)
        return raw_result[: max_tokens * _CHARS_PER_TOKEN] + "... [đã nén]"


# ── Section 5: Instruction Re-injection ────────────────────────────────────────

def reinject_instructions(messages: list[Any], instructions: str) -> list[Any]:
    """Tái chèn chỉ dẫn quan trọng ở CUỐI context chống instruction fade-out.

    Đặt lại quy tắc an toàn cốt lõi ở vị trí attention cao nhất trước khi gọi mô hình.
    """
    if not instructions or not instructions.strip():
        return list(messages)

    content_text = f"{REINJECT_PREFIX} {instructions.strip()}"
    first_msg = messages[0] if messages else None
    if first_msg and hasattr(first_msg, "__class__") and not isinstance(first_msg, dict):
        try:
            from langchain_core.messages import SystemMessage
            reinject_msg = SystemMessage(content=content_text)
        except Exception:
            reinject_msg = {"role": "system", "content": content_text}
    else:
        reinject_msg = {"role": "system", "content": content_text}

    return list(messages) + [reinject_msg]


# ── Section 6: Additional Agent Capabilities (Scan Query & Circuit Breaker) ────

def latest_human_query(messages: list[Any]) -> str:
    """Tìm nội dung tin nhắn user/human gần nhất làm query cho tool retrieval / memory recall.

    Giữa 1 vòng agent⇄tools, message cuối có thể là tool result (không phải câu hỏi)
    — quét ngược tìm đúng message role 'human' hoặc 'user', không chỉ lấy messages[-1].
    """
    for m in reversed(messages):
        if _role_of(m) in ("human", "user"):
            return _text_of(m)
    return ""


# Alias tương thích hoàn toàn với mẫu _latest_human_query trong llm-engineer-demo
_latest_human_query = latest_human_query


def detect_repetition(messages_or_state: Any, window: int = 4) -> bool:
    """Phát hiện agent lặp lại cùng 1 hành động/tool call liên tiếp (loop termination guard).

    Trả về True nếu `window` tool call gần nhất giống hệt nhau — dấu hiệu agent bị kẹt vòng lặp.
    """
    messages = messages_or_state
    if isinstance(messages_or_state, dict) and "messages" in messages_or_state:
        messages = messages_or_state["messages"]

    if not isinstance(messages, (list, tuple)):
        return False

    recent_calls: list[str] = []
    for m in messages[- (window * 3):]:
        calls = None
        if hasattr(m, "tool_calls") and getattr(m, "tool_calls"):
            calls = m.tool_calls
        elif isinstance(m, dict) and m.get("tool_calls"):
            calls = m.get("tool_calls")
        elif isinstance(m, dict) and m.get("role") == "tool":
            calls = [m.get("content", "")]

        if calls:
            recent_calls.append(str(calls[0]))

    if len(recent_calls) < window:
        return False

    target = recent_calls[-window:]
    return len(set(target)) == 1


# Alias tương thích hoàn toàn với mẫu _detect_repetition trong llm-engineer-demo
_detect_repetition = detect_repetition
