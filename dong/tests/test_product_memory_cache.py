"""Product test suite for Memory & Cache: Short-term session memory, Long-term summarization, Memory nodes, TTL caching, Graceful degradation."""
from __future__ import annotations

# ==============================================================================
# --- Sourced from test_memory_shortterm.py ---
# ==============================================================================

"""Unit tests for Phase 3b short-term memory checkpointer MVP."""

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

# ==============================================================================
# --- Sourced from test_memory_longterm.py ---
# ==============================================================================

"""Unit tests for Phase 3b long-term memory store by user_id."""

import pytest

from src.memory import clear_long_term, recall_long_term, save_to_long_term


@pytest.fixture(autouse=True)
def clean_store():
    """Ensure in-memory long-term store is clean before and after each test."""
    clear_long_term()
    yield
    clear_long_term()


def test_save_and_recall_long_term_fact():
    """Save fact for user 'u1', recall with related query returns fact."""
    fact = "Người dùng ưu tiên theo dõi số lượng xe tải vào cổng chính"
    save_to_long_term("u1", fact)

    results = recall_long_term("u1", "xe tải cổng chính", k=3)
    assert len(results) >= 1
    assert results[0] == fact


def test_same_user_different_sessions_concept():
    """Same user_id, different session concept: recall still works (no session_id in longterm API)."""
    # Session 1: user configures a preference
    session_1_id = "session-login-day-1"  # simulated session concept
    save_to_long_term("u1", "Người dùng thích biểu đồ hình tròn khi xem tỷ lệ xe")

    # Session 2: new conversation session, same user
    session_2_id = "session-login-day-2"  # simulated another session concept
    recalled = recall_long_term("u1", "biểu đồ hình tròn")

    assert len(recalled) == 1
    assert "biểu đồ hình tròn" in recalled[0]


def test_user_isolation_u2_does_not_see_u1_facts():
    """User 'u2' does NOT see u1 facts."""
    save_to_long_term("u1", "Ghi chú bảo mật riêng của u1: trạm cân số 2")
    save_to_long_term("u2", "Ghi chú riêng của u2: cổng số 4")

    # u2 tries to query terms from u1's note
    u2_results = recall_long_term("u2", "bảo mật trạm cân số 2")
    for r in u2_results:
        assert "u1" not in r
        assert "trạm cân số 2" not in r

    # u1 tries to query terms from u2's note
    u1_results = recall_long_term("u1", "cổng số 4")
    for r in u1_results:
        assert "u2" not in r
        assert "cổng số 4" not in r


def test_empty_user_id_noop_or_empty():
    """Empty user_id -> save/recall no-op or empty list."""
    save_to_long_term("", "Dữ liệu không có user")
    save_to_long_term("   ", "Dữ liệu khoảng trắng user")

    assert recall_long_term("", "Dữ liệu") == []
    assert recall_long_term("   ", "Dữ liệu") == []


def test_empty_or_whitespace_fact_noop():
    """Empty or whitespace fact is skipped."""
    save_to_long_term("u1", "")
    save_to_long_term("u1", "   ")
    assert recall_long_term("u1", "anything") == []


def test_keyword_overlap_ranking():
    """Facts with higher keyword overlap with the query rank higher."""
    save_to_long_term("u1", "Cảnh báo hàng rào ảo khu vực kho A")
    save_to_long_term("u1", "Cảnh báo cháy nổ và khói tại bãi đỗ xe")

    # Query relates specifically to fire/smoke at parking
    results = recall_long_term("u1", "cháy nổ bãi đỗ xe", k=2)
    assert len(results) == 2
    assert "cháy nổ" in results[0]

# ==============================================================================
# --- Sourced from test_memory_nodes.py ---
# ==============================================================================

"""Unit tests for Phase 3b: Node recall (đầu) + store/extract (cuối)."""

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

    def fake_invoke(_system: str, user: str, max_tokens: int | None = None, **kwargs) -> str:
        if "sql" in _system.lower() or "select" in _system.lower():
            return "```sql\nSELECT camera_name, count(*) AS so_luot FROM plate_event GROUP BY camera_name\n```"
        captured.append(user)
        return "Trả lời có bối cảnh người dùng."

    monkeypatch.setattr("src.llm.client.invoke_text", fake_invoke)
    monkeypatch.setattr("src.llm.client.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.agent.generate_sql.invoke_text", fake_invoke)
    monkeypatch.setattr("src.agent.generate_sql.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.agent.execute_sql.use_offline_tools", lambda: False)
    monkeypatch.setattr("src.agent.execute_sql.execute_sql", lambda sql, params=None: [
        {"camera_name": "Cổng 2", "so_luot": 10},
        {"camera_name": "Cổng 1", "so_luot": 20},
    ])

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
    assert "respond_inline" in node_ids
    assert "guardrail_output" in node_ids
    assert "store_extract" in node_ids
    assert "respond" in node_ids
    assert node_ids.index("respond") > node_ids.index("respond_inline")
    assert node_ids.index("guardrail_output") > node_ids.index("respond")
    assert node_ids.index("store_extract") > node_ids.index("guardrail_output")


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

