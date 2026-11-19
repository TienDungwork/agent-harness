"""Backend presets — OpenAI Cloud hoặc self_hosted (vLLM gateway OpenAI-compatible)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Backend:
    name: str
    default_base_url: str  # "" = SDK mặc định OpenAI Cloud
    requires_real_key: bool
    dummy_key: str = "not-needed"


BACKENDS: dict[str, Backend] = {
    "openai": Backend(name="openai", default_base_url="", requires_real_key=True),
    "self_hosted": Backend(
        name="self_hosted",
        default_base_url="http://192.168.1.198:18083/v1",
        requires_real_key=False,
        dummy_key="",
    ),
}


def get_backend(name: str) -> Backend:
    key = (name or "").strip().lower()
    if key not in BACKENDS:
        raise ValueError(
            f"LLM_BACKEND='{name}' không hợp lệ. Chọn một trong: {', '.join(BACKENDS)}."
        )
    return BACKENDS[key]
