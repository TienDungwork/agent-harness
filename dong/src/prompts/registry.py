"""Prompt Registry — Git-based prompt versioning & rendering system.

Quản lý prompt dưới dạng file YAML trong thư mục `prompts/`.
Hỗ trợ load theo version (số nguyên) hoặc alias ("production" đọc từ production.txt).
Validate biến truyền vào template: raise ValueError nếu thiếu biến bắt buộc.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Prompt(BaseModel):
    name: str
    version: int
    template: str
    description: str = ""
    owner: str = ""
    created: str = ""
    changelog: str = ""
    model: str = ""


class PromptRegistry:
    def __init__(self, prompts_dir: Path | str | None = None):
        if prompts_dir is None:
            # mặc định: <repo_root>/prompts
            prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        self.prompts_dir = Path(prompts_dir)

    def _resolve_version(self, name: str, version: int | str) -> int | str:
        ver_str = str(version).strip()
        if ver_str.lower() == "production":
            alias_file = self.prompts_dir / name / "production.txt"
            if not alias_file.exists():
                raise FileNotFoundError(f"Production alias for prompt '{name}' not found at {alias_file}")
            ver_str = alias_file.read_text("utf-8").strip()

        if ver_str.lower().startswith("v") and ver_str[1:].isdigit():
            ver_str = ver_str[1:]

        # Thử ép sang int nếu là chuỗi số
        if ver_str.isdigit():
            return int(ver_str)
        return ver_str

    def get(self, name: str, version: int | str = "production") -> Prompt:
        resolved_ver = self._resolve_version(name, version)
        yaml_file = self.prompts_dir / name / f"v{resolved_ver}.yaml"
        if not yaml_file.exists():
            raise FileNotFoundError(f"Prompt file for '{name}' version '{version}' (resolved v{resolved_ver}) not found at {yaml_file}")

        data = yaml.safe_load(yaml_file.read_text("utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML content in {yaml_file}")

        return Prompt(**data)

    def _required_vars(self, template: str) -> list[str]:
        import string

        required: list[str] = []
        formatter = string.Formatter()
        for _, field_name, _, _ in formatter.parse(template):
            if field_name is not None:
                # Lấy tên biến gốc nếu có attribute/index (vd. obj.attr -> obj)
                var_name = field_name.split(".")[0].split("[")[0]
                if var_name and var_name not in required:
                    required.append(var_name)
        return required

    def render(self, name: str, version: int | str = "production", **kwargs) -> str:
        prompt = self.get(name, version)
        required = self._required_vars(prompt.template)
        missing = [v for v in required if v not in kwargs]
        if missing:
            raise ValueError(f"Thiếu biến khi render prompt: {missing}")

        return prompt.template.format(**kwargs)


@lru_cache(maxsize=1)
def registry() -> PromptRegistry:
    return PromptRegistry()
