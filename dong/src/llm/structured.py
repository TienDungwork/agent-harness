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
) -> T:
    """Gọi LLM với structured output; trả về instance `schema`."""
    try:
        llm = base_llm(model_override=model_override, backend_override=backend_override)
        structured = llm.with_structured_output(schema)
        result = structured.invoke(messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
    except ValidationError as e:
        raise RuntimeError(f"LLM structured output không khớp schema {schema.__name__}: {e}") from e
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Lỗi LLM structured ({schema.__name__}): không thể sinh phản hồi. Chi tiết: {e}"
        ) from e
