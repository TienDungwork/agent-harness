"""Generation parameters — gom temperature / max_tokens / top_p theo task.

Giống vn-stock-swarm `infra/llm/params.py`: mỗi request chọn preset thay vì
override rải rác trong caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.shared.settings import settings


class GenerationParams(BaseModel):
    """Tham số sinh text cho ChatOpenAI / OpenAI-compatible."""

    temperature: float = Field(default_factory=lambda: settings.llm_temperature)
    max_tokens: int | None = None
    top_p: float | None = Field(default_factory=lambda: settings.llm_top_p)

    def to_langchain_kwargs(self) -> dict:
        """Map sang kwargs ChatOpenAI / SafeChatOpenAI."""
        out: dict = {"temperature": self.temperature}
        if self.max_tokens is not None:
            out["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            out["top_p"] = self.top_p
        return out

    def to_openai_kwargs(self) -> dict:
        """Map sang OpenAI Chat Completions API (async_client / SDK)."""
        return self.to_langchain_kwargs()


# Preset — chọn temperature theo task (giống vn-stock).
DETERMINISTIC = GenerationParams(temperature=0.0)  # SQL, structured, fact extraction
BALANCED = GenerationParams(temperature=0.5)  # chatbot, Q&A / respond
CREATIVE = GenerationParams(temperature=0.9)  # brainstorming, creative writing
