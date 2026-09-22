"""Unit tests for Phase 3b short-term memory checkpointer MVP."""
from __future__ import annotations

from src.agent.graph import Agent_Input, _get_graph, run_agent
from src.main import ChatRequest
from src.memory.shortterm import get_checkpointer


def test_get_checkpointer_singleton():
    """get_checkpointer trả về MemorySaver singleton."""
    cp1 = get_checkpointer()
    cp2 = get_checkpointer()
    assert cp1 is not None
    assert cp1 is cp2


def test_shortterm_checkpoint_invoke_twice_same_session():
    """Offline: invoke graph twice same session_id, assert checkpoint has 2+ messages (use graph.get_state(config))."""
    graph = _get_graph()
    session_id = "test-session-shortterm-invoke-twice"
    config = {"configurable": {"thread_id": session_id}}

    res1 = graph.invoke(
        {"question": "Hôm nay có bao nhiêu lượt xe vào?", "events": []},
        config=config,
    )
    assert "result" in res1
    state1 = graph.get_state(config)
    assert len(state1.values.get("messages", [])) >= 1

    res2 = graph.invoke(
        {"question": "Có bao nhiêu xe tải vào?", "events": []},
        config=config,
    )
    assert "result" in res2
    state2 = graph.get_state(config)
    messages = state2.values.get("messages", [])
    assert len(messages) >= 2


def test_run_agent_persists_messages_by_session_id():
    """Kiểm tra run_agent nhận session_id và lưu checkpoint messages qua get_state."""
    graph = _get_graph()
    session_id = "test-session-run-agent-shortterm"
    config = {"configurable": {"thread_id": session_id}}

    out1 = run_agent(
        Agent_Input(question="Hôm nay có bao nhiêu xe máy?"),
        session_id=session_id,
    )
    assert out1.answer.strip() != ""

    out2 = run_agent(
        Agent_Input(question="Có bao nhiêu xe buýt?"),
        session_id=session_id,
    )
    assert out2.answer.strip() != ""

    state = graph.get_state(config)
    messages = state.values.get("messages", [])
    assert len(messages) >= 2
    assert messages[0].content == "Hôm nay có bao nhiêu xe máy?"
    assert messages[1].content == "Có bao nhiêu xe buýt?"


def test_shortterm_memory_session_isolation():
    """Kiểm tra các session_id khác nhau không bị lẫn checkpoint messages."""
    graph = _get_graph()
    sess_a = "test-sess-isolated-a"
    sess_b = "test-sess-isolated-b"

    run_agent(Agent_Input(question="Câu hỏi A1"), session_id=sess_a)
    run_agent(Agent_Input(question="Câu hỏi A2"), session_id=sess_a)
    run_agent(Agent_Input(question="Câu hỏi B1"), session_id=sess_b)

    state_a = graph.get_state({"configurable": {"thread_id": sess_a}})
    state_b = graph.get_state({"configurable": {"thread_id": sess_b}})

    assert len(state_a.values.get("messages", [])) >= 2
    assert len(state_b.values.get("messages", [])) == 1


def test_chat_request_session_id_default():
    """ChatRequest có trường session_id tùy chọn với giá trị mặc định là 'default'."""
    req_default = ChatRequest(question="Thống kê xe")
    assert req_default.session_id == "default"

    req_custom = ChatRequest(question="Thống kê xe", session_id="custom-sess-123")
    assert req_custom.session_id == "custom-sess-123"
