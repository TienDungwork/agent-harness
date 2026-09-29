"""Unit tests for Context Engineering Engine (src/memory/context.py).

Kiểm thử toàn diện 5 trụ cột Context Engineering theo specs/test-plan.md:
1. Sliding Window (bảo tồn system message + giữ N message gần nhất).
2. Token Estimation & Context Usage.
3. Ngưỡng kích hoạt nén chủ động 40% (nguyên tắc 40-60%).
4. Summarization hội thoại cũ thành 1 system message mang tiền tố.
5. Tool-Output Compression (chỉ nén khi vượt ngưỡng, bỏ qua khi ngắn).
6. Instruction Re-injection ở cuối context.
7. Tương thích cả dict lẫn LangChain BaseMessage.
"""
from __future__ import annotations

from unittest.mock import patch
import pytest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.memory.context import (
    REINJECT_PREFIX,
    SUMMARY_PREFIX,
    compress_tool_result,
    context_usage,
    estimate_tokens,
    format_messages,
    reinject_instructions,
    should_compact,
    sliding_window,
    summarize_old_messages,
    summarize_text,
)


def test_sliding_window_preserves_system_and_recent():
    """Tạo 25 message (1 system + 24 turns). Sliding window max=10 trả về đúng 11 message."""
    messages = [{"role": "system", "content": "System prompt gốc VMS KCN"}]
    for i in range(1, 25):
        role = "user" if i % 2 != 0 else "assistant"
        messages.append({"role": role, "content": f"Turn {i} nội dung tin nhắn"})

    assert len(messages) == 25

    windowed = sliding_window(messages, max_messages=10)
    assert len(windowed) == 11
    # System message gốc được bảo tồn ở đầu
    assert windowed[0]["role"] == "system"
    assert "System prompt gốc" in windowed[0]["content"]
    # 10 message sau cùng là các turn mới nhất (15 đến 24)
    assert windowed[-1]["content"] == "Turn 24 nội dung tin nhắn"
    assert windowed[1]["content"] == "Turn 15 nội dung tin nhắn"


def test_sliding_window_short_history_unchanged():
    """Khi tổng số message nhỏ hơn max_messages, giữ nguyên danh sách."""
    messages = [
        {"role": "system", "content": "Prompt"},
        {"role": "user", "content": "Câu 1"},
        {"role": "assistant", "content": "Đáp 1"},
    ]
    windowed = sliding_window(messages, max_messages=10)
    assert len(windowed) == 3
    assert windowed == messages


def test_estimate_tokens_and_context_usage():
    """Ước lượng số token theo tỷ lệ 4 ký tự/token và đo tỷ lệ context_usage."""
    # 400 ký tự -> ~100 tokens
    messages = [
        {"role": "user", "content": "A" * 200},
        {"role": "assistant", "content": "B" * 200},
    ]
    tokens = estimate_tokens(messages)
    assert tokens == 100

    usage = context_usage(messages, window_tokens=1000)
    assert pytest.approx(usage, 0.001) == 0.1

    # Khi window_tokens <= 0
    assert context_usage(messages, window_tokens=0) == 0.0


def test_should_compact_activates_at_40_percent():
    """Kiểm tra điều kiện kích hoạt nén chủ động khi tỷ lệ vượt 40% window (nguyên tắc 40-60%)."""
    # 800 ký tự -> ~200 tokens
    messages = [
        {"role": "user", "content": "X" * 800},
    ]
    tokens = estimate_tokens(messages)
    assert tokens == 200

    # 200 tokens / 1000 window = 20% (< 40%) -> Không compact
    assert should_compact(messages, window_tokens=1000, threshold=0.40) is False

    # 200 tokens / 400 window = 50% (> 40%) -> Kích hoạt compact
    assert should_compact(messages, window_tokens=400, threshold=0.40) is True


