"""Short-term memory checkpointer MVP using MemorySaver."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

_checkpointer = MemorySaver()


def get_checkpointer() -> MemorySaver:
    """Return singleton MemorySaver checkpointer."""
    return _checkpointer
