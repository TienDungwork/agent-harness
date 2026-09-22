"""Unit tests verifying rewrite_question, classify_intent, and graph intent routing."""

from __future__ import annotations

from unittest.mock import patch

from src.agent import classify_intent, classify_intent_str, rewrite_question
from src.agent.graph import Agent_Input, _build_graph, run_agent
from src.llm.schemas import IntentResult, RewrittenQuestion


def test_graph_nodes_and_structure():
    """Kiểm tra đồ thị v5: rewrite → classify → query/docs/out (không còn react)."""
    compiled_graph = _build_graph()
    graph = compiled_graph.get_graph()
    node_names = set(graph.nodes.keys())
    assert "rewrite" in node_names
    assert "classify" in node_names
    assert "retrieve_schema" in node_names
    assert "plan_query" in node_names
    assert "retrieve_docs" in node_names
    assert "out_of_scope" in node_names
    assert "react" not in node_names


@patch("src.agent.graph.rewrite_question")
@patch("src.agent.intent.use_offline_tools", return_value=False)
@patch("src.agent.intent.invoke_structured")
def test_intent_routing(mock_invoke_structured, mock_offline, mock_rewrite):
    """Test intent routing qua invoke_structured: stats, how-to, weather."""
    from src.llm.schemas import RewrittenQuestion
    mock_rewrite.side_effect = [
        RewrittenQuestion(text="Hôm nay có bao nhiêu lượt xe vào?", intent_hint=None),
        RewrittenQuestion(text="Cách xem lại camera", intent_hint=None),
        RewrittenQuestion(text="Thời tiết hôm nay", intent_hint=None),
    ]
    mock_invoke_structured.side_effect = [
        IntentResult(intent="query_data", reason="hỏi số liệu"),
        IntentResult(intent="how_to", reason="hướng dẫn"),
        IntentResult(intent="out_of_scope", reason="thời tiết"),
    ]

    # 1. query_data -> should go to query_data path
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
    out1 = run_agent(inp)
    assert out1.detail != "docs" and out1.detail != "out_of_scope"

    # 2. how_to -> docs YAML path (không còn invoke_text)
    inp = Agent_Input(question="Cách xem lại camera")
    out2 = run_agent(inp)
    assert out2.detail == "docs"
    assert out2.answer

    # 3. out_of_scope -> should go to out
    inp = Agent_Input(question="Thời tiết hôm nay")
    out3 = run_agent(inp)
    assert out3.detail == "out_of_scope"

    assert mock_invoke_structured.call_count == 3


def test_rewrite_question_offline():
    """Test rewrite_question chế độ offline (không gọi LAN)."""
    res = rewrite_question("Hôm nay có bao nhiêu xe vào cổng 1?")
    assert isinstance(res, RewrittenQuestion)
    assert res.text == "Hôm nay có bao nhiêu xe vào cổng 1?"
    assert res.time_range == "today"
    assert "direction=IN" in res.filters
    assert res.intent_hint == "query_data"

    empty = rewrite_question("   ")
    assert empty.text == ""
    assert empty.filters == []


@patch("src.agent.rewrite.use_offline_tools", return_value=False)
@patch("src.agent.rewrite.invoke_structured")
def test_rewrite_question_mock_structured(mock_structured, _mock_offline):
    """Test rewrite_question gọi invoke_structured khi online."""
    expected = RewrittenQuestion(
        text="Thống kê xe vào hôm nay",
        filters=["direction=IN"],
        time_range="today",
        intent_hint="query_data",
    )
    mock_structured.return_value = expected

    out = rewrite_question("xe vào hôm nay")
    assert out == expected
    assert out.filters == ["direction=IN"]
    assert mock_structured.called


def test_classify_intent_offline_heuristics():
    """Test classify_intent offline heuristic cho từng loại intent."""
    res_how_to = classify_intent("Làm sao thêm camera?")
    assert isinstance(res_how_to, IntentResult)
    assert res_how_to.intent == "how_to"

    res_troubleshoot = classify_intent("Tại sao camera mất kết nối?")
    assert res_troubleshoot.intent == "troubleshoot"

    res_concept = classify_intent("AIOC là gì?")
    assert res_concept.intent == "concept"

    res_oos = classify_intent("Thời tiết hôm nay thế nào?")
    assert res_oos.intent == "out_of_scope"

    res_query = classify_intent("Hôm nay có bao nhiêu lượt xe vào?")
    assert res_query.intent == "query_data"


@patch("src.agent.intent.use_offline_tools", return_value=False)
@patch("src.agent.intent.invoke_structured")
def test_classify_intent_mock_structured(mock_structured, _mock_offline):
    """Test classify_intent mock invoke_structured (how_to != query_data)."""
    mock_structured.return_value = IntentResult(intent="how_to", reason="hướng dẫn cấu hình")

    rewritten = RewrittenQuestion(text="cách xem lại video")
    res = classify_intent(rewritten)
    assert isinstance(res, IntentResult)
    assert res.intent == "how_to"
    assert res.intent != "query_data"
    assert res.reason == "hướng dẫn cấu hình"

    # Helper classify_intent_str returns str
    assert classify_intent_str(rewritten) == "how_to"
