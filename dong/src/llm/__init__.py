"""LLM package — client + structured output."""

from src.llm.client import (
    _BACKENDS,
    _RotatingKeyPool,
    _pool,
    base_llm,
    invoke_text,
    invoke_with_tools,
    ping,
    use_offline_tools,
)
from src.llm.schemas import (
    ChartSpec,
    DocsAnswer,
    IntentResult,
    QueryPlan,
    RewrittenQuestion,
    StatAnswer,
)
from src.llm.structured import invoke_structured

__all__ = [
    "_BACKENDS",
    "_RotatingKeyPool",
    "_pool",
    "base_llm",
    "invoke_text",
    "invoke_with_tools",
    "invoke_structured",
    "ping",
    "use_offline_tools",
    "RewrittenQuestion",
    "IntentResult",
    "QueryPlan",
    "DocsAnswer",
    "StatAnswer",
    "ChartSpec",
]
