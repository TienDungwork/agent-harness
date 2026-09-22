"""Unit tests for Phase 3b: Node recall (đầu) + store/extract (cuối)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Input, _build_graph, run_agent, run_agent_stream
from src.main import app
from src.memory import (
    clear_long_term,
    clear_ttl_cache,
    extract_and_store_memory,
    extract_memories,
    recall_long_term,
    save_to_long_term,
)


@pytest.fixture(autouse=True)
def clean_stores():
    clear_long_term()
    clear_ttl_cache()
    yield
    clear_long_term()
    clear_ttl_cache()


def test_graph_has_recall_node_store_extract_post_pipeline():
    """Recall trong graph; store_extract chạy post-pipeline sau respond."""
    compiled = _build_graph()
    nodes = set(compiled.get_graph().nodes.keys())
    assert "recall" in nodes
    assert "store_extract" not in nodes
    assert "rewrite" in nodes
    assert "classify" in nodes


def test_heuristic_extract_patterns():
    """Kiểm tra trích xuất fact theo các mẫu phổ biến."""
    # Tên người dùng
    m1 = extract_memories("u1", "Xin chào, tôi tên là Hoàng")
    assert any("Tên người dùng là Hoàng" in f for f in m1)

    # Vai trò
    m2 = extract_memories("u1", "Tôi phụ trách camera trạm cân số 1")
    assert any("Người dùng phụ trách camera trạm cân số 1" in f for f in m2)

    # Sở thích
    m3 = extract_memories("u1", "Tôi thích xem biểu đồ hình tròn")
    assert any("Người dùng quan tâm xem biểu đồ hình tròn" in f for f in m3)

    # Ghi nhớ
    m4 = extract_memories("u1", "Nhớ là xe tải thường vào sau 18h")
    assert any("Ghi nhớ: xe tải thường vào sau 18h" in f for f in m4)

    # Rỗng
    assert extract_memories("", "Tôi tên là Nam") == []
    assert extract_memories("u1", "") == []


def test_extract_and_store_memory_persists():
    """extract_and_store_memory lưu fact trực tiếp vào long-term memory."""
    facts = extract_and_store_memory("u_vip", "Tôi phụ trách cổng chính số 1")
    assert len(facts) >= 1

    recalled = recall_long_term("u_vip", "cổng chính")
    assert len(recalled) >= 1
    assert "phụ trách" in recalled[0]


def test_online_extract_with_llm(monkeypatch):
    """Docs branch: extract gọi LLM với prompt memory_extract."""
    monkeypatch.setattr("src.memory.extract.use_offline_tools", lambda: False)

    mock_invoke = MagicMock(return_value="- Người dùng thường trực ban đêm tại Cổng A")
    monkeypatch.setattr("src.memory.extract.invoke_text", mock_invoke)

    facts = extract_memories(
        "u_test",
        "Hướng dẫn mở Quản Lý Camera",
        "Vào menu Cấu hình & Thiết bị.",
        detail="docs",
    )
    assert "Người dùng thường trực ban đêm tại Cổng A" in facts
    assert mock_invoke.call_count == 1


def test_stat_query_skips_answer_memory(monkeypatch):
    """Query thống kê: chỉ heuristic từ câu hỏi, không gọi LLM với số liệu trả lời."""
    monkeypatch.setattr("src.memory.extract.use_offline_tools", lambda: False)
    mock_invoke = MagicMock()
    monkeypatch.setattr("src.memory.extract.invoke_text", mock_invoke)

    facts = extract_memories(
        "u_test",
        "Tôi phụ trách cổng 1. Hôm nay có bao nhiêu xe vào?",
        "Hôm nay có 6816 lượt xe vào.",
        detail="query_data",
    )
    mock_invoke.assert_not_called()
    assert any("cổng 1" in f for f in facts)
    assert not any("6816" in f for f in facts)


def test_end_to_end_graph_recall_and_store():
    """End-to-end: turn 1 store fact, turn 2 recall fact cùng user_id khác session."""
    import time

    user_id = "user-engineer-1"

    # Turn 1: User cung cấp thông tin vai trò qua câu hỏi
    inp1 = Agent_Input(question="Tôi phụ trách khu vực trạm cân 1", user_id=user_id)
    out1 = run_agent(inp1, session_id="session-1")
    assert out1 is not None
    time.sleep(0.3)

    # Kiểm tra long-term store đã lưu fact
    stored = recall_long_term(user_id, "trạm cân 1")
    assert len(stored) >= 1
    assert "trạm cân 1" in stored[0]

    # Turn 2: Session hoàn toàn mới với cùng user_id
    inp2 = Agent_Input(question="Trạm cân 1 hôm nay thế nào?", user_id=user_id)
    out2 = run_agent(inp2, session_id="session-2")
    assert out2 is not None

    # User khác không recall được thông tin của user 1
    other_recalled = recall_long_term("user-other", "trạm cân 1")
    assert other_recalled == []


def test_stream_emits_recall_and_store_extract_events():
    """run_agent_stream: recall trong graph; store_extract sau __final_result__."""
    user_id = "user-stream-test"
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?", user_id=user_id)
    events = list(run_agent_stream(inp, session_id="stream-sess"))

    node_ids = [ev.get("node_id") for ev in events if ev.get("node_id")]
    assert "recall" in node_ids
    assert "store_extract" in node_ids

    # recall đến trước rewrite
    first_recall_idx = node_ids.index("recall")
    first_rewrite_idx = node_ids.index("rewrite")
    assert first_recall_idx < first_rewrite_idx

    # __final_result__ (→ UI answer) trước store_extract
    final_idx = next(i for i, ev in enumerate(events) if "__final_result__" in ev)
    store_idxs = [i for i, ev in enumerate(events) if ev.get("node_id") == "store_extract"]
    assert store_idxs
    assert final_idx < store_idxs[0]

    first_respond_idx = node_ids.index("respond")
    first_store_idx = node_ids.index("store_extract")
    assert first_respond_idx < first_store_idx

    store_done = next(
        ev for ev in events
        if ev.get("node_id") == "store_extract" and ev.get("status") == "done"
    )
    assert isinstance(store_done["input"], dict)
    assert isinstance(store_done["output"], dict)
    assert store_done["input"]["include_answer"] is False
    assert store_done["input"]["answer"] == ""
    assert "extracted_memories" in store_done["output"]


def test_orchestrator_multi_skips_answer_memory(monkeypatch):
    """Orchestrator multi: không gọi LLM với câu trả lời chứa số liệu thống kê."""
    monkeypatch.setattr("src.memory.extract.use_offline_tools", lambda: False)
    mock_invoke = MagicMock()
    monkeypatch.setattr("src.memory.extract.invoke_text", mock_invoke)

    facts = extract_memories(
        "u_test",
        "Tôi phụ trách cổng 2. Hôm nay có bao nhiêu xe và cho biết cách thêm camera?",
        "Về số liệu thống kê:\nHôm nay có 6816 lượt xe vào.",
        detail="orchestrator:multi",
    )
    mock_invoke.assert_not_called()
    assert any("cổng 2" in f for f in facts)
    assert not any("6816" in f for f in facts)


def test_recall_memories_injected_into_respond_prompt(monkeypatch):
    """Recalled long-term memories được chèn vào prompt respond_stat."""
    save_to_long_term("u_mem", "Người dùng phụ trách cổng số 2")
    captured: list[str] = []

    def fake_invoke(_system: str, user: str) -> str:
        captured.append(user)
        return "Trả lời có bối cảnh người dùng."

    monkeypatch.setattr("src.llm.client.invoke_text", fake_invoke)
    monkeypatch.setattr("src.llm.client.use_offline_tools", lambda: False)

    inp = Agent_Input(
        question="Hôm nay có bao nhiêu xe vào cổng số 2?",
        user_id="u_mem",
    )
    run_agent(inp, session_id="sess-recall-inject")

    assert captured
    assert any("Người dùng phụ trách cổng số 2" in c for c in captured)


def test_out_of_scope_still_runs_store_extract():
    """Nhánh out_of_scope vẫn chạy store_extract post-pipeline."""
    inp = Agent_Input(question="Thời tiết hôm nay thế nào?", user_id="u_oos")
    events = list(run_agent_stream(inp, session_id="oos-sess"))
    node_ids = [e.get("node_id") for e in events if e.get("node_id")]
    assert "out_of_scope" in node_ids
    assert "store_extract" in node_ids
    assert node_ids.index("store_extract") > node_ids.index("out_of_scope")


def test_api_chat_propagates_user_id_and_stores_memory():
    """Endpoint /api/chat nhận user_id và kích hoạt lưu memory."""
    client = TestClient(app)
    uid = "api-user-99"

    import time

    resp = client.post("/api/chat", json={
        "question": "Tôi phụ trách cổng số 2 KCN Hưng Phú",
        "session_id": "api-sess-1",
        "user_id": uid,
    })
    assert resp.status_code == 200
    time.sleep(0.3)

    # Long-term memory của uid phải có fact
    facts = recall_long_term(uid, "cổng số 2")
    assert len(facts) >= 1
    assert "cổng số 2" in facts[0]
