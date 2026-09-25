"""Short-term memory checkpointer MVP using MemorySaver."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver | None:
    """Return singleton MemorySaver khi bật; None khi MEMORY_SHORT_TERM_ENABLED=false."""
    from src.config import settings

    if not settings.short_term_memory_enabled:
        return None
    return _checkpointer
