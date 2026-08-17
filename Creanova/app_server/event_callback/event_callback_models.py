# pyright: reportIncompatibleMethodOverride=false
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Literal
from uuid import UUID, uuid4

from pydantic import Field

from Creanova.agent_server.utils import CreanovaUUID, utc_now
from Creanova.app_server.event_callback.event_callback_result_models import (
    EventCallbackResult,
    EventCallbackResultStatus,
)
from Creanova.sdk import Event
from Creanova.sdk.utils.models import (
    CreanovaModel,
    DiscriminatedUnionMixin,
    get_known_concrete_subclasses,
)
from Creanova.sdk.utils.redact import redact_text_secrets

_logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    EventKind = str
else:
    EventKind = Literal[tuple(c.__name__ for c in get_known_concrete_subclasses(Event))]


class EventCallbackStatus(Enum):
    ACTIVE = 'ACTIVE'
    DISABLED = 'DISABLED'
    COMPLETED = 'COMPLETED'
    ERROR = 'ERROR'


class EventCallbackProcessor(DiscriminatedUnionMixin, ABC):
    event_kind: ClassVar[EventKind] = 'MessageEvent'

    @classmethod
    def get_event_kind(cls) -> EventKind:
        return cls.event_kind

    @abstractmethod
    async def __call__(
        self,
        conversation_id: UUID,
        callback: EventCallback,
        event: Event,
    ) -> EventCallbackResult | None:
        """Process an event."""


class LoggingCallbackProcessor(EventCallbackProcessor):
    """Example implementation which logs callbacks."""

    async def __call__(
        self,
        conversation_id: UUID,
        callback: EventCallback,
        event: Event,
    ) -> EventCallbackResult:
        _logger.info(
            'Callback %s Invoked for event %s',
            callback.id,
            redact_text_secrets(str(event)),
        )
        return EventCallbackResult(
            status=EventCallbackResultStatus.SUCCESS,
            event_callback_id=callback.id,
            event_id=event.id,
            conversation_id=conversation_id,
        )


class CreateEventCallbackRequest(CreanovaModel):
    conversation_id: CreanovaUUID = Field(
        description='Conversation to which this callback applies',
    )
    processor: EventCallbackProcessor
    event_kind: EventKind = Field(
        default='MessageEvent',
        description='Type of event to which this callback applies',
    )


class EventCallback(CreateEventCallbackRequest):
    id: CreanovaUUID = Field(default_factory=uuid4)
    status: EventCallbackStatus = Field(default=EventCallbackStatus.ACTIVE)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EventCallbackPage(CreanovaModel):
    items: list[EventCallback]
    next_page_id: str | None = None
