"""Chat completion helpers — text / tools / stream trên LangChain `base_llm`."""

from __future__ import annotations

from collections.abc import Iterator

from src.infra.llm.client import base_llm, llm_model_label
from src.infra.llm.params import BALANCED, GenerationParams


def invoke_with_tools(messages, tools=None, model_override: str | None = None, backend_override: str | None = None):
    from src.domain.observability.tracing import add_request_tokens, extract_token_usage

    llm = base_llm(model_override=model_override, backend_override=backend_override)
    if tools:
        llm = llm.bind_tools(tools)
    try:
        response = llm.invoke(messages)
        add_request_tokens(extract_token_usage(response))
        return response
    except Exception as e:
        raise RuntimeError(f"Lỗi kết nối tới LLM: Không thể sinh phản hồi. Chi tiết: {e}") from e


def invoke_text(
    system_prompt: str,
    user_prompt: str,
    model_override: str | None = None,
    backend_override: str | None = None,
    max_tokens: int | None = None,
    *,
    params: GenerationParams | None = None,
    substep: str | None = "llm_text",
    stop: list[str] | None = None,
) -> str:
    """Lời gọi LLM text — Answer / SQL generate."""
    from src.domain.observability.tracing import llm_io_payload
    from src.domain.observability.tracing import add_request_tokens, current_span, extract_token_usage, trace_step

    gen = params or BALANCED
    mt = max_tokens if max_tokens is not None else gen.max_tokens
    meta = {"model_name": llm_model_label(backend_override), "temperature": gen.temperature}
    prompt_in = llm_io_payload(system_prompt or "", user_prompt or "", "")["input"]
    if mt is not None:
        prompt_in = {**prompt_in, "max_tokens": mt}

    def _call() -> tuple[str, dict[str, int]]:
        llm = base_llm(
            model_override=model_override,
            backend_override=backend_override,
            max_tokens_override=mt,
            params=gen,
        )
        if stop:
            llm = llm.bind(stop=stop)
        response = llm.invoke(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        )
        usage = extract_token_usage(response)
        add_request_tokens(usage)
        return (str(response.content or ""), usage)

    try:
        if substep:
            with trace_step(current_span(), substep, input=prompt_in, metadata=meta, as_type="generation") as box:
                text, usage = _call()
                payload = llm_io_payload(system_prompt or "", user_prompt or "", text)
                box["usage"] = usage
                box["input"] = payload["input"]
                box["output"] = payload["output"]
                box["model_name"] = meta["model_name"]
                return text
        text, _usage = _call()
        return text
    except Exception as e:
        raise RuntimeError(f"Lỗi kết nối tới LLM: Không thể sinh phản hồi. Chi tiết: {e}") from e


def chat_stream(
    system_prompt: str,
    user_prompt: str,
    model_override: str | None = None,
    backend_override: str | None = None,
    max_tokens: int | None = None,
    *,
    params: GenerationParams | None = None,
    stop: list[str] | None = None,
) -> Iterator[str]:
    """Streaming sync — yield từng token (dùng với ``trace_stream`` như vn-stock)."""
    gen = params or BALANCED
    mt = max_tokens if max_tokens is not None else gen.max_tokens
    llm = base_llm(
        model_override=model_override,
        backend_override=backend_override,
        max_tokens_override=mt,
        params=gen,
    )
    if stop:
        llm = llm.bind(stop=stop)
    try:
        for chunk in llm.stream(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        ):
            delta = getattr(chunk, "content", None)
            if delta:
                yield str(delta)
    except Exception as e:
        raise RuntimeError(f"Lỗi kết nối tới LLM: Không thể sinh phản hồi. Chi tiết: {e}") from e