def test_summarize_old_messages_creates_summary_message():
    """Tạo 15 message, summarize_old_messages(keep_recent=4) trả về 5 message với prefix chuẩn."""
    messages = [{"role": "system", "content": "Prompt VMS"}]
    for i in range(1, 15):
        messages.append({"role": "user", "content": f"Câu hỏi {i}"})

    assert len(messages) == 15

    with patch("src.memory.context.summarize_text", return_value="Tóm tắt các sự kiện an ninh từ lượt 1 đến 10."):
        compacted = summarize_old_messages(messages, keep_recent=4)
        assert len(compacted) == 5
        # Message đầu tiên là bản tóm tắt
        assert compacted[0]["role"] == "system"
        assert compacted[0]["content"].startswith(SUMMARY_PREFIX)
        assert "Tóm tắt các sự kiện an ninh" in compacted[0]["content"]
        # 4 message gần nhất được giữ nguyên
        assert compacted[-1]["content"] == "Câu hỏi 14"
        assert compacted[-4]["content"] == "Câu hỏi 11"


def test_summarize_old_messages_short_history_no_compact():
    """Nếu lịch sử ít hơn hoặc bằng keep_recent + 1, không thực hiện tóm tắt."""
    messages = [
        {"role": "system", "content": "Prompt"},
        {"role": "user", "content": "Câu 1"},
        {"role": "assistant", "content": "Đáp 1"},
    ]
    res = summarize_old_messages(messages, keep_recent=4)
    assert len(res) == 3
    assert res == messages


def test_compress_tool_result_skips_short_output():
    """Kết quả tool ngắn (< 300 token * 4 chars) giữ nguyên bản, không gọi LLM nén."""
    short_table = "| camera | count |\n| C01 | 15 |\n"
    with patch("src.memory.context.invoke_text") as mock_invoke:
        result = compress_tool_result(short_table, query="Số xe camera C01?", max_tokens=300)
        assert result == short_table
        assert not mock_invoke.called


def test_compress_tool_result_compresses_long_output():
    """Kết quả tool dài (> 300 token * 4 chars) kích hoạt nén và trả về kết quả tóm tắt."""
    long_raw_data = "Sự kiện chi tiết camera: " + ("ID: 15K, Loại xe: tải, Cổng: 1, Thời gian: 08:30;\n" * 60)
    assert len(long_raw_data) > 1200

    with patch("src.memory.context.invoke_text", return_value="Tổng hợp: 60 lượt xe tải qua Cổng 1 lúc 08:30."):
        with patch("src.memory.context.use_offline_tools", return_value=False):
            compressed = compress_tool_result(long_raw_data, query="Bao nhiêu xe tải qua cổng 1?", max_tokens=250)
            assert "Tổng hợp: 60 lượt xe tải" in compressed


def test_reinject_instructions_appends_to_end():
    """reinject_instructions chèn system message mang tiền tố [Nhắc lại chỉ dẫn] vào cuối danh sách."""
    messages = [
        {"role": "system", "content": "System prompt gốc"},
        {"role": "user", "content": "Tôi muốn kiểm tra camera"},
    ]
    instructions = "Chỉ truy vấn bảng read-only, tuyệt đối không suy đoán số liệu."

    reinjected = reinject_instructions(messages, instructions)
    assert len(reinjected) == 3
    last_msg = reinjected[-1]
    assert last_msg["role"] == "system"
    assert last_msg["content"].startswith(REINJECT_PREFIX)
    assert instructions in last_msg["content"]


def test_reinject_instructions_empty_instructions_passthrough():
    """Nếu instructions rỗng, trả về danh sách nguyên bản."""
    messages = [{"role": "user", "content": "Hello"}]
    assert reinject_instructions(messages, "") == messages
    assert reinject_instructions(messages, "   ") == messages


def test_langchain_base_messages_compatibility():
    """Xác nhận Context Engineering tương thích hoàn hảo với LangChain BaseMessage."""
    sys_m = SystemMessage(content="System prompt LangChain")
    human_m = HumanMessage(content="Hôm nay có bao nhiêu lượt xe?")
    ai_m = AIMessage(content="Có 150 lượt xe vào KCN.")

    msgs = [sys_m, human_m, ai_m]

    # format_messages
    text_repr = format_messages(msgs)
    assert "system: System prompt LangChain" in text_repr
    assert "human: Hôm nay có bao nhiêu lượt xe?" in text_repr
    assert "ai: Có 150 lượt xe vào KCN." in text_repr

    # estimate_tokens
    assert estimate_tokens(msgs) > 0

    # reinject_instructions
    re_msgs = reinject_instructions(msgs, "Không bịa số liệu")
    assert len(re_msgs) == 4
    assert isinstance(re_msgs[-1], SystemMessage)
    assert re_msgs[-1].content.startswith(REINJECT_PREFIX)


