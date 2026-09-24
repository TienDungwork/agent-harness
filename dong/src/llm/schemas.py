"""Pydantic schemas cho mọi LLM structured call (dong v5)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RewrittenQuestion(BaseModel):
    text: str
    sub_questions: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    time_range: str | None = None
    intent_hint: str | None = None


class IntentResult(BaseModel):
    intent: Literal["query_data", "how_to", "troubleshoot", "concept", "out_of_scope", "chat", "clarify"]
    reason: str
    answer: str = ""


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


def normalize_chart_type(raw: Any) -> Literal["bar", "pie", "line"]:
    """Normalize raw chart type into 'bar' | 'pie' | 'line'. Defaults to 'bar' if invalid."""
    if not raw or not isinstance(raw, str):
        return "bar"
    val = raw.strip().lower()
    if val in ("bar", "pie", "line"):
        return val  # type: ignore[return-value]
    if any(k in val for k in ("pie", "tròn", "tron", "bánh", "banh", "cơ cấu", "co cau", "tỷ lệ", "ty le", "phần trăm")):
        return "pie"
    if any(k in val for k in ("line", "đường", "duong", "thời gian", "thoi gian", "xu hướng", "xu huong", "ngày", "ngay", "tháng", "thang", "giờ", "gio")):
        return "line"
    if any(k in val for k in ("bar", "cột", "cot")):
        return "bar"
    return "bar"


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "pie", "line"] = "bar"
    x_column: str = ""
    y_column: str = ""
    title_vi: str = ""

    @field_validator("chart_type", mode="before")
    @classmethod
    def _validate_chart_type(cls, v: Any) -> str:
        return normalize_chart_type(v)


class OrchestratorStep(BaseModel):
    agent: Literal["query_data", "docs"]
    sub_question: str


class OrchestratorPlan(BaseModel):
    steps: list[OrchestratorStep] = Field(default_factory=list)
    is_multi: bool = False
    reason: str = ""

    @field_validator("is_multi", mode="after")
    @classmethod
    def _validate_is_multi(cls, v: bool, info: Any) -> bool:
        return v

    def model_post_init(self, __context: Any) -> None:
        if len(self.steps) >= 2:
            self.is_multi = True



class QueryResult(BaseModel):
    tool: str = "sql_builder"
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    error: str = ""
    reply_vi: str = ""


import base64


class FeedbackRequest(BaseModel):
    session_id: str
    user_id: str = "default"
    question: str
    answer: str
    rating: Literal["positive", "negative"]
    feedback_reason: str | None = None
    image_base64: str | None = None
    image_filename: str | None = None
    agent_trace: dict[str, Any] | None = None

    @field_validator("session_id", "question", "answer", mode="after")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Trường này không được để trống.")
        return v.strip()

    @field_validator("image_base64", mode="after")
    @classmethod
    def _validate_image_base64(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return None
        raw = v.strip()
        if "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            decoded = base64.b64decode(raw, validate=True)
        except Exception:
            raise ValueError("Dữ liệu ảnh base64 không hợp lệ.")
        if len(decoded) > 5 * 1024 * 1024:
            raise ValueError("Kích thước ảnh vượt quá giới hạn 5MB.")
        return v




