"""Static-tier prompt sections ported verbatim from ``agent/prompts/system_prompt.j2``.

Each section owns its guard and renders text from ``bodies/<TAG>.md``. Bodies are the
exact blocks the template produced; ``tests/sdk/context/prompts/test_default_registry.py``
pins them byte-for-byte against the Phase 0 snapshot oracle. The cache tier is ``STATIC``
for every block here (the dynamic tier is ported separately).
"""

# Section bodies are verbatim long-form prompt text; wrapping a line would change
# the rendered bytes, so line-length (E501) is disabled for this whole file.
# ruff: noqa: E501

import re
from pathlib import Path
from typing import ClassVar

from Creanova.sdk.context.prompts.section import (
    CacheTier,
    Platform,
    PromptContext,
)


_BODIES_DIR = Path(__file__).resolve().parent / "bodies"


def _section(name: str) -> str:
    """Load a static prompt block from ``bodies/<name>.md``."""
    return (_BODIES_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


__all__ = [
    "BrowserSection",
    "CodeQualitySection",
    "EfficiencySection",
    "EnvironmentSetupSection",
    "ExternalServicesSection",
    "FileSystemSection",
    "MemorySection",
    "ModelSpecificSection",
    "ProblemSolvingSection",
    "ProcessManagementSection",
    "PullRequestsSection",
    "RoleSection",
    "SecurityRiskAssessmentSection",
    "SecuritySection",
    "SelfDocumentationSection",
    "SoulSection",
    "TroubleshootingSection",
    "VersionControlSection",
]


def _refine(text: str, platform: Platform) -> str:
    """Windows shell-term substitution, mirroring ``context.prompts.prompt.refine``.

    Kept for byte-for-byte parity with the live template; gated on ``ctx.platform``
    (not ``sys.platform``) so sections stay pure. Retired once ``ShellGuidanceSection``
    (#85) describes the bound shell tool directly.
    """
    if platform is Platform.WINDOWS:
        text = re.sub(r"\bterminal\b", "execute_powershell", text, flags=re.IGNORECASE)
        text = re.sub(
            r"(?<!execute_)(?<!_)\bbash\b", "powershell", text, flags=re.IGNORECASE
        )
    return text


class _StaticTextSection:
    """Base for a verbatim static block: a subclass sets ``name`` + ``body``.

    Guarded blocks override :meth:`guard`. ``render`` applies the platform shell
    refinement and nothing else, so the block is reproduced exactly.
    """

    cache_tier = CacheTier.STATIC
    name: str
    body: str

    def guard(self, ctx: PromptContext) -> bool:  # noqa: ARG002
        return True

    def render(self, ctx: PromptContext) -> str | None:  # noqa: ARG002
        return self.body


class SoulSection(_StaticTextSection):
    name = "soul"

    _DEFAULT_SOUL = (
        "You are Creanova agent, a helpful AI assistant that can interact"
        " with a computer to solve tasks."
    )

    def render(self, ctx: PromptContext) -> str | None:
        soul = str(ctx.template_kwargs.get("soul_content") or self._DEFAULT_SOUL)
        return f"<SOUL>\n{soul}\n</SOUL>"


class RoleSection(_StaticTextSection):
    name = "role"
    body = _section("ROLE")


class MemorySection(_StaticTextSection):
    name = "memory"
    body = _section("MEMORY")


class EfficiencySection(_StaticTextSection):
    name = "efficiency"
    body = _section("EFFICIENCY")

    def render(self, ctx: PromptContext) -> str | None:
        # Mentions "bash", which refine() rewrites to "powershell" on Windows.
        return _refine(self.body, ctx.platform)


class FileSystemSection(_StaticTextSection):
    name = "file_system"
    body = _section("FILE_SYSTEM_GUIDELINES")


class CodeQualitySection(_StaticTextSection):
    name = "code_quality"
    body = _section("CODE_QUALITY")


class VersionControlSection(_StaticTextSection):
    name = "version_control"
    body = _section("VERSION_CONTROL")


class PullRequestsSection(_StaticTextSection):
    name = "pull_requests"
    body = _section("PULL_REQUESTS")


class ProblemSolvingSection(_StaticTextSection):
    name = "problem_solving"
    body = _section("PROBLEM_SOLVING_WORKFLOW")


class SelfDocumentationSection(_StaticTextSection):
    name = "self_documentation"
    body = _section("SELF_DOCUMENTATION")


class SecuritySection(_StaticTextSection):
    """The ``<SECURITY>`` block: the built-in default policy, or a custom policy's
    ``security_policy_content`` when configured. Guarded by ``security_policy_filename``
    (empty string disables it).
    """

    name = "security"
    body = _section("SECURITY")

    def guard(self, ctx: PromptContext) -> bool:
        return bool(ctx.template_kwargs.get("security_policy_filename"))

    def render(self, ctx: PromptContext) -> str | None:
        content = ctx.template_kwargs.get("security_policy_content")
        # `is not None`: an explicitly empty custom policy must not fall back to body.
        if content is not None:
            return _refine(f"<SECURITY>\n\n{content}\n\n</SECURITY>", ctx.platform)
        return self.body


class SecurityRiskAssessmentSection:
    """``<SECURITY_RISK_ASSESSMENT>`` -- the LOW/MEDIUM/HIGH tiers swap with ``cli_mode``."""

    name = "security_risk_assessment"
    cache_tier = CacheTier.STATIC

    def guard(self, ctx: PromptContext) -> bool:
        return bool(ctx.template_kwargs.get("llm_security_analyzer"))

    def render(self, ctx: PromptContext) -> str | None:
        # cli_mode defaults to True, matching the template's `cli_mode | default(true)`
        # (note ctx.cli_mode would default False).
        cli = bool(ctx.template_kwargs.get("cli_mode", True))
        name = "SECURITY_RISK_ASSESSMENT" if cli else "SECURITY_RISK_ASSESSMENT.sandbox"
        return _refine(_section(name), ctx.platform)


class BrowserSection(_StaticTextSection):
    name = "browser"
    body = _section("BROWSER_TOOLS")

    def guard(self, ctx: PromptContext) -> bool:
        return ctx.enable_browser


class ExternalServicesSection(_StaticTextSection):
    name = "external_services"
    body = _section("EXTERNAL_SERVICES")


class EnvironmentSetupSection(_StaticTextSection):
    name = "environment_setup"
    body = _section("ENVIRONMENT_SETUP")


class TroubleshootingSection(_StaticTextSection):
    name = "troubleshooting"
    body = _section("TROUBLESHOOTING")


class ProcessManagementSection(_StaticTextSection):
    name = "process_management"
    body = _section("PROCESS_MANAGEMENT")


class ModelSpecificSection:
    """``<IMPORTANT>`` -- selects the family + variant guidance for the model."""

    name = "model_specific"
    cache_tier = CacheTier.STATIC

    # <IMPORTANT> bodies keyed by the family/variant that ``get_model_prompt_spec``
    # resolves. Ported from ``model_specific/*.j2``.
    _IMPORTANT_BY_FAMILY: ClassVar[dict[str, str]] = {
        "anthropic_claude": """\
* Try to follow the instructions exactly as given - don't make extra or fewer actions if not asked.
* Avoid unnecessary defensive programming; do not add redundant fallbacks or default values — fail fast instead of masking misconfigurations.
* When backward compatibility expectations are unclear, confirm with the user before making changes that could break existing behavior.""",
        "google_gemini": """\
* Avoid being too proactive. Fulfill the user's request thoroughly: if they ask questions/investigations, answer them; if they ask for implementations, provide them. But do not take extra steps beyond what is requested.""",
    }

    _IMPORTANT_BY_VARIANT: ClassVar[dict[str, str]] = {
        "gpt-5": """\
## Communicate with the user

* Stream your thinking and responses while staying concise; surface key assumptions and environment prerequisites explicitly.
* ALWAYS send a brief preamble to the user explaining what you're about to do before each tool call, using 8 - 12 words, with a friendly and curious tone.
* You have access to external resources and should actively use available tools to try accessing them first, rather than claiming you can’t access something without making an attempt.

## Replying to GitHub inline review threads (PR review comments)

To reply in an existing inline thread, use the REST API:
- List comments (incl. inline threads):
  - `GET /repos/{owner}/{repo}/pulls/{pull_number}/comments?per_page=100`
  - Top-level inline comments have `in_reply_to_id = null`.
  - Replies have `in_reply_to_id = <top_level_comment_id>`.
- Post a threaded reply:
  - `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments`
  - body: `{ "body": "...", "in_reply_to": <comment_id> }`

This creates a proper reply attached to the original inline comment thread.""",
        "gpt-5-codex": """\
* Stream your thinking and responses while staying concise; surface key assumptions and environment prerequisites explicitly.
* You have access to external resources and should actively use available tools to try accessing them first, rather than claiming you can’t access something without making an attempt.""",
    }

    def guard(self, ctx: PromptContext) -> bool:
        return bool(ctx.model_family)

    def render(self, ctx: PromptContext) -> str | None:
        family = ctx.model_family or ""
        variant = str(ctx.template_kwargs.get("model_variant") or "")
        body = (
            self._IMPORTANT_BY_FAMILY.get(family, "")
            + self._IMPORTANT_BY_VARIANT.get(variant, "")
        ).strip()
        if not body:
            return None
        return f"<IMPORTANT>\n{body}\n</IMPORTANT>"