def test_latest_human_query_scans_backwards():
    """latest_human_query quét ngược qua các tool message để tìm câu hỏi user gần nhất."""
    from src.memory.context import latest_human_query, _latest_human_query

    messages = [
        {"role": "user", "content": "Câu hỏi đầu tiên"},
        {"role": "assistant", "content": "Trả lời câu đầu"},
        {"role": "user", "content": "Xe tải biển số 65A có vào không?"},
        {"role": "assistant", "content": "Để tôi kiểm tra SQL", "tool_calls": [{"name": "sql_query"}]},
        {"role": "tool", "content": "Kết quả: 1 bản ghi xe 65A"},
    ]
    query = latest_human_query(messages)
    assert query == "Xe tải biển số 65A có vào không?"
    # Alias
    assert _latest_human_query(messages) == query


def test_detect_repetition_detects_infinite_loop():
    """detect_repetition trả về True khi có window tool calls giống hệt nhau liên tiếp."""
    from src.memory.context import detect_repetition, _detect_repetition, REPETITION_WARNING

    # 4 tool calls giống nhau liên tiếp -> bị kẹt vòng lặp
    stuck_messages = [
        {"role": "user", "content": "Kiểm tra camera 1"},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c1"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c1"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c1"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c1"}]},
    ]
    assert detect_repetition(stuck_messages, window=4) is True
    assert _detect_repetition(stuck_messages, window=4) is True
    assert "lặp lại cùng 1 hành động" in REPETITION_WARNING

    # Các calls khác nhau -> False
    normal_messages = [
        {"role": "user", "content": "Kiểm tra camera 1"},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c1"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c2"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c3"}]},
        {"role": "assistant", "content": "Gọi tool", "tool_calls": [{"name": "check_cam", "id": "c4"}]},
    ]
    assert detect_repetition(normal_messages, window=4) is False


def test_create_compaction_diff_persists_to_state():
    """create_compaction_diff tạo danh sách RemoveMessage(id) và 1 summary message."""
    from src.memory.context import create_compaction_diff
    from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage

    msgs = [
        HumanMessage(content="Tin nhắn cũ 1", id="m-1"),
        AIMessage(content="Trả lời cũ 1", id="m-2"),
        HumanMessage(content="Tin nhắn cũ 2", id="m-3"),
        AIMessage(content="Trả lời cũ 2", id="m-4"),
        HumanMessage(content="Tin nhắn gần 1", id="m-5"),
        AIMessage(content="Trả lời gần 1", id="m-6"),
        HumanMessage(content="Tin nhắn gần 2", id="m-7"),
        AIMessage(content="Trả lời gần 2", id="m-8"),
    ]

    with patch("src.memory.context.use_offline_tools", return_value=True):
        diff = create_compaction_diff(msgs, keep_recent=4)
        assert "messages" in diff
        diff_msgs = diff["messages"]
        # 4 old messages -> 4 RemoveMessage + 1 SystemMessage (summary) = 5
        assert len(diff_msgs) == 5
        removals = [m for m in diff_msgs if isinstance(m, RemoveMessage)]
        assert len(removals) == 4
        assert [r.id for r in removals] == ["m-1", "m-2", "m-3", "m-4"]
        summary = diff_msgs[-1]
        assert isinstance(summary, SystemMessage)
        assert summary.content.startswith(SUMMARY_PREFIX)


def test_should_compact_route_conditional_edge():
    """should_compact_route trả về 'compact' nếu vượt 40% window, ngược lại 'continue'."""
    from src.memory.context import should_compact_route

    # Dưới ngưỡng
    short_msgs = [{"role": "user", "content": "A" * 100}]
    assert should_compact_route(short_msgs, window_tokens=1000, threshold=0.40) == "continue"

    # Vượt ngưỡng 40% (500 tokens / 1000 tokens = 50%)
    long_msgs = [{"role": "user", "content": "A" * 2000}]
    assert should_compact_route(long_msgs, window_tokens=1000, threshold=0.40) == "compact"
    # State dict input
    assert should_compact_route({"messages": long_msgs}, window_tokens=1000, threshold=0.40) == "compact"