# ==============================================================================
# --- Sourced from test_memory_ttl_cache.py ---
# ==============================================================================

"""Unit tests for Phase 3b: TTL Response Cache 300s."""


import time
import pytest

from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
    _ttl_cache,
)


def test_make_cache_key_normalization_and_different_routes():
    """make_cache_key normalizes question and generates different keys for different routes."""
    k1 = make_cache_key("  Hôm Nay Có Bao Nhiêu Xe Vào?  ")
    k2 = make_cache_key("hôm nay có bao nhiêu xe vào?")
    assert k1 == k2

    k_stat = make_cache_key("hôm nay có bao nhiêu xe vào?", route="query_data")
    k_docs = make_cache_key("hôm nay có bao nhiêu xe vào?", route="docs")
    assert k_stat != k_docs
    assert k1 != k_stat
    assert k1 != k_docs


def test_ttl_cache_hit_within_300s(monkeypatch):
    """Entry stored in TTL cache hits successfully within 300s duration."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    payload = {"question": "Hôm nay có bao nhiêu xe vào?", "answer": "Có 150 xe", "row_count": 1}
    set_ttl_cached(key, payload)

    # Fast forward to 299s (within 300s)
    current_time = 1299.0
    cached = get_ttl_cached(key)
    assert cached is not None
    assert cached["answer"] == "Có 150 xe"
    assert cached["row_count"] == 1


def test_ttl_cache_miss_after_expire(monkeypatch):
    """Entry expires after 300s and get_ttl_cached returns None and cleans up."""
    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    payload = {"answer": "Có 150 xe"}
    set_ttl_cached(key, payload)

    assert get_ttl_cached(key) is not None

    # Advance past 300s
    current_time = 1301.0
    cached = get_ttl_cached(key)
    assert cached is None


def test_ttl_cache_disabled_cache_enabled_false(monkeypatch):
    """When CACHE_ENABLED is false, cache operations are disabled."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", False)

    key = make_cache_key("Hôm nay có bao nhiêu xe vào?")
    set_ttl_cached(key, {"answer": "test"})
    assert get_ttl_cached(key) is None


