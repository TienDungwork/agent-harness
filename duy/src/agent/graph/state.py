from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    intent: str
    intent_reason: str
    relevant_datasets: list[dict[str, Any]]
    schema_excerpt: str
    relevant_docs: list[dict[str, Any]]
    docs_excerpt: str
    doc_card_id: str
    doc_card_title: str
    sql: str
    sql_validation: dict[str, Any]
    repair_count: int
    query_result: dict[str, Any]
    chart_png_base64: str
    chart_meta: str
    web_results: list[dict[str, Any]]
    web_excerpt: str
    web_sources: list[dict[str, str]]
    llm_model_id: str
    llm_model_label: str
    answer: str
    error: str
