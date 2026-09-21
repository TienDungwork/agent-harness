from __future__ import annotations

from agent.graph.state import AgentState
from agent.tools.postgres.validator import validate_sql


def validate_sql_node(state: AgentState) -> dict:
    result = validate_sql(state.get("sql") or "", state.get("relevant_datasets") or [])
    return {"sql_validation": result.to_dict()}
