"""Prompt lint — CI validation cho `resource/prompts/` (pattern llm-engineer-demo / vn-stock)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from src.infra.prompts.registry import _required_vars, resolve_prompts_dir

REQUIRED_META = ("name", "version", "model", "owner", "changelog", "template")


class LintIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _load_yaml(path: Path) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return {"__parse_error__": str(exc)}
    return data if isinstance(data, dict) else {}


def lint_prompt_file(path: Path, *, prompt_name: str) -> list[LintIssue]:
    rel = str(path)
    issues: list[LintIssue] = []
    data = _load_yaml(path)
    if data is None:
        return [LintIssue(path=rel, message="YAML không phải object")]
    if "__parse_error__" in data:
        return [LintIssue(path=rel, message=f"YAML parse error: {data['__parse_error__']}")]

    for field in REQUIRED_META:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(LintIssue(path=rel, message=f"Thiếu hoặc rỗng metadata '{field}'"))

    file_version = path.stem[1:] if path.stem.startswith("v") else None
    if file_version and file_version.isdigit():
        yaml_version = data.get("version")
        if yaml_version is not None and int(yaml_version) != int(file_version):
            issues.append(
                LintIssue(
                    path=rel,
                    message=f"version trong YAML ({yaml_version}) != tên file (v{file_version})",
                )
            )

    yaml_name = str(data.get("name", "")).strip()
    if yaml_name and yaml_name != prompt_name:
        issues.append(
            LintIssue(path=rel, message=f"name '{yaml_name}' != thư mục prompt '{prompt_name}'")
        )

    template = str(data.get("template", ""))
    template_vars = _required_vars(template)
    declared = data.get("variables")
    if declared is not None:
        if not isinstance(declared, list):
            issues.append(LintIssue(path=rel, message="Trường 'variables' phải là list"))
        else:
            declared_set = {str(v).strip() for v in declared if str(v).strip()}
            if declared_set != template_vars:
                issues.append(
                    LintIssue(
                        path=rel,
                        message=(
                            f"variables khai báo {sorted(declared_set)} "
                            f"!= biến template {sorted(template_vars)}"
                        ),
                    )
                )
    return issues


def lint_prompts_dir(root: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    if not root.is_dir():
        return [LintIssue(path=str(root), message="Thư mục prompts không tồn tại")]

    for prompt_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        prompt_name = prompt_dir.name
        version_files = sorted(prompt_dir.glob("v*.yaml"))
        if not version_files:
            issues.append(LintIssue(path=str(prompt_dir), message="Không có file v*.yaml"))
            continue
        alias = prompt_dir / "production.txt"
        if not alias.is_file():
            issues.append(LintIssue(path=str(prompt_dir), message="Thiếu production.txt"))
        else:
            content = alias.read_text(encoding="utf-8").strip()
            cleaned = content.lstrip("vV") if content.lower().startswith("v") else content
            if not cleaned.isdigit() or "\n" in content or len(content) > 20:
                issues.append(
                    LintIssue(
                        path=str(alias),
                        message="production.txt phải chỉ chứa version (vd. v1), không full template",
                    )
                )

        for vf in version_files:
            issues.extend(lint_prompt_file(vf, prompt_name=prompt_name))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint prompt registry YAML files.")
    parser.add_argument(
        "prompts_dir",
        nargs="?",
        default=str(resolve_prompts_dir()),
        help="Đường dẫn tới resource/prompts/",
    )
    args = parser.parse_args(argv)
    root = Path(args.prompts_dir)
    issues = lint_prompts_dir(root)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"\n{len(issues)} lint error(s)", file=sys.stderr)
        return 1
    print(f"OK: {root} — all prompts passed lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
