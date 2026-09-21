"""Unit tests verifying the ReAct agent graph structure (seed -> agent <-> tools -> pack)."""

from __future__ import annotations

import os
from backend.agent import Agent_Input, run_agent, save_graph_visualization
from src.agent.graph import _build_graph


def test_react_graph_nodes_and_structure():
    """Kiểm tra đồ thị ReAct LangGraph có đầy đủ 4 node cốt lõi: seed, agent, tools, pack."""
    compiled_graph = _build_graph()
    graph = compiled_graph.get_graph()
    node_names = set(graph.nodes.keys())
    
    # LangGraph standard internal nodes + custom nodes
    assert "seed" in node_names
    assert "agent" in node_names
    assert "tools" in node_names
    assert "pack" in node_names


def test_run_agent_execution_flow():
    """Kiểm tra luồng thực thi run_agent với câu hỏi mẫu."""
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
    out = run_agent(inp)
    assert out.question == "Hôm nay có bao nhiêu lượt xe vào?"
    assert out.answer.strip() != ""
    assert out.detail != ""


def test_save_graph_visualization_produces_diagram(tmp_path):
    """Kiểm tra hàm xuất sơ đồ ReAct graph tạo ra file Mermaid/PNG thành công."""
    out_file = str(tmp_path / "test_graph.png")
    result_path = save_graph_visualization(out_file)
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
