"""Prompt Registry — Git-based prompt versioning & rendering system.

Quản lý prompt dưới dạng file YAML trong thư mục `resource/prompts/`.
Hỗ trợ load theo version (số nguyên) hoặc alias ("production" đọc từ production.txt).
Validate biến truyền vào template: raise ValueError nếu thiếu biến bắt buộc.
"""

from __future__ import annotations

import re
import string
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
            prompts_dir = Path(__file__).resolve().parent.parent.parent / "resource" / "prompts"
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
        alias_file = self.prompts_dir / name / "production.txt"
        if str(version).lower() == "production" and alias_file.exists():
            content = alias_file.read_text("utf-8").strip()
            # Nếu production.txt chứa nội dung template trực tiếp thay vì version identifier
            if "\n" in content or len(content) > 50:
                v1_file = self.prompts_dir / name / "v1.yaml"
                if v1_file.exists():
                    data = yaml.safe_load(v1_file.read_text("utf-8")) or {}
                    if isinstance(data, dict):
                        data["template"] = content
                        return Prompt(**data)
                return Prompt(name=name, version=1, template=content)

        resolved_ver = self._resolve_version(name, version)
        yaml_file = self.prompts_dir / name / f"v{resolved_ver}.yaml"
        if yaml_file.exists():
            data = yaml.safe_load(yaml_file.read_text("utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"Invalid YAML content in {yaml_file}")
            return Prompt(**data)

        raise FileNotFoundError(f"Prompt file for '{name}' version '{version}' (resolved v{resolved_ver}) not found at {yaml_file}")

    def _required_vars(self, template: str) -> list[str]:
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
        if not prompt.template or not prompt.template.strip():
            raise ValueError(f"Prompt '{name}' có template rỗng")

        required = self._required_vars(prompt.template)
        missing = [v for v in required if v not in kwargs]
        if missing:
            raise ValueError(f"Prompt '{name}' thiếu biến: {missing}")

        try:
            rendered = prompt.template.format(**kwargs)
        except (KeyError, IndexError) as e:
            key_name = str(e).strip("'\"")
            raise ValueError(f"Prompt '{name}' thiếu biến: ['{key_name}']") from e

        if not rendered or not rendered.strip():
            raise ValueError(f"Prompt '{name}' sau khi render có nội dung rỗng")

        unreplaced = re.findall(
            r"\{[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\w+\])*\}", rendered
        )
        if unreplaced:
            raise ValueError(
                f"Prompt '{name}' còn chứa placeholder chưa thay thế: {sorted(set(unreplaced))}"
            )

        return rendered


@lru_cache(maxsize=1)
def registry() -> PromptRegistry:
    return PromptRegistry()
