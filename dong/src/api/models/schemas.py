"""Pydantic request/response cho REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi thống kê tự nhiên")
    model_provider: str | None = Field(default=None, description="Tùy chọn: 'openai' hoặc 'self_hosted'")
    model_override: str | None = Field(default=None, description="Tùy chọn ghi đè model name")
    session_id: str = Field(default="default", description="ID phiên hội thoại")
    user_id: str = Field(default="default", description="ID người dùng")
    stream_tokens: bool = Field(default=False, description="Phát các SSE chunk events cho câu trả lời")


class ChatResponse(BaseModel):
    question: str
    answer: str
    tool: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    row_count: int = 0


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="Câu hỏi thống kê tự nhiên")


class AskResponse(BaseModel):
    question: str
    answer: str
    tool: str = ""
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0


class MemoryListResponse(BaseModel):
    status: str = "ok"
    user_id: str
    facts: list[str] = Field(default_factory=list, description="Danh sách sự thật/thông tin cá nhân đã nhớ")
    memories: list[str] = Field(default_factory=list, description="Alias tương thích ngược cho facts")
    total: int = 0


class MemoryDeleteResponse(BaseModel):
    status: str = "ok"
    message: str
    user_id: str
    deleted: bool = True
