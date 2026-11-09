"""Root + shared nodes: supervisor routing and prefix/team helpers."""

from __future__ import annotations

from src.domain.agents.nodes.supervisor import orchestrator_node, route_orchestrator
from src.domain.agents.nodes.synth import (
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
)
from src.domain.agents.state import AssistantState

top_supervisor_node = orchestrator_node


def route_from_top(state: AssistantState) -> str:
    return state.get("next_team") or "synth"


__all__ = [
    "top_supervisor_node",
    "route_from_top",
    "orchestrator_node",
    "route_orchestrator",
    "orchestrator_collect_step_node",
    "route_after_orchestrator_collect",
]
