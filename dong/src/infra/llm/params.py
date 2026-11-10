"""Generation parameters — gom temperature / max_tokens / top_p theo task.

Giống vn-stock-swarm `infra/llm/params.py`: mỗi request chọn preset thay vì
override rải rác trong caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.shared.config import settings


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


# Preset theo task — SQL/cấu trúc vs diễn giải câu trả lời.
DETERMINISTIC = GenerationParams(temperature=0.0)  # text-to-SQL, repair, structured
TASK = GenerationParams()  # mặc định pipeline (LLM_TEMPERATURE)
RESPOND = GenerationParams(temperature=settings.llm_respond_temperature)  # respond_stat / inline
