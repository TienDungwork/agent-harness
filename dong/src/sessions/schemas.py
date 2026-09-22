"""Pydantic schemas for Sessions API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionItem(BaseModel):
    id: str = Field(description="ID phiên hội thoại")
    user_id: str = Field(description="ID người dùng")
    title: str = Field(description="Tiêu đề phiên hội thoại")
    preview: str = Field(default="", description="Xem trước tin nhắn gần nhất")
    updated_at: str = Field(description="Thời gian cập nhật (ISO8601)")
    created_at: str = Field(description="Thời gian tạo (ISO8601)")


class SessionListResponse(BaseModel):
    sessions: list[SessionItem] = Field(default_factory=list, description="Danh sách phiên hội thoại")


class CreateSessionRequest(BaseModel):
    user_id: str = Field(min_length=1, description="ID người dùng")
    title: str | None = Field(default=None, description="Tiêu đề phiên hội thoại")


class DeleteSessionResponse(BaseModel):
    deleted: bool = Field(default=True, description="Trạng thái đã xóa thành công")


class SessionMessage(BaseModel):
    role: str = Field(description="Vai trò: user hoặc assistant")
    content: str = Field(description="Nội dung tin nhắn")
    timestamp: str = Field(description="Thời gian ISO8601")
    detail: dict | None = Field(default=None, description="Metadata trợ lý (tool, row_count, …)")
    chart: dict | None = Field(default=None, description="Payload biểu đồ {png, spec, type, rows}")


class SessionMessagesResponse(BaseModel):
    messages: list[SessionMessage] = Field(default_factory=list, description="Lịch sử tin nhắn phiên")
