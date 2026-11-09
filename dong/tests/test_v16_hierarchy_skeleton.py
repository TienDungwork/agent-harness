"""v16 Task 1 — skeleton AssistantState + build_graph."""

from langgraph.checkpoint.memory import MemorySaver

from src.domain.agents.graph import build_graph
from src.domain.agents.state import AssistantState


def test_assistant_state_has_root_fields():
    keys = set(AssistantState.__annotations__)
    for k in ("question", "user_id", "session_id", "intent", "next_team", "final_answer"):
        assert k in keys


def test_build_graph_callable():
    g = build_graph(checkpointer=MemorySaver())
    assert g is not None


def test_root_graph_is_canonical():
    import src.domain.agents.graph as root
    import src.domain.agents.graph as vms

    assert root.build_graph is not None
    g1 = root.build_graph(checkpointer=MemorySaver())
    assert "guardrail_input" in g1.get_graph().nodes
    assert "top_supervisor" in g1.get_graph().nodes
    assert vms._build_graph is root._build_graph


def test_route_greeting_to_synth():
    from src.domain.agents.nodes import route_from_top

    assert route_from_top({"intent": "chat", "next_team": "synth"}) == "synth"


def test_route_multi_continues_to_team():
    from src.domain.agents.nodes import route_from_top

    assert route_from_top({"next_team": "analytics_team"}) == "analytics_team"