def test_ttl_cache_disabled_when_memory_ttl_zero_or_negative(monkeypatch):
    """When memory_ttl_seconds <= 0, cache returns None and does not store."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 0)

    key = make_cache_key("test zero ttl")
    set_ttl_cached(key, {"answer": "val"})
    assert get_ttl_cached(key) is None


def test_ttl_cache_same_question_hits_before_graph_with_stored_route(monkeypatch):
    """When stored with route after graph, checking before graph (without route) hits cache."""
    current_time = 5000.0
    monkeypatch.setattr(time, "time", lambda: current_time)
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    clear_ttl_cache()
    question = "Thống kê xe IN hôm nay"
    # Stored after graph with route="query_data"
    store_key = make_cache_key(question, route="query_data")
    data = {"question": question, "answer": "Tổng cộng 20 xe vào.", "tool": "query_traffic"}
    set_ttl_cached(store_key, data)

    # Hit before graph with make_cache_key(question) (no route)
    check_key = make_cache_key(question)
    cached = get_ttl_cached(check_key)
    assert cached is not None
    assert cached["answer"] == "Tổng cộng 20 xe vào."


def test_ttl_cache_clear():
    """clear_ttl_cache removes all entries from the store."""
    clear_ttl_cache()
    set_ttl_cached(make_cache_key("q1"), {"answer": "1"})
    set_ttl_cached(make_cache_key("q2"), {"answer": "2"})
    assert len(_ttl_cache) >= 2

    clear_ttl_cache()
    assert len(_ttl_cache) == 0
    assert get_ttl_cached(make_cache_key("q1")) is None
    assert get_ttl_cached(make_cache_key("q2")) is None


def test_ttl_cache_disabled_via_ttl_cache_enabled_property(monkeypatch):
    """Setting ttl_cache_enabled=False disables cache retrieval and setting."""
    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.ttl_cache_enabled", False)

    key = make_cache_key("test question")
    set_ttl_cached(key, {"answer": "cached"})
    assert get_ttl_cached(key) is None


def test_chat_cache_hit_before_graph(monkeypatch):
    """Chat endpoint hits TTL cache before graph execution and sets cache_hit=True."""
    from unittest.mock import MagicMock
    from src.main import chat, ChatRequest

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    # Pre-populate cache (simulating prior graph run with route)
    q = "Hôm nay có bao nhiêu lượt xe vào?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Hôm nay có 150 lượt xe vào.",
        "tool": "query_traffic",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_run = MagicMock()
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = chat(ChatRequest(question=q))
    assert mock_run.call_count == 0
    assert resp.answer == "Hôm nay có 150 lượt xe vào."
    assert resp.detail.get("cache_hit") is True


def test_cache_hit_skips_rewrite_when_llm_fails(monkeypatch):
    """TTL hit trước rewrite — LLM lỗi vẫn trả 200, không 503."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from src.main import app, chat, ChatRequest

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào?"
    set_ttl_cached(make_cache_key(q, route="query_data"), {
        "question": q,
        "answer": "Hôm nay có 100 lượt xe vào.",
        "tool": "sql_builder",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    def boom(*_args, **_kwargs):
        raise TimeoutError("LLM gateway timeout")

    monkeypatch.setattr("src.agent.rewrite.rewrite_question", boom)
    mock_run = MagicMock()
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = chat(ChatRequest(question=q))
    assert mock_run.call_count == 0
    assert resp.answer == "Hôm nay có 100 lượt xe vào."
    assert resp.detail.get("cache_hit") is True

    client = TestClient(app)
    stream_res = client.post("/api/agent/stream", json={"question": q})
    assert stream_res.status_code == 200
    assert '"node_id": "cache"' in stream_res.text
    assert mock_run.call_count == 0


def test_stream_agent_cache_hit_before_graph(monkeypatch):
    """Stream endpoint hits TTL cache before graph execution and yields cache node."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from src.main import app

    clear_ttl_cache()
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Tổng cộng 200 lượt xe.",
        "tool": "query_traffic",
        "columns": ["total"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_stream = MagicMock()
    monkeypatch.setattr("src.agent.graph.run_agent_stream", mock_stream)

    client = TestClient(app)
    res = client.post("/api/agent/stream", json={"question": q})
    assert res.status_code == 200
    body = res.text

    assert mock_stream.call_count == 0
    assert '"node_id": "cache"' in body
    assert '"cache_hit": true' in body
    assert "Tổng cộng 200 lượt xe." in body

# ==============================================================================
# --- Sourced from test_phase5_ttl_memory_degrade.py ---
# ==============================================================================

"""Phase 5: TTL / memory fail — degrade an toàn (vẫn trả lời được).

Tests:
- TTL get raises -> _lookup_ttl_cache returns None; /api/chat still 200 when agent mocked OK.
- TTL set raises -> response still returned with answer.
- recall_long_term raises -> recall_node returns empty memories, no exception.
- extract_and_store_memory raises -> run_store_extract returns done event with degraded output, no raise.
- Integration: stream with recall fail + agent OK -> __answer__ status done (not error); store_extract degraded OK.
"""


import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Input, Agent_Output, recall_node, run_agent_stream, run_store_extract
from src.llm.schemas import QueryResult
from src.main import app, _lookup_ttl_cache
from src.memory.ttl_cache import (
    clear_ttl_cache,
    get_ttl_cached,
    make_cache_key,
    set_ttl_cached,
    _ttl_cache,
)
from src.memory.longterm import clear_long_term, recall_long_term, save_to_long_term

client = TestClient(app)


class _FailingLock:
    def __enter__(self):
        raise RuntimeError("Lock error")

    def __exit__(self, *args):
        pass


class _FailingList:
    def append(self, item):
        raise RuntimeError("Store list append failure")


@pytest.fixture(autouse=True)
def reset_stores():
    clear_ttl_cache()
    clear_long_term()
    yield
    clear_ttl_cache()
    clear_long_term()


def test_ttl_get_raises_lookup_returns_none():
    """TTL get raises -> _lookup_ttl_cache returns None (cache miss), no exception."""
    with patch("src.main.get_ttl_cached", side_effect=RuntimeError("Corrupt TTL cache state")):
        cached = _lookup_ttl_cache("Hôm nay có bao nhiêu lượt xe?")
        assert cached is None


def test_get_ttl_cached_internal_error_returns_none(monkeypatch):
    """get_ttl_cached handles internal errors gracefully, returning None."""
    monkeypatch.setattr("src.memory.ttl_cache._ttl_lock", _FailingLock())
    val = get_ttl_cached("any_key")
    assert val is None


def test_get_ttl_cached_corrupted_entry_shape_returns_none():
    """Corrupted entry in _ttl_cache does not crash get_ttl_cached."""
    key = make_cache_key("Câu hỏi kiểm tra corrupt")
    # Store invalid entry shape
    _ttl_cache[key] = "not a dict"  # type: ignore[assignment]
    assert get_ttl_cached(key) is None

    _ttl_cache[key] = {"expire_at": "invalid_time", "data": "foo"}  # type: ignore[dict-item]
    assert get_ttl_cached(key) is None


def test_ttl_get_fails_chat_still_200_when_agent_ok(monkeypatch):
    """TTL get fails -> /api/chat proceeds to agent and returns 200 with answer."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Hôm nay có bao nhiêu xe vào?",
        answer="Hôm nay có 120 xe vào cổng.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[120]], row_count=1),
        detail="query_data",
    )

    with patch("src.main.get_ttl_cached", side_effect=RuntimeError("Cache connection lost")), \
         patch("src.main.run_agent", return_value=mock_output):
        res = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu xe vào?"})

    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "Hôm nay có 120 xe vào cổng."
    assert data["row_count"] == 1


def test_ttl_set_raises_chat_and_ask_still_return_answer(monkeypatch):
    """TTL set raises -> /api/chat and /ask still return answers successfully."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Hôm nay có bao nhiêu xe vào?",
        answer="Tổng số 150 xe.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[150]], row_count=1),
        detail="query_data",
    )

    with patch("src.main.set_ttl_cached", side_effect=RuntimeError("Disk full / Cache write failed")), \
         patch("src.main.run_agent", return_value=mock_output):
        # /api/chat
        res_chat = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu xe vào?"})
        assert res_chat.status_code == 200
        assert res_chat.json()["answer"] == "Tổng số 150 xe."

        # /ask
        res_ask = client.post("/ask", json={"question": "Hôm nay có bao nhiêu xe vào?"})
        assert res_ask.status_code == 200
        assert res_ask.json()["answer"] == "Tổng số 150 xe."


def test_ttl_set_raises_in_stream_still_returns_answer(monkeypatch):
    """TTL set raises in /api/agent/stream -> SSE stream completes with __answer__ done."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    mock_output = Agent_Output(
        question="Bao nhiêu xe hôm nay?",
        answer="Có 200 xe vào.",
        query=QueryResult(tool="query_traffic", columns=["total"], rows=[[200]], row_count=1),
        detail="query_data",
    )

    def fake_stream(*_args, **_kwargs):
        yield {"node_id": "recall", "status": "done"}
        yield {"__final_result__": mock_output}

    with patch("src.main.set_ttl_cached", side_effect=RuntimeError("Cache store error")), \
         patch("src.agent.graph.run_agent_stream", side_effect=fake_stream):
        res = client.post("/api/agent/stream", json={"question": "Bao nhiêu xe hôm nay?"})

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))

    ans = next(e for e in events if e.get("node_id") == "__answer__")
    assert ans.get("status") == "done"
    assert ans.get("output") == "Có 200 xe vào."


