"""LLM package — client factory, completion, async, structured output."""

from src.infra.llm.backends import BACKENDS, get_backend
from src.infra.llm.client import (
    _pool,
    base_llm,
    clear_key_pool,
    get_client,
    llm_model_label,
    mark_current_key_limited,
    ping,
    use_offline_tools,
)
from src.infra.llm.completion import invoke_text, invoke_with_tools
from src.infra.llm.params import (
    BALANCED,
    CREATIVE,
    DETERMINISTIC,
    GenerationParams,
)
from src.infra.llm.resilience import RotatingKeyPool
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

# Alias tương thích test / import cũ.
_BACKENDS = BACKENDS
_RotatingKeyPool = RotatingKeyPool
_llm_model_label = llm_model_label

__all__ = [
    "BACKENDS",
    "_BACKENDS",
    "RotatingKeyPool",
    "_RotatingKeyPool",
    "_pool",
    "clear_key_pool",
    "get_backend",
    "get_client",
    "mark_current_key_limited",
    "base_llm",
    "invoke_text",
    "invoke_with_tools",
    "invoke_structured",
    "ping",
    "use_offline_tools",
    "llm_model_label",
    "_llm_model_label",
    "GenerationParams",
    "DETERMINISTIC",
    "BALANCED",
    "CREATIVE",
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
