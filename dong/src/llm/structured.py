"""Structured LLM — mọi call v5 qua Pydantic schema."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.client import base_llm

T = TypeVar("T", bound=BaseModel)


def invoke_structured(
    messages,
    schema: type[T],
    *,
    model_override: str | None = None,
    backend_override: str | None = None,
    substep: str | None = None,
) -> T:
    """Gọi LLM với structured output; trả về instance `schema`."""
    from src.config import settings
    from src.llm.client import _llm_model_label
    from src.monitoring.tracing import trace_substep

    step_name = substep or schema.__name__

    def _call() -> T:
        llm = base_llm(model_override=model_override, backend_override=backend_override)
        structured = llm.with_structured_output(schema)
        result = structured.invoke(messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)

    meta = {"model_name": _llm_model_label(backend_override), "temperature": settings.llm_temperature}
    try:
        with trace_substep(step_name, kind="agent", input={"schema": schema.__name__}, metadata=meta) as box:
            out = _call()
            box["output"] = out.model_dump() if hasattr(out, "model_dump") else str(out)
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
