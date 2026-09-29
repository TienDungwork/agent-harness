"""Unit tests for Fact Extraction (src/memory/extract.py).

Kiểm thử:
1. Regex tiếng Việt trích xuất Tên, Vai trò, Camera, Sở thích, Ghi nhớ
2. Lọc bỏ các từ nghi vấn trong câu hỏi (ai, gì, sao...)
3. Bỏ qua các số liệu thống kê realtime tạm thời (query_data)
4. Tích hợp LLM extraction với prompt memory_extract khi online
5. Trích xuất trực tiếp từ danh sách tin nhắn hội thoại (extract_from_messages)
6. Lưu trữ tự động vào PostgreSQL qua extract_and_store_memory
7. An toàn tuyệt đối (Graceful degradation): input rỗng hoặc lỗi không gây crash
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.memory.extract import (
    _heuristic_extract,
    extract_and_store_memory,
    extract_from_messages,
    extract_memories,
    memory_detail_includes_answer,
)
from src.memory.longterm import clear_long_term, recall_long_term


@pytest.fixture(autouse=True)
def clean_memory():
    """Tự động dọn dẹp long-term memory trước và sau mỗi ca test."""
    clear_long_term()
    yield
    clear_long_term()


def test_heuristic_extract_name():
    """Trích xuất tên người dùng qua nhiều dạng mẫu câu tiếng Việt."""
    assert _heuristic_extract("Xin chào, tôi tên là Tuấn Anh") == ["Tên người dùng là Tuấn Anh"]
    assert _heuristic_extract("Tên tôi là Hoàng Minh.") == ["Tên người dùng là Hoàng Minh"]
    assert _heuristic_extract("Mình tên là Thanh Trúc, phụ trách ca sáng") == [
        "Tên người dùng là Thanh Trúc",
        "Người dùng phụ trách ca sáng",
    ]


def test_heuristic_extract_role_and_camera():
    """Trích xuất vai trò và camera theo dõi."""
    facts = _heuristic_extract("Tôi phụ trách camera trạm cân số 1")
    assert any("trạm cân số 1" in f for f in facts)

    facts_cam = _heuristic_extract("Tôi theo dõi camera Cổng 2 và Cổng 3")
    assert any("Cổng 2 và Cổng 3" in f for f in facts_cam)


def test_heuristic_extract_preference_and_note():
    """Trích xuất sở thích và lưu ý cần ghi nhớ."""
    facts = _heuristic_extract("Tôi thích xem biểu đồ hình tròn. Nhớ là xe bồn vào sau 18h nhé.")
    assert any("biểu đồ hình tròn" in f for f in facts)
    assert any("xe bồn vào sau 18h" in f for f in facts)


def test_heuristic_extract_ignores_question_words():
    """Không trích xuất nhầm các câu hỏi truy vấn của người dùng."""
    assert _heuristic_extract("Tôi là ai?") == []
    assert _heuristic_extract("Tôi tên là gì?") == []
    assert _heuristic_extract("Ai phụ trách camera cổng 1?") == []


def test_memory_detail_includes_answer_filtering():
    """Chỉ cho phép trích xuất answer từ docs; bỏ qua query_data và out_of_scope."""
    assert memory_detail_includes_answer("docs") is True
    assert memory_detail_includes_answer("query_data") is False
    assert memory_detail_includes_answer("out_of_scope") is False
    assert memory_detail_includes_answer("orchestrator_multi") is False
    assert memory_detail_includes_answer("") is False


def test_extract_memories_skips_realtime_traffic_stats():
    """Câu hỏi thống kê lượt xe: Tuyệt đối không lưu số liệu 150 xe vào long-term memory."""
    facts = extract_memories(
        user_id="u_test_stat",
        question="Hôm nay có bao nhiêu lượt xe vào KCN?",
        answer="Hệ thống ghi nhận có 150 lượt xe tải và 45 lượt xe con.",
        detail="query_data",
    )
    # Không có fact nào chứa con số thống kê tạm thời
    assert facts == []
    assert not any("150" in f for f in facts)


def test_extract_memories_online_with_llm(monkeypatch):
    """Khi online và detail=docs: gọi LLM trích xuất thông tin hữu ích."""
    monkeypatch.setattr("src.memory.extract.use_offline_tools", lambda: False)
    mock_invoke = MagicMock(return_value="- Người dùng phụ trách quản lý camera kho A\n- Lưu ý ca trực từ 6h-14h")
    monkeypatch.setattr("src.memory.extract.invoke_text", mock_invoke)

    facts = extract_memories(
        user_id="u_online",
        question="Tài liệu camera kho A ở đâu?",
        answer="Xem tài liệu quy trình vận hành kho A.",
        detail="docs",
    )
    assert mock_invoke.call_count == 1
    assert "Người dùng phụ trách quản lý camera kho A" in facts
    assert "Lưu ý ca trực từ 6h-14h" in facts


def test_extract_from_messages_scans_history():
    """Trích xuất fact từ danh sách tin nhắn LangChain / dict."""
    messages = [
        {"role": "system", "content": "System prompt"},
        HumanMessage(content="Chào bạn, tôi tên là Đăng Khoa, phụ trách an ninh cổng 1"),
        AIMessage(content="Chào anh Đăng Khoa, tôi có thể giúp gì cho anh?"),
    ]
    facts = extract_from_messages("u_msg_test", messages)
    assert any("Đăng Khoa" in f for f in facts)
    assert any("cổng 1" in f for f in facts)


def test_extract_and_store_memory_persists_to_db():
    """extract_and_store_memory trích xuất và lưu ngay vào long-term store."""
    facts = extract_and_store_memory("u_persist", "Tôi tên là Quốc Hưng, tôi phụ trách trạm biến áp")
    assert len(facts) >= 2

    # Kiểm tra recall lại fact từ long-term
    recalled = recall_long_term("u_persist", "ai phụ trách trạm biến áp?")
    assert len(recalled) >= 1
    assert any("trạm biến áp" in r for r in recalled)


def test_extract_memories_empty_or_whitespace_noop():
    """Đầu vào rỗng hoặc whitespace không gây lỗi, trả về danh sách rỗng."""
    assert extract_memories("", "Tôi tên là Nam") == []
    assert extract_memories("   ", "Tôi tên là Nam") == []
    assert extract_memories("u1", "") == []
    assert extract_memories("u1", "   ") == []
    assert extract_from_messages("u1", []) == []
