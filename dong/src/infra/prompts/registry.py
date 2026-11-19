"""Prompt Registry git-based — pattern llm-engineer-demo / vn-stock-swarm.

Đọc `resource/prompts/<name>/vN.yaml` + alias `production.txt` (chỉ chứa version,
vd. `v1` — không nhét full template vào alias).
Template: `str.format` (`{var}`).
"""

from __future__ import annotations

import string
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


def resolve_prompts_dir() -> Path:
    """Tìm `resource/prompts/` — local / Docker / cwd."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "resource" / "prompts",
        Path("/app/resource/prompts"),
        Path.cwd() / "resource" / "prompts",
        Path.cwd() / "prompts",
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand
    return candidates[0]


class Prompt(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    template: str
    description: str = ""
    owner: str = ""
    created: str = ""
    changelog: str = ""
    model: str = ""


def _required_vars(template: str) -> set[str]:
    """Tên biến `{var}` trong template (string.Formatter)."""
    names: set[str] = set()
    for _, field_name, _, _ in string.Formatter().parse(template):
        if not field_name:
            continue
        var = field_name.split(".", 1)[0].split("[", 1)[0]
        if var:
            names.add(var)
    return names


class PromptRegistry:
    """Interface: `get(name, version)` / `render(name, version, **vars)`."""

    def __init__(self, prompts_dir: Path | str | None = None) -> None:
        self.prompts_dir = Path(prompts_dir) if prompts_dir is not None else resolve_prompts_dir()

    def _resolve_version(self, name: str, version: int | str) -> int:
        if isinstance(version, int):
            return version
        text = str(version).strip()
        if text.isdigit():
            return int(text)
        lowered = text.lower()
        if lowered.startswith("v") and lowered[1:].isdigit():
            return int(lowered[1:])
        if lowered == "production":
            alias_file = self.prompts_dir / name / "production.txt"
            try:
                content = alias_file.read_text(encoding="utf-8").strip()
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    f"Production alias for prompt '{name}' not found at {alias_file}"
                ) from exc
            cleaned = content.lstrip("vV") if content.lower().startswith("v") else content
            if cleaned.isdigit():
                return int(cleaned)
            raise ValueError(
                f"production.txt của '{name}' phải là version (vd. v1), không phải full template"
            )
        if lowered == "latest":
            versions = sorted(
                int(p.stem[1:])
                for p in (self.prompts_dir / name).glob("v*.yaml")
                if p.stem.startswith("v") and p.stem[1:].isdigit()
            )
            if not versions:
                raise ValueError(f"Không có version nào cho prompt '{name}'")
            return versions[-1]
        raise ValueError(f"Alias version không hỗ trợ: {version!r}")

    def _load(self, name: str, version: int) -> Prompt:
        path = self.prompts_dir / name / f"v{version}.yaml"
        if not path.is_file():
            raise FileNotFoundError(
                f"Prompt file for '{name}' version '{version}' not found at {path}"
            )
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "template" not in data:
            raise ValueError(f"Invalid YAML content in {path}")
        return Prompt(
            name=str(data.get("name", name)),
            version=int(data.get("version", version)),
            template=str(data["template"]),
            description=str(data.get("description", "")),
            owner=str(data.get("owner", "")),
            created=str(data.get("created", "")),
            changelog=str(data.get("changelog", "")),
            model=str(data.get("model", "")),
        )

    def get(self, name: str, version: int | str | None = None) -> Prompt:
        """`version=None` → ContextVar A/B (hoặc production). Thiếu file B → fallback production."""
        from src.infra.prompts.experiment import current_prompt_version

        ver: int | str = current_prompt_version() if version is None else version
        try:
            return self._load(name, self._resolve_version(name, ver))
        except FileNotFoundError:
            # shortcut: A/B chỉ có v2 cho vài prompt; prompt khác giữ production
            if ver in ("production", "latest") or ver == 1 or str(ver).lower() in ("v1", "1"):
                raise
            return self._load(name, self._resolve_version(name, "production"))

    def render(self, name: str, version: int | str | None = None, **kwargs: object) -> str:
        prompt = self.get(name, version)
        if not prompt.template or not prompt.template.strip():
            raise ValueError(f"Prompt '{name}' có template rỗng")
        missing = sorted(v for v in _required_vars(prompt.template) if v not in kwargs)
        if missing:
            raise ValueError(f"Prompt '{name}' thiếu biến: {missing}")
        try:
            rendered = prompt.template.format(**kwargs)
        except (KeyError, IndexError) as exc:
            key_name = str(exc).strip("'\"")
            raise ValueError(f"Prompt '{name}' thiếu biến: ['{key_name}']") from exc
        if not rendered.strip():
            raise ValueError(f"Prompt '{name}' sau khi render có nội dung rỗng")
        return rendered


@lru_cache(maxsize=1)
def registry() -> PromptRegistry:
    return PromptRegistry()
