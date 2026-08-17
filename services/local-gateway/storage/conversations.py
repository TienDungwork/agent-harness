from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from storage.models import ConversationTool, UserConversation


def touch_conversation(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    title: str | None = None,
    status: str | None = None,
    source: str | None = None,
    agent_profile: str | None = None,
    llm_model: str | None = None,
) -> UserConversation:
    row = (
        db.query(UserConversation)
        .filter(UserConversation.conversation_id == conversation_id)
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if row is None:
        row = UserConversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
            status=status or 'active',
            source=source or 'web',
            agent_profile=agent_profile,
            llm_model=llm_model,
            last_activity_at=now,
        )
        db.add(row)
    else:
        if row.user_id != user_id:
            raise PermissionError('Conversation belongs to another user')
        if title is not None:
            row.title = title
        if status is not None:
            row.status = status
        if agent_profile is not None:
            row.agent_profile = agent_profile
        if llm_model is not None:
            row.llm_model = llm_model
        row.last_activity_at = now
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def upsert_conversation_tool(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    tool_kind: str,
    tool_name: str,
    tool_version: str | None = None,
    source: str | None = None,
    config: dict | None = None,
) -> None:
    existing = (
        db.query(ConversationTool)
        .filter(
            ConversationTool.conversation_id == conversation_id,
            ConversationTool.tool_kind == tool_kind,
            ConversationTool.tool_name == tool_name,
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if existing is None:
        db.add(
            ConversationTool(
                conversation_id=conversation_id,
                user_id=user_id,
                tool_kind=tool_kind,
                tool_name=tool_name,
                tool_version=tool_version,
                source=source,
                config=config or {},
                enabled=True,
                last_used_at=now,
            )
        )
    else:
        existing.enabled = True
        existing.tool_version = tool_version or existing.tool_version
        if config is not None:
            existing.config = config
        if source is not None:
            existing.source = source
        existing.last_used_at = now
    db.commit()


def list_conversation_tools(
    db: Session, conversation_id: str
) -> list[ConversationTool]:
    return (
        db.query(ConversationTool)
        .filter(ConversationTool.conversation_id == conversation_id)
        .order_by(ConversationTool.tool_kind, ConversationTool.tool_name)
        .all()
    )
