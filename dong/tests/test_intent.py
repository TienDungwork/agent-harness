"""Unit tests verifying the ReAct agent graph intent routing."""

from __future__ import annotations

from unittest.mock import patch
from src.agent.graph import Agent_Input, run_agent, _build_graph


def test_graph_nodes_and_structure():
    """Kiểm tra đồ thị có các node classify, docs, out, react."""
    compiled_graph = _build_graph()
    graph = compiled_graph.get_graph()
    node_names = set(graph.nodes.keys())
    assert "classify" in node_names
    assert "docs" in node_names
    assert "out" in node_names
    assert "react" in node_names


@patch("src.llm.use_offline_tools", return_value=False)
@patch("src.agent.intent.invoke_text")
@patch("src.agent.docs.invoke_text", return_value="Đây là cách xem lại camera")
def test_intent_routing(mock_docs_invoke, mock_invoke_text, mock_offline):
    """Test intent routing: stats, how-to, weather."""
    # Mock return values for different intents
    mock_invoke_text.side_effect = ["query_data", "how_to", "out_of_scope"]
    
    # 1. query_data -> should go to react
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
    out1 = run_agent(inp)
    assert out1.detail != "docs" and out1.detail != "out_of_scope"
    
    # 2. how_to -> should go to docs, no tool called
    inp = Agent_Input(question="Cách xem lại camera")
    out2 = run_agent(inp)
    assert out2.detail == "docs"
    
    # 3. out_of_scope -> should go to out
    inp = Agent_Input(question="Thời tiết hôm nay")
    out3 = run_agent(inp)
    assert out3.detail == "out_of_scope"