def test_set_ttl_cached_direct_swallows_exception(monkeypatch):
    """set_ttl_cached swallows internal exceptions and does not raise."""
    monkeypatch.setattr("src.memory.ttl_cache._ttl_lock", _FailingLock())
    # Must not raise
    set_ttl_cached("k", {"ans": "1"})


def test_recall_long_term_raises_recall_node_returns_empty_memories(monkeypatch):
    """recall_long_term raises -> recall_node returns empty memories, no exception, with degraded flag."""
    with patch("src.memory.longterm.recall_long_term", side_effect=RuntimeError("Qdrant cluster unavailable")):
        state = {
            "question": "Tôi phụ trách cổng số 1",
            "user_id": "u_test_degrade",
            "session_id": "sess_test",
        }
        res = recall_node(state)

    assert res["recalled_memories"] == []
    assert len(res["events"]) == 1
    ev = res["events"][0]
    assert ev["node_id"] == "recall"
    assert ev["output"]["recalled_memories"] == []
    assert ev["output"]["degraded"] is True
    assert "Qdrant" in ev["output"]["error"]


def test_recall_long_term_direct_hardened_against_exceptions():
    """recall_long_term itself catches unexpected exceptions and returns []."""
    with patch("src.memory.longterm._tokenize", side_effect=RuntimeError("Tokenize failure")):
        save_to_long_term("u1", "Some fact")
        res = recall_long_term("u1", "fact")
        assert res == []


