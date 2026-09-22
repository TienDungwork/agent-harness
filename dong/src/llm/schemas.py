"""Pydantic schemas cho mọi LLM structured call (dong v5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RewrittenQuestion(BaseModel):
    text: str
    filters: list[str] = Field(default_factory=list)
    time_range: str | None = None
    intent_hint: str | None = None


class IntentResult(BaseModel):
    intent: Literal["query_data", "how_to", "troubleshoot", "concept", "out_of_scope"]
    reason: str


class QueryPlan(BaseModel):
    tables: list[str]
    selects: list[str]
    filters: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: str | None = None
    limit: int | None = None


class DocsAnswer(BaseModel):
    answer_vi: str
    card_ids: list[str] = Field(default_factory=list)
    steps: list[str] | None = None


class StatAnswer(BaseModel):
    answer_vi: str
    highlights: list[str] = Field(default_factory=list)
    chart_requested: bool = False


class ChartSpec(BaseModel):
    chart_type: str
    x_column: str
    y_column: str
    title_vi: str
