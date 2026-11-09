"""v16 Task 3 — analytics subgraph node set."""

from src.domain.agents.analytics.graph import build_analytics_graph


def test_analytics_graph_has_sql_nodes():
    g = build_analytics_graph()
    nodes = set(g.get_graph().nodes)
    for n in ("retrieve_schema", "generate_sql", "validate_sql", "repair_sql", "execute_sql"):
        assert n in nodes