def test_save_to_long_term_direct_hardened_against_exceptions(monkeypatch):
    """save_to_long_term catches unexpected exceptions and does not raise."""
    monkeypatch.setattr("src.memory.longterm._LONG_TERM_STORE", _FailingList())
    # Must not raise
    save_to_long_term("u1", "Fact")


def test_extract_and_store_memory_raises_run_store_extract_degraded():
    """extract_and_store_memory raises -> run_store_extract returns done event with degraded output, no raise."""
    with patch(
        "src.memory.extract.extract_and_store_memory",
        side_effect=RuntimeError("Database write deadlock"),
    ):
        events = run_store_extract(
            user_id="u_degrade",
            session_id="s_degrade",
            question="Tôi tên là Nam",
            result=Agent_Output(question="Tôi tên là Nam", answer="Chào Nam!"),
        )

    assert isinstance(events, list)
    assert len(events) >= 2
    done_ev = next(e for e in events if e.get("node_id") == "store_extract" and e.get("status") == "done")
    assert done_ev["output"]["extracted_memories"] == []
    assert done_ev["output"]["degraded"] is True
    assert "deadlock" in done_ev["output"]["error"].lower()


def test_stream_integration_recall_fail_agent_ok_store_extract_degraded(monkeypatch):
    """Integration: stream with recall fail + extract fail + agent OK -> answer status done, store degraded."""
    monkeypatch.setattr("src.monitoring.tracing.settings.monitoring_enabled", False)

    with patch("src.memory.longterm.recall_long_term", side_effect=RuntimeError("Vector DB unavailable")), \
         patch("src.memory.extract.extract_and_store_memory", side_effect=RuntimeError("Store DB full")):
        res = client.post("/api/agent/stream", json={"question": "Hôm nay có bao nhiêu lượt xe vào?"})

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload and payload != "[DONE]":
                events.append(json.loads(payload))

    # Graph executed and emitted __answer__
    answer_event = next((e for e in events if e.get("node_id") == "__answer__"), None)
    assert answer_event is not None
    assert answer_event.get("status") == "done"
    assert answer_event.get("output") != ""

    # Recall event had degraded output
    recall_event = next((e for e in events if e.get("node_id") == "recall" and e.get("status") == "done"), None)
    assert recall_event is not None
    assert recall_event.get("output", {}).get("degraded") is True
    assert recall_event.get("output", {}).get("recalled_memories") == []

    # Store extract had degraded output
    store_event = next((e for e in events if e.get("node_id") == "store_extract" and e.get("status") == "done"), None)
    assert store_event is not None
    assert store_event.get("output", {}).get("degraded") is True
    assert store_event.get("output", {}).get("extracted_memories") == []


def test_memory_master_disabled_turns_off_all_layers(monkeypatch):
    """MEMORY_ENABLED=false tắt short-term checkpointer, long-term recall/store, TTL cache."""
    from src.agent.graph import recall_node, run_store_extract, Agent_Output
    from src.config import settings

    clear_ttl_cache()
    monkeypatch.setattr(settings, "memory_enabled", False)

    assert settings.short_term_memory_enabled is False
    assert settings.long_term_memory_enabled is False
    assert settings.ttl_cache_enabled is False
    assert get_checkpointer() is None

    recall_out = recall_node({"question": "Hôm nay có bao nhiêu xe?", "user_id": "u1"})
    assert recall_out["recalled_memories"] == []
    assert recall_out["events"][0]["output"].get("disabled") is True

    stored = run_store_extract("u1", "s1", "q", Agent_Output(question="q", answer="a", detail="query_data"))
    assert stored == []

    key = make_cache_key("test")
    set_ttl_cached(key, {"answer": "x"})
    assert get_ttl_cached(key) is None


def test_memory_env_bool_accepts_one(monkeypatch):
    """MEMORY_ENABLED=1 được coi là true."""
    from src.config import Settings

    s = Settings(MEMORY_ENABLED="1")
    assert s.memory_enabled is True
    s0 = Settings(MEMORY_ENABLED="0")
    assert s0.memory_enabled is False

