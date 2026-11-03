"""LangGraph pipeline — wiring mỏng; nodes trong submodules (pattern llm-engineer-demo)."""

from __future__ import annotations

from src.domain.agents.graph_run import (
    _fresh_invoke_state,
    run_agent,
    run_agent_stream,
    save_graph_visualization,
)
from src.domain.agents.graph_runtime import _stream_queue, _wrap_node, emit_answer_chunks
from src.domain.agents.graph_wiring import _build_graph, _compiled, _get_graph, reset_graph
from src.domain.agents.nodes_memory import (
    extract_memory_node,
    recall_memory_node,
    recall_node,
    run_store_extract,
)
from src.domain.agents.nodes_orchestrator_core import orchestrator_node, route_orchestrator
from src.domain.agents.nodes_orchestrator_synth import (
    _aggregate_all_events_rows,
    _build_orchestrator_query_result,
    _try_format_all_events_answer,
    _try_format_hay_comparison_answer,
    orchestrator_collect_step_node,
    route_after_orchestrator_collect,
)
from src.domain.agents.nodes_pipeline import (
    answer_from_docs_node,
    render_chart_node,
    retrieve_docs_node,
    retrieve_schema_node,
)
from src.domain.agents.nodes_respond import respond_node
from src.domain.agents.nodes_rewrite_classify import (
    classify_node,
    respond_inline_node,
    rewrite_node,
    route_intent,
)
from src.domain.agents.state import Agent_Input, Agent_Output, AgentState

# Re-export cho unittest.mock.patch("src.domain.agents.graph.*")
from src.domain.agents.graph_helpers import memory_context_block as _memory_context_block
from src.domain.agents.graph_helpers import strip_thinking as _strip_thinking
from src.domain.agents.intent import classify_intent_safe, sanitize_intent_result
from src.domain.agents.rewrite import rewrite_question
from src.infra.chart.render import render_chart
from src.infra.db.executor import execute_sql

__all__ = [
    "Agent_Input",
    "Agent_Output",
    "AgentState",
    "run_agent",
    "run_agent_stream",
    "_build_graph",
    "_get_graph",
    "reset_graph",
    "_compiled",
    "_fresh_invoke_state",
    "_stream_queue",
    "_wrap_node",
    "emit_answer_chunks",
    "recall_node",
    "recall_memory_node",
    "extract_memory_node",
    "run_store_extract",
    "rewrite_node",
    "classify_node",
    "respond_inline_node",
    "route_intent",
    "orchestrator_node",
    "route_orchestrator",
    "orchestrator_collect_step_node",
    "route_after_orchestrator_collect",
    "retrieve_docs_node",
    "answer_from_docs_node",
    "retrieve_schema_node",
    "render_chart_node",
    "respond_node",
    "save_graph_visualization",
    "classify_intent_safe",
    "rewrite_question",
    "execute_sql",
    "render_chart",
]

if __name__ == "__main__":
    png = save_graph_visualization("graph.png")
    print(f"Exported: {png}, graph.mmd, graph_diagram.html")
