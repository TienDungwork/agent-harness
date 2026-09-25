from __future__ import annotations

from langchain_openai import ChatOpenAI

from agent.llm.runtime import get_llm_profile


def get_llm(*, temperature: float = 0.0, max_tokens: int | None = None) -> ChatOpenAI:
    profile = get_llm_profile()
    kwargs: dict = {
        "base_url": profile.base_url.rstrip("/"),
        "api_key": profile.api_key,
        "model": profile.model,
        "temperature": temperature,
    }
    # Chỉ ép think=false trên Ollama local; gateway remote (198) trả rỗng nếu gửi think=false.
    if profile.id.startswith("local") and not profile.think:
        kwargs["extra_body"] = {"think": False}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)
