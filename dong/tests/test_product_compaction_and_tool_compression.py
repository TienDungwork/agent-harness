"""Comprehensive test suite for Context Compaction (40% threshold) and Tool Compression.

Tiêu chuẩn nghiệm thu:
- AC-6 (Active Compaction 40%): Khi dung lượng ngữ cảnh vượt ngưỡng 40% window, hệ thống tự động
  gom tin nhắn cũ thành 1 đoạn tóm tắt mang tiền tố `[Tóm tắt hội thoại trước]: ...`, giữ nguyên các
  tin nhắn gần nhất (keep_recent=6).
- AC-7 (Tool Output Compression): Kết quả SQL table hoặc Docs dài hơn 300 tokens (1200 ký tự)
  được nén cô đọng trước khi nạp vào context và sinh câu trả lời.
"""
from __future__ import annotations

from unittest.mock import patch
import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage

from src.memory.context import (
    SUMMARY_PREFIX,
    compress_tool_result,
    context_usage,
    create_compaction_diff,
    estimate_tokens,
    should_compact,
    should_compact_route,
    summarize_old_messages,
)
from src.agent.graph import AgentState, answer_from_docs_node, respond_node, rewrite_node
from src.llm.schemas import RewrittenQuestion


def test_should_compact_mathematical_threshold_40_percent():
    """Kiểm tra chính xác ngưỡng toán học 40% theo nguyên tắc 40-60%."""
    # 4000 tokens window: ngưỡng 40% là 1600 tokens
    window_tokens = 4000

    # 1. 1500 tokens (37.5% < 40%) -> Không compact
    msgs_under = [HumanMessage(content="A" * 6000)]  # 6000 chars / 4 = 1500 tokens
    assert estimate_tokens(msgs_under) == 1500
    assert pytest.approx(context_usage(msgs_under, window_tokens), 0.001) == 0.375
    assert should_compact(msgs_under, window_tokens=window_tokens, threshold=0.40) is False
    assert should_compact_route(msgs_under, window_tokens=window_tokens, threshold=0.40) == "continue"

    # 2. 1600 tokens (40.0% == 40%) -> Không compact (chỉ compact khi > 40%)
    msgs_exact = [HumanMessage(content="A" * 6400)]  # 6400 chars / 4 = 1600 tokens
    assert estimate_tokens(msgs_exact) == 1600
    assert should_compact(msgs_exact, window_tokens=window_tokens, threshold=0.40) is False

    # 3. 1700 tokens (42.5% > 40%) -> Kích hoạt compact
    msgs_over = [HumanMessage(content="A" * 6800)]  # 6800 chars / 4 = 1700 tokens
    assert estimate_tokens(msgs_over) == 1700
    assert pytest.approx(context_usage(msgs_over, window_tokens), 0.001) == 0.425
    assert should_compact(msgs_over, window_tokens=window_tokens, threshold=0.40) is True
    assert should_compact_route(msgs_over, window_tokens=window_tokens, threshold=0.40) == "compact"


def test_summarize_old_messages_generates_standard_prefix():
    """Hội thoại dài khi nén tự động sinh tiền tố [Tóm tắt hội thoại trước]: ... và giữ 6 turn gần nhất."""
    messages = [{"role": "system", "content": "System prompt ban đầu"}]
    for i in range(1, 15):
        role = "user" if i % 2 != 0 else "assistant"
        messages.append({"role": role, "content": f"Turn {i}: trao đổi về camera và an ninh"})

    assert len(messages) == 15

    with patch("src.memory.context.summarize_text", return_value="Người dùng đã hỏi về các camera cổng 1 và cổng 2."):
        compacted = summarize_old_messages(messages, keep_recent=6)
        # 1 summary + 6 recent = 7
        assert len(compacted) == 7
        summary_msg = compacted[0]
        assert summary_msg["role"] == "system"
        assert summary_msg["content"].startswith(SUMMARY_PREFIX)
        assert "Người dùng đã hỏi về các camera cổng 1 và cổng 2." in summary_msg["content"]
        # 6 tin nhắn gần nhất được giữ nguyên
        assert compacted[-1]["content"] == "Turn 14: trao đổi về camera và an ninh"
        assert compacted[-6]["content"] == "Turn 9: trao đổi về camera và an ninh"


