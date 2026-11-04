"""Agent graph state và I/O models."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel
from langgraph.graph.message import add_messages

from src.infra.llm.schemas import ChartSpec, OrchestratorPlan, QueryResult, RewrittenQuestion

class Agent_Input(BaseModel):
    question: str
    rewritten: Any | None = None
    user_id: str = "default"
    stream_tokens: bool = False

class Agent_Output(BaseModel):
    question: str
    answer: str
    query: QueryResult | None = None
    detail: str = ""

class AgentState(TypedDict, total=False):
    question: str
    original_question: str
    rewritten: RewrittenQuestion
    intent: str
    answer: str
    stream_tokens: bool
    messages: Annotated[list, add_messages]
    user_id: str
    session_id: str
    recalled_memories: list[str]
    extracted_memories: list[str]
    orchestrator_plan: OrchestratorPlan
    orchestrator_step_index: int
    orchestrator_batch_sub_questions: list[str]
    orchestrator_batch_end_index: int
    orchestrator_step_results: list[dict]
    orchestrator_multi_active: bool
    sql_batch: list[dict]
    sql_batch_results: list[dict]
    multi_hop_ready: bool
    respond_mode: str
    docs_answer: dict

    # Query Data branch
    selected_tables: list[str]
    schema_excerpt: str
    sql: str
    sql_validation: dict
    repair_count: int
    params: list
    rows: list
    columns: list
    error: str
    chart_png_base64: str
    chart_spec: ChartSpec
    chart_requested: bool
    chart_type: str | None
    
    events: Annotated[list[dict], operator.add]
    result: Agent_Output
    guardrail_in_scope: bool
