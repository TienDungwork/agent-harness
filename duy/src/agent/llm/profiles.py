from __future__ import annotations

from dataclasses import dataclass

from agent.config.settings import get_settings


@dataclass(frozen=True)
class LlmProfile:
    id: str
    label: str
    base_url: str
    model: str
    api_key: str
    think: bool = False


def list_profiles() -> list[LlmProfile]:
    s = get_settings()
    profiles = [
        LlmProfile(
            id="local-8b",
            label="Local · qwen3-16k-nothink",
            base_url=s.llm_base_url.rstrip("/"),
            model=s.llm_model,
            api_key=s.llm_api_key,
            think=False,
        ),
    ]
    remote_url = (s.llm_remote_base_url or "").strip()
    remote_model = (s.llm_remote_model or "").strip()
    remote_key = (s.llm_remote_api_key or "").strip()
    if remote_url and remote_model and remote_key:
        profiles.append(
            LlmProfile(
                id="remote-4b",
                label=s.llm_remote_label or "Remote · qwen3:4b (192.168.1.198)",
                base_url=remote_url.rstrip("/"),
                model=remote_model,
                api_key=remote_key,
                think=False,
            )
        )
    return profiles


def default_profile_id() -> str:
    s = get_settings()
    preferred = (s.llm_default_profile or "").strip()
    ids = {p.id for p in list_profiles()}
    if preferred and preferred in ids:
        return preferred
    if "remote-4b" in ids:
        return "remote-4b"
    return list_profiles()[0].id


def resolve_profile(model_id: str | None = None) -> LlmProfile:
    profiles = list_profiles()
    by_id = {p.id: p for p in profiles}
    if model_id and model_id in by_id:
        return by_id[model_id]
    return by_id[default_profile_id()]


def profiles_public() -> list[dict[str, str]]:
    return [
        {"id": p.id, "label": p.label, "model": p.model}
        for p in list_profiles()
    ]