def test_create_compaction_diff_persists_to_state():
    """create_compaction_diff tạo danh sách RemoveMessage(id) cho tin nhắn cũ và 1 SystemMessage tóm tắt."""
    messages = [
        HumanMessage(content="Câu hỏi 1", id="msg-01"),
        AIMessage(content="Trả lời 1", id="msg-02"),
        HumanMessage(content="Câu hỏi 2", id="msg-03"),
        AIMessage(content="Trả lời 2", id="msg-04"),
        HumanMessage(content="Câu hỏi 3", id="msg-05"),
        AIMessage(content="Trả lời 3", id="msg-06"),
        HumanMessage(content="Câu hỏi 4", id="msg-07"),
        AIMessage(content="Trả lời 4", id="msg-08"),
        HumanMessage(content="Câu hỏi 5 (mới nhất)", id="msg-09"),
        AIMessage(content="Trả lời 5 (mới nhất)", id="msg-10"),
    ]

    with patch("src.memory.context.summarize_text", return_value="Các lượt trao đổi đầu tiên về camera"):
        diff = create_compaction_diff(messages, keep_recent=6)
        assert "messages" in diff
        diff_msgs = diff["messages"]
        # 10 - 6 = 4 tin nhắn cũ bị xóa -> 4 RemoveMessage + 1 SystemMessage = 5
        assert len(diff_msgs) == 5
        removals = [m for m in diff_msgs if isinstance(m, RemoveMessage)]
        assert len(removals) == 4
        assert [r.id for r in removals] == ["msg-01", "msg-02", "msg-03", "msg-04"]
        summary = diff_msgs[-1]
        assert isinstance(summary, SystemMessage)
        assert summary.content.startswith(SUMMARY_PREFIX)
        assert "Các lượt trao đổi đầu tiên về camera" in summary.content


def test_rewrite_node_triggers_compaction_when_exceeding_40_percent():
    """Node rewrite_node trong LangGraph tự động phát hiện ngữ cảnh vượt 40% window và kích hoạt nén diff."""
    # Tạo 10 tin nhắn dài (mỗi tin nhắn 800 ký tự -> ~2000 tokens tổng > 40% của 4000 window)
    long_history = []
    for i in range(1, 11):
        mid = f"hist-{i:02d}"
        if i % 2 != 0:
            long_history.append(HumanMessage(content=f"Chi tiết câu hỏi dài {i}: " + ("x" * 700), id=mid))
        else:
            long_history.append(AIMessage(content=f"Chi tiết câu trả lời dài {i}: " + ("y" * 700), id=mid))

    state: AgentState = {
        "question": "Hôm nay có sự kiện gì mới?",
        "user_id": "test_user",
        "session_id": "test_session",
        "messages": long_history,
    }

    with patch("src.memory.context.use_offline_tools", return_value=True):
        out = rewrite_node(state)
        messages_out = out["messages"]
        # Phải chứa các RemoveMessage, 1 SystemMessage tóm tắt, và cuối cùng là HumanMessage của lượt hiện tại
        has_removals = any(isinstance(m, RemoveMessage) for m in messages_out)
        has_summary = any(
            isinstance(m, SystemMessage) and m.content.startswith(SUMMARY_PREFIX)
            for m in messages_out
        )
        assert has_removals, "Phải có RemoveMessage để xóa tin nhắn cũ khỏi state"
        assert has_summary, f"Phải có SystemMessage mang tiền tố {SUMMARY_PREFIX}"
        assert isinstance(messages_out[-1], HumanMessage)
        assert messages_out[-1].content == "Hôm nay có sự kiện gì mới?"


def test_compress_tool_result_skips_short_output():
    """Bảng kết quả SQL ngắn (< 300 token tức < 1200 ký tự) không bị nén, giữ nguyên bản 100%."""
    short_table = (
        "Kết quả (2 dòng):\n"
        "camera_id=CAM_01, total_vehicles=12, time=08:00\n"
        "camera_id=CAM_02, total_vehicles=15, time=08:15\n"
    )
    with patch("src.memory.context.invoke_text") as mock_llm:
        compressed = compress_tool_result(short_table, query="Thống kê xe theo camera", max_tokens=300)
        assert compressed == short_table
        assert not mock_llm.called


