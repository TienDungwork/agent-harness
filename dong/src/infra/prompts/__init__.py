"""Prompt management — git YAML registry (tương tự llm-engineer-demo `app/prompts/`).

- Code: `registry`, `lint`, `experiment`
- Data: `resource/prompts/<name>/vN.yaml` + `production.txt` (alias version)
"""

from src.infra.prompts.experiment import (
    bind_prompt_version,
    current_prompt_version,
    pick_prompt_version,
    reset_prompt_version,
    resolve_prompt_version,
)
from src.infra.prompts.registry import (
    Prompt,
    PromptRegistry,
    registry,
    resolve_prompts_dir,
)

__all__ = [
    "Prompt",
    "PromptRegistry",
    "bind_prompt_version",
    "current_prompt_version",
    "pick_prompt_version",
    "registry",
    "reset_prompt_version",
    "resolve_prompt_version",
    "resolve_prompts_dir",
]
