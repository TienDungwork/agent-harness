"""LLM package — client + structured output."""

from src.infra.llm.client import (
    _BACKENDS,
    _RotatingKeyPool,
    _pool,
    base_llm,
    invoke_text,
    invoke_with_tools,
    ping,
    use_offline_tools,
)
from src.infra.llm.schemas import (
    ChartSpec,
    DocsAnswer,
    IntentResult,
    OrchestratorPlan,
    OrchestratorStep,
    QueryPlan,
    RewrittenQuestion,
    StatAnswer,
    normalize_chart_type,
)
from src.infra.llm.structured import invoke_structured

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
    "normalize_chart_type",
    "OrchestratorStep",
    "OrchestratorPlan",
]
