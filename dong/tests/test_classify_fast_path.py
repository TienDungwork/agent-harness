"""Tests for Phase 3a: Classify fast path (chào → 1 hop; câu số liệu → vẫn vào SQL path).

Acceptance criteria verified:
A. Chào → 1 hop / fast END:
   - "xin chào" / "chào bạn" via run_agent and graph.invoke
   - result.detail in ("chat", "clarify"), answer non-empty, query is None
   - Node path has classify + respond_inline; NO retrieve_schema, plan_query, execute,
     retrieve_docs, answer_from_docs, orchestrator
   - 1 hop meaning:
     * Online: classify is the only structured LLM hop (intent invoke_structured called once;
       rewrite.invoke_structured not called). Events with meta.llm_used True == 1 (classify only).
     * Offline: rewrite meta skipped=True, llm_used=False; events with meta.llm_used True <= 1 (0 offline).
B. Câu số liệu → SQL path:
   - "Hôm nay có bao nhiêu lượt xe vào?" (and variations)
   - Goes to SQL path: retrieve_schema + plan_query executed
   - NOT respond_inline; orchestrator skipped for simple single-domain queries
   - Hallucinated answers on pipeline intents are sanitized and do not trigger fake inline skips.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch
import pytest

from src.agent.graph import Agent_Input, _get_graph, run_agent
from src.llm.schemas import IntentResult, RewrittenQuestion
from src.memory.ttl_cache import clear_ttl_cache


FORBIDDEN_NODES_FOR_GREETING = (
    "retrieve_schema",
    "plan_query",
    "validate",
    "execute",
    "render_chart",
    "respond",
    "retrieve_docs",
    "answer_from_docs",
    "orchestrator",
    "orchestrator_respond",
    "out_of_scope",
)


@pytest.fixture(autouse=True)
def reset_graph_and_state():
    """Reset compiled graph and memory caches to ensure clean, isolated tests."""
    import src.agent.graph
    src.agent.graph._compiled = None
    clear_ttl_cache()
    yield
    src.agent.graph._compiled = None
    clear_ttl_cache()


# ==============================================================================
# Part A: Chào → 1 hop / fast END
# ==============================================================================

@pytest.mark.parametrize("greeting", ["xin chào", "chào bạn", "Xin chào bạn!"])
def test_greeting_offline_fast_path_run_agent(greeting: str):
    """Greeting offline via run_agent returns chat/clarify detail without executing queries."""
    with patch("src.llm.client.use_offline_tools", return_value=True):
        inp = Agent_Input(question=greeting)
        res = run_agent(inp, session_id=f"test_session_{uuid.uuid4().hex}")

        assert res.detail in ("chat", "clarify"), f"Expected chat or clarify, got {res.detail}"
        assert res.answer.strip(), "Greeting answer must not be empty"
        assert res.query is None, "Greeting must not execute any SQL query"


@pytest.mark.parametrize("greeting", ["xin chào", "chào bạn"])
def test_greeting_offline_fast_path_graph_events(greeting: str):
    """Greeting offline node path: classify + respond_inline; no SQL/docs/orchestrator nodes; 0 LLM hops."""
    with patch("src.llm.client.use_offline_tools", return_value=True):
        graph = _get_graph()
        state = graph.invoke(
            {"question": greeting, "events": []},
            config={"configurable": {"thread_id": f"test_thread_{uuid.uuid4().hex}"}},
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        # 1. Path must contain classify and respond_inline
        assert "classify" in node_ids
        assert "respond_inline" in node_ids

        # 2. Path must NOT contain any SQL, Docs, or Orchestrator nodes
        for forbidden in FORBIDDEN_NODES_FOR_GREETING:
            assert forbidden not in node_ids, f"Node '{forbidden}' should not be visited for greeting"

        # 3. Rewrite node meta marks llm_used=False and skipped=True
        rewrite_ev = next(ev for ev in events if ev.get("node_id") == "rewrite")
        assert rewrite_ev.get("meta", {}).get("llm_used") is False
        assert rewrite_ev.get("meta", {}).get("skipped") is True

        # 4. Offline: total events with llm_used=True is <= 1 (specifically 0)
        llm_used_events = [ev for ev in events if ev.get("meta", {}).get("llm_used") is True]
        assert len(llm_used_events) <= 1
        assert len(llm_used_events) == 0

        # 5. Result validation
        result = state.get("result")
        assert result is not None
        assert result.detail in ("chat", "clarify")
        assert result.answer.strip()
        assert result.query is None


@pytest.mark.parametrize("greeting", ["xin chào", "chào bạn"])
def test_greeting_online_one_hop_meaning(greeting: str):
    """Greeting online structured LLM: classify is the ONLY structured hop; rewrite LLM is skipped.

    Verification:
    - mock invoke_structured on intent path called exactly once.
    - mock invoke_structured on rewrite path not called.
    - Events with meta.llm_used=True == 1 (classify only).
    - Routes to respond_inline -> END; no SQL/docs/orchestrator nodes.
    """
    mock_chat_intent = IntentResult(
        intent="chat",
        reason="chào hỏi giao tiếp",
        answer="Chào bạn, tôi là trợ lý ảo AIOC. Bạn cần tôi giúp gì?",
    )

    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.use_offline_tools", return_value=False), \
         patch("src.agent.rewrite.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=mock_chat_intent) as mock_intent_invoke, \
         patch("src.agent.rewrite.invoke_structured") as mock_rewrite_invoke:

        graph = _get_graph()
        state = graph.invoke(
            {"question": greeting, "events": []},
            config={"configurable": {"thread_id": f"test_thread_{uuid.uuid4().hex}"}},
        )

        # 1. Hop check: rewrite LLM NOT called; classify LLM called ONCE
        mock_rewrite_invoke.assert_not_called()
        mock_intent_invoke.assert_called_once()

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        # 2. Node path has classify and respond_inline
        assert "classify" in node_ids
        assert "respond_inline" in node_ids

        # 3. No SQL, Docs, or Orchestrator nodes
        for forbidden in FORBIDDEN_NODES_FOR_GREETING:
            assert forbidden not in node_ids, f"Node '{forbidden}' should not be visited for greeting"

        # 4. Meta check: only classify has llm_used=True
        llm_used_events = [ev for ev in events if ev.get("meta", {}).get("llm_used") is True]
        assert len(llm_used_events) == 1
        assert llm_used_events[0].get("node_id") == "classify"

        # 5. Rewrite node marked skipped
        rewrite_ev = next(ev for ev in events if ev.get("node_id") == "rewrite")
        assert rewrite_ev.get("meta", {}).get("llm_used") is False
        assert rewrite_ev.get("meta", {}).get("skipped") is True

        # 6. Result integrity
        result = state.get("result")
        assert result is not None
        assert result.detail == "chat"
        assert result.answer == "Chào bạn, tôi là trợ lý ảo AIOC. Bạn cần tôi giúp gì?"
        assert result.query is None


def test_greeting_run_agent_online_one_hop():
    """run_agent for greeting online executes single-hop classify and returns Agent_Output."""
    mock_chat_intent = IntentResult(
        intent="chat",
        reason="chào hỏi",
        answer="Chào bạn! Tôi có thể hỗ trợ gì cho bạn hôm nay?",
    )

    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.use_offline_tools", return_value=False), \
         patch("src.agent.rewrite.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=mock_chat_intent) as mock_intent_invoke, \
         patch("src.agent.rewrite.invoke_structured") as mock_rewrite_invoke:

        inp = Agent_Input(question="xin chào")
        res = run_agent(inp, session_id=f"test_session_{uuid.uuid4().hex}")

        mock_rewrite_invoke.assert_not_called()
        mock_intent_invoke.assert_called_once()

        assert res.detail == "chat"
        assert res.answer == "Chào bạn! Tôi có thể hỗ trợ gì cho bạn hôm nay?"
        assert res.query is None


# ==============================================================================
# Part B: Câu số liệu → SQL path
# ==============================================================================

@pytest.mark.parametrize("question", [
    "Hôm nay có bao nhiêu lượt xe vào?",
    "Hôm nay có bao nhiêu người vào",
])
def test_stat_question_routes_to_sql_path_offline(question: str):
    """Stat questions offline route to SQL path: retrieve_schema, plan_query, validate, execute, respond."""
    mock_rows = [{"so_luot": 120}]

    with patch("src.llm.client.use_offline_tools", return_value=True), \
         patch("src.agent.graph.execute_sql", return_value=mock_rows):

        # 1. run_agent test
        inp = Agent_Input(question=question)
        res = run_agent(inp, session_id=f"test_session_{uuid.uuid4().hex}")

        assert res.detail == "query_data"
        assert res.answer.strip(), "Stat answer must not be empty"
        assert res.query is not None, "Stat question must return QueryResult"
        assert res.query.tool == "sql_builder"

        # 2. graph.invoke node path test
        graph = _get_graph()
        state = graph.invoke(
            {"question": question, "events": []},
            config={"configurable": {"thread_id": f"test_thread_{uuid.uuid4().hex}"}},
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        # Verify SQL path nodes
        assert "classify" in node_ids
        assert "retrieve_schema" in node_ids
        assert "generate_sql" in node_ids
        assert "validate_sql" in node_ids
        assert "execute_sql" in node_ids
        assert "respond" in node_ids

        # Verify fast-path inline respond is NOT used
        assert "respond_inline" not in node_ids

        # Verify orchestrator is skipped for simple single query
        assert "orchestrator" not in node_ids

        # Verify docs nodes are NOT visited
        assert "retrieve_docs" not in node_ids
        assert "answer_from_docs" not in node_ids


def test_stat_question_routes_to_sql_path_online_mocked():
    """Stat question online with structured LLM routes to SQL path and skips orchestrator & inline respond."""
    mock_query_intent = IntentResult(
        intent="query_data",
        reason="hỏi số liệu lượt xe",
        answer="",
    )
    mock_rewritten = RewrittenQuestion(
        text="Thống kê lượt xe vào hôm nay",
        filters=["direction=IN"],
        time_range="today",
        intent_hint="query_data",
    )
    mock_rows = [{"so_luot": 250}]

    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.use_offline_tools", return_value=False), \
         patch("src.agent.rewrite.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=mock_query_intent), \
         patch("src.agent.rewrite.invoke_structured", return_value=mock_rewritten), \
         patch("src.agent.graph.execute_sql", return_value=mock_rows):

        graph = _get_graph()
        state = graph.invoke(
            {"question": "Hôm nay có bao nhiêu lượt xe vào?", "events": []},
            config={"configurable": {"thread_id": f"test_thread_{uuid.uuid4().hex}"}},
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        assert "classify" in node_ids
        assert "retrieve_schema" in node_ids
        assert "generate_sql" in node_ids
        assert "validate_sql" in node_ids
        assert "execute_sql" in node_ids
        assert "respond" in node_ids

        assert "respond_inline" not in node_ids
        assert "orchestrator" not in node_ids

        result = state.get("result")
        assert result is not None
        assert result.detail == "query_data"
        assert result.query is not None


def test_stat_question_with_hallucinated_answer_sanitized_and_routes_to_sql():
    """Anti fake-skip: if LLM hallucinates an answer for query_data, it is cleared and stays on SQL path."""
    fake_intent = IntentResult(
        intent="query_data",
        reason="truy vấn số liệu xe",
        answer="Tôi trả lời ngay không cần SQL: có 99 xe.",
    )
    mock_rows = [{"so_luot": 99}]

    with patch("src.llm.client.use_offline_tools", return_value=False), \
         patch("src.agent.intent.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured", return_value=fake_intent), \
         patch("src.agent.graph.execute_sql", return_value=mock_rows):

        graph = _get_graph()
        state = graph.invoke(
            {"question": "Hôm nay có bao nhiêu lượt xe vào?", "events": []},
            config={"configurable": {"thread_id": f"test_thread_{uuid.uuid4().hex}"}},
        )

        events = state.get("events", [])
        node_ids = [ev.get("node_id") for ev in events]

        # classify answer must be sanitized to ""
        classify_ev = next(ev for ev in events if ev.get("node_id") == "classify")
        assert classify_ev["output"]["answer"] == ""

        # Must go to SQL path, never respond_inline
        assert "respond_inline" not in node_ids
        assert "retrieve_schema" in node_ids
        assert "generate_sql" in node_ids
        assert "orchestrator" not in node_ids

        result = state.get("result")
        assert result is not None
        assert result.detail == "query_data"
        assert result.query is not None
