import pytest
from unittest.mock import patch, MagicMock
from src.agent.graph import run_agent, Agent_Input, _compiled

@pytest.fixture(autouse=True)
def reset_graph():
    """Reset compiled graph to pick up new nodes/edges."""
    import src.agent.graph
    src.agent.graph._compiled = None
    yield
    src.agent.graph._compiled = None

def test_inline_answer_routing():
    """Test that a greeting (chat intent) routes directly to END without hitting SQL or Docs nodes."""
    with patch("src.llm.client.use_offline_tools", return_value=True):
        inp = Agent_Input(question="xin chào bạn")
        result = run_agent(inp)
        
        assert result.answer, "Result answer should not be empty"
        assert result.detail in ("chat", "clarify"), "Detail should be chat or clarify"
        assert result.query is None, "Should not execute any SQL query"
        
        from src.agent.graph import _get_graph
        graph = _get_graph()
        
        state = graph.invoke(
            {"question": "xin chào bạn", "events": []},
            config={"configurable": {"thread_id": "test_session_inline"}}
        )
        
        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]
        
        assert "classify" in node_ids
        assert "respond_inline" in node_ids
        assert "orchestrator" not in node_ids
        assert "retrieve_schema" not in node_ids
        assert "plan_query" not in node_ids
        assert "execute" not in node_ids
        assert "retrieve_docs" not in node_ids
        
def test_stat_question_still_routes_to_orchestrator():
    """Test that a simple stat question routes directly to SQL without orchestrator."""
    with patch("src.llm.client.use_offline_tools", return_value=True), \
         patch("src.agent.graph.execute_sql", return_value=[{"count": 1}]):
        inp = Agent_Input(question="hôm nay có bao nhiêu người vào")
        from src.agent.graph import _get_graph
        graph = _get_graph()
        
        state = graph.invoke(
            {"question": "hôm nay có bao nhiêu người vào", "events": []},
            config={"configurable": {"thread_id": "test_session_stat"}}
        )
        
        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]
        
        assert "classify" in node_ids
        assert "respond_inline" not in node_ids
        assert "orchestrator" not in node_ids
        assert "retrieve_schema" in node_ids
        assert "plan_query" in node_ids or "generate_sql" in node_ids


def test_pipeline_intent_fake_inline_answer_cleared_routes_to_orchestrator():
    """Pipeline intent with fake LLM answer must clear answer and skip orchestrator to retrieve_schema."""
    from src.llm.schemas import IntentResult

    fake_intent = IntentResult(
        intent="query_data",
        reason="hỏi số liệu",
        answer="bịa inline answer skip SQL",
    )
    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=fake_intent), \
         patch("src.agent.graph.execute_sql", return_value=[{"count": 1}]):
        from src.agent.graph import _get_graph
        graph = _get_graph()

        state = graph.invoke(
            {"question": "hôm nay có bao nhiêu người vào", "events": []},
            config={"configurable": {"thread_id": "test_fake_skip_stat"}}
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        assert "classify" in node_ids
        assert "respond_inline" not in node_ids
        assert "orchestrator" not in node_ids
        assert "retrieve_schema" in node_ids

        classify_ev = next(ev for ev in events if ev.get("node_id") == "classify")
        assert classify_ev["output"]["answer"] == ""


def test_docs_intent_fake_inline_answer_cleared_routes_to_docs():
    """Docs intent with fake LLM answer must clear answer and skip orchestrator to retrieve_docs."""
    from src.llm.schemas import IntentResult

    fake_intent = IntentResult(
        intent="how_to",
        reason="hướng dẫn",
        answer="bịa inline answer skip docs",
    )
    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=fake_intent):
        from src.agent.graph import _get_graph
        graph = _get_graph()

        state = graph.invoke(
            {"question": "cách xem lại camera", "events": []},
            config={"configurable": {"thread_id": "test_fake_skip_docs"}}
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        assert "classify" in node_ids
        assert "respond_inline" not in node_ids
        assert "orchestrator" not in node_ids
        assert "retrieve_docs" in node_ids

        classify_ev = next(ev for ev in events if ev.get("node_id") == "classify")
        assert classify_ev["output"]["answer"] == ""

def test_multi_heuristic_hits_orchestrator():
    """Test that a multi question still hits orchestrator."""
    with patch("src.llm.client.use_offline_tools", return_value=True):
        from src.agent.graph import _get_graph
        graph = _get_graph()

        state = graph.invoke(
            {"question": "hôm nay có bao nhiêu người vào, và cho biết cách xem lại camera", "events": []},
            config={"configurable": {"thread_id": "test_multi"}}
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        assert "classify" in node_ids
        assert "orchestrator" in node_ids