def test_compress_tool_result_compresses_large_table():
    """Bảng kết quả SQL dài (> 300 token tức > 1200 ký tự) được nén cô đọng."""
    # Tạo bảng SQL gồm 50 dòng kết quả (> 3000 ký tự)
    rows = [f"camera=CAM_{i:02d}, license_plate=65A-{1000+i}, speed={40+i%20}km/h, status=normal" for i in range(50)]
    large_table = f"Kết quả ({len(rows)} dòng):\n" + "\n".join(rows)
    assert len(large_table) > 1200

    # 1. Chế độ offline fallback
    with patch("src.memory.context.use_offline_tools", return_value=True):
        offline_compressed = compress_tool_result(large_table, query="Bao nhiêu xe vượt tốc độ?", max_tokens=300)
        assert "[đã nén]" in offline_compressed
        assert len(offline_compressed) <= 300 * 4 + 50

    # 2. Chế độ LLM nén thông minh
    mock_llm_summary = "Tổng hợp: 50 lượt xe di chuyển tốc độ 40-59 km/h, không có vi phạm tốc độ."
    with patch("src.memory.context.use_offline_tools", return_value=False):
        with patch("src.memory.context.invoke_text", return_value=mock_llm_summary):
            llm_compressed = compress_tool_result(large_table, query="Bao nhiêu xe vượt tốc độ?", max_tokens=300)
            assert llm_compressed == mock_llm_summary


def test_sql_respond_node_compresses_large_sql_table():
    """respond_node tự động nén kết quả bảng SQL lớn (> 300 tokens) trước khi sinh câu trả lời."""
    # Tạo 40 rows dữ liệu SQL
    columns = ["id", "license_plate", "camera_id", "timestamp", "vehicle_type", "speed"]
    rows = [
        {
            "id": i,
            "license_plate": f"65A-{1000+i}",
            "camera_id": f"CAM_{i%5+1:02d}",
            "timestamp": "2026-09-28T08:30:00",
            "vehicle_type": "truck",
            "speed": 45,
        }
        for i in range(40)
    ]

    state: AgentState = {
        "question": "Danh sách xe tải qua các camera",
        "original_question": "Danh sách xe tải qua các camera",
        "rewritten": RewrittenQuestion(text="Danh sách xe tải qua các camera", intent_hint="query_data"),
        "intent": "query_data",
        "rows": rows,
        "columns": columns,
        "user_id": "test_guard",
        "session_id": "test_sess",
    }

    with patch("src.llm.client.use_offline_tools", return_value=True):
        out = respond_node(state)
        ans = out.get("answer", "")
        # Phải kích hoạt nén do bảng SQL vượt quá 300 tokens
        assert "[đã nén]" in ans or len(ans) < len(str(rows))


def test_docs_node_compresses_large_docs_answer():
    """answer_from_docs_node tự động nén nội dung tài liệu nếu câu trả lời vượt 300 tokens."""
    long_docs_text = "Quy trình kiểm soát an ninh cảng và cổng KCN:\n" + ("Mục điều khoản an ninh chi tiết;\n" * 50)
    assert len(long_docs_text) > 1200

    from src.llm.schemas import DocsAnswer

    mock_docs_answer = DocsAnswer(
        answer_vi=long_docs_text,
        card_ids=["card_01"],
    )

    state: AgentState = {
        "question": "Quy trình an ninh cổng?",
        "rows": [{"id": "card_01", "title": "An ninh cổng"}],
        "user_id": "test_user",
        "session_id": "test_sess",
    }

    with patch("src.knowledge.answer_from_docs", return_value=mock_docs_answer):
        with patch("src.memory.context.use_offline_tools", return_value=True):
            out = answer_from_docs_node(state)
            ans = out.get("answer", "")
            assert "[đã nén]" in ans
            assert out["docs_answer"]["answer_vi"] == ans
