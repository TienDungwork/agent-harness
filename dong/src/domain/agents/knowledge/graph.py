"""Compile knowledge subgraph (docs retrieval + answer)."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.domain.agents.knowledge.docs_agent.nodes import answer_from_docs_node, retrieve_docs_node
from src.domain.agents.state import AgentState


def build_knowledge_graph():
    from src.domain.agents.graph import _wrap_node

    g = StateGraph(AgentState)
    g.add_node("retrieve_docs", _wrap_node("retrieve_docs", retrieve_docs_node))
    g.add_node("answer_from_docs", _wrap_node("answer_from_docs", answer_from_docs_node))
    g.add_edge(START, "retrieve_docs")
    g.add_edge("retrieve_docs", "answer_from_docs")
    g.add_edge("answer_from_docs", END)
    return g.compile()
