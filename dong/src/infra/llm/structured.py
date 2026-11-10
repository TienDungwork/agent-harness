"""Structured LLM — mọi call v5 qua Pydantic schema."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.infra.llm.client import base_llm
from src.infra.llm.params import DETERMINISTIC, GenerationParams

T = TypeVar("T", bound=BaseModel)


def invoke_structured(
    messages,
    schema: type[T],
    *,
    model_override: str | None = None,
    backend_override: str | None = None,
    substep: str | None = None,
    params: GenerationParams | None = None,
) -> T:
    """Gọi LLM với structured output; trả về instance `schema`."""
    from src.infra.llm.client import _llm_model_label
    from src.infra.monitoring.tracing import current_span, trace_step

    gen = params or DETERMINISTIC
    step_name = substep or schema.__name__

    def _call() -> T:
        llm = base_llm(model_override=model_override, backend_override=backend_override, params=gen)
        structured = llm.with_structured_output(schema)
        result = structured.invoke(messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)

    from src.infra.monitoring.trace_payload import redact_text

    meta = {"model_name": _llm_model_label(backend_override), "temperature": gen.temperature}
    trace_in: dict = {"schema": schema.__name__}
    if isinstance(messages, list):
        safe_msgs = []
        for m in messages:
            if isinstance(m, dict) and "content" in m:
                role = m["role"] if "role" in m else ""
                safe_msgs.append({"role": role, "content": redact_text(str(m["content"]))})
            else:
                safe_msgs.append(redact_text(str(m)))
        trace_in["messages"] = safe_msgs
    try:
        with trace_step(current_span(), step_name, input=trace_in, metadata=meta, as_type="generation") as box:
            out = _call()
            dumped = out.model_dump() if hasattr(out, "model_dump") else str(out)
            box["output"] = dumped
            box["model_name"] = meta["model_name"]
            return out
    except ValidationError as e:
        raise RuntimeError(f"LLM structured output không khớp schema {schema.__name__}: {e}") from e
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Lỗi LLM structured ({schema.__name__}): không thể sinh phản hồi. Chi tiết: {e}"
        ) from e
