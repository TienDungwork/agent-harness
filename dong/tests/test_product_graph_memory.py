"""Unit tests for Phase 4: Graph Memory & Context Engineering integration (src/agent/graph.py)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.agent.graph import (
    Agent_Input,
    Agent_Output,
    _memory_context_block,
    extract_memory_node,
    recall_memory_node,
    recall_node,
    run_agent,
    run_agent_stream,
)
from src.agent.inline_respond import generate_inline_response
from src.memory import (
    clear_long_term,
    clear_ttl_cache,
    recall_long_term,
    save_to_long_term,
)
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture(autouse=True)
def clean_stores():
    clear_long_term()
    clear_ttl_cache()
    yield
    clear_long_term()
    clear_ttl_cache()


def test_recall_memory_node_alias_and_functionality():
    """recall_memory_node là alias hợp lệ của recall_node và truy vấn đúng fact."""
    assert recall_memory_node is recall_node

    save_to_long_term("u_graph_test", "Người dùng là kỹ sư trưởng ca sáng")
    state = {
        "user_id": "u_graph_test",
        "question": "Tôi làm nhiệm vụ gì?",
    }
    out = recall_memory_node(state)
    assert "recalled_memories" in out
    assert any("kỹ sư trưởng" in m for m in out["recalled_memories"])


def test_memory_context_block_formatting():
    """_memory_context_block định dạng chính xác tiền tố 'Thông tin đã biết về user:'."""
    state = {
        "recalled_memories": [
            "Tên người dùng là Tuấn",
            "Người dùng phụ trách camera cổng số 2",
        ]
    }
    block = _memory_context_block(state)
    assert "Thông tin đã biết về user:" in block
    assert "- Tên người dùng là Tuấn" in block
    assert "- Người dùng phụ trách camera cổng số 2" in block


def test_extract_memory_node_stores_facts_directly():
    """extract_memory_node trích xuất thông tin mới từ state và lưu vào bộ nhớ bền vững."""
    state = {
        "user_id": "u_extract_node",
        "question": "Tôi tên là Hoàng Minh, phụ trách trạm cân KCN Hưng Phú",
        "answer": "Chào bạn Hoàng Minh, tôi đã ghi nhận vai trò phụ trách trạm cân của bạn.",
        "respond_mode": "chat",
    }
    res = extract_memory_node(state)
    assert "extracted_memories" in res
    extracted = res["extracted_memories"]
    assert any("Hoàng Minh" in f for f in extracted)

    # Kiểm tra đã lưu bền vững
    saved_facts = recall_long_term("u_extract_node", "Hoàng Minh trạm cân")
    assert len(saved_facts) >= 1
    assert any("Hoàng Minh" in f for f in saved_facts)


def test_sliding_window_prunes_long_history(monkeypatch):
    """Lịch sử hội thoại dài trên 20 tin nhắn được sliding_window thu gọn an toàn."""
    from src.agent.graph import rewrite_node

    long_messages = [HumanMessage(content=f"Câu hỏi số {i}") for i in range(25)]
    state = {
        "question": "Hôm nay có bao nhiêu lượt xe tải?",
        "messages": long_messages,
    }
    out = rewrite_node(state)
    assert out["rewritten"] is not None


def test_compress_tool_result_applied_when_long(monkeypatch):
    """Khi kết quả tool/bảng SQL quá dài (> 1200 chars), compress_tool_result được gọi để nén."""
    from src.memory.context import compress_tool_result

    raw_table = "\n".join(f"camera_{i}=Cổng_{i}, so_luot={i*10}, loai_xe=TRUCK" for i in range(50))
    assert len(raw_table) > 1200

    compressed = compress_tool_result(raw_table, query="Số lượt xe tải", max_tokens=300)
    assert len(compressed) <= len(raw_table)
    assert "... [đã nén]" in compressed or len(compressed) < len(raw_table)


def test_inline_respond_answers_identity_with_memories():
    """Khi người dùng hỏi 'Tôi là ai?', trợ lý dùng thông tin memories để phản hồi lịch sự."""
    memories = [
        "Tên người dùng là Tuấn",
        "Người dùng phụ trách camera cổng số 2",
    ]
    resp = generate_inline_response("Tôi là ai?", intent="chat", memories=memories)
    assert "Tuấn" in resp
    assert "Theo thông tin tôi ghi nhận về bạn" in resp


def test_instruction_reinject_in_respond_prompt(monkeypatch):
    """Chỉ dẫn an toàn [Nhắc lại chỉ dẫn] được tái chèn vào prompt trước khi gọi LLM."""
    captured_sys: list[str] = []

    def mock_invoke(sys_prompt: str, user_prompt: str, **kwargs) -> str:
        captured_sys.append(sys_prompt)
        return "Kết quả truy vấn xe tải."

    monkeypatch.setattr("src.llm.client.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.llm.client.invoke_text", mock_invoke)
    monkeypatch.setattr("src.agent.generate_sql.invoke_text", mock_invoke)
    monkeypatch.setattr("src.agent.generate_sql.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.agent.execute_sql.use_offline_tools", lambda: False)
    monkeypatch.setattr(
        "src.agent.execute_sql.execute_sql",
        lambda sql, params=None: ([{"loai_xe": "TRUCK", "so_luot": 25}], ["loai_xe", "so_luot"]),
    )

    inp = Agent_Input(question="Hôm nay có bao nhiêu xe tải vào cổng?", user_id="u_reinject")
    out = run_agent(inp, session_id="sess_reinject")
    assert out.answer.strip() != ""
    assert captured_sys
    assert any("[Nhắc lại chỉ dẫn]:" in s for s in captured_sys)


def test_end_to_end_graph_memory_flow():
    """Kiểm tra trọn vẹn luồng Agent Graph với recall, respond và store_extract."""
    # Lượt 1: Giới thiệu danh tính
    inp1 = Agent_Input(
        question="Chào bạn, tôi tên là Minh, tôi quản lý camera cổng chính",
        user_id="u_e2e_dong",
    )
    out1 = run_agent(inp1, session_id="sess_e2e_1")
    assert out1.answer.strip() != ""

    import time
    time.sleep(0.3)

    # Kiểm tra long-term memory đã có fact
    facts = recall_long_term("u_e2e_dong", "Minh cổng chính")
    assert len(facts) >= 1
    assert any("Minh" in f for f in facts)

    # Lượt 2: Hỏi lại danh tính trong phiên mới
    inp2 = Agent_Input(question="Tôi là ai?", user_id="u_e2e_dong")
    out2 = run_agent(inp2, session_id="sess_e2e_2")
    assert "Minh" in out2.answer
