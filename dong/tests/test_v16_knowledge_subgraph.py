"""v16 Task 4 — knowledge subgraph."""

from src.domain.agents.knowledge.graph import build_knowledge_graph


def test_knowledge_graph_nodes():
    nodes = set(build_knowledge_graph().get_graph().nodes)
    assert "retrieve_docs" in nodes
    assert "answer_from_docs" in nodes
