"""Lean local VMS/SSH agent: short system prompt, FinishTool only, NoOp condenser.

``OpenHandsAgentSettings`` has no ``system_prompt`` / ``include_default_tools``
fields, so gateway lean create cannot pass them through. ``create_agent()``
always wires the full ~16KB SDK coding prompt + ThinkTool + LLM condenser —
that alone makes LAN Ollama several times slower than a direct API call.

When ``agent_context.system_message_suffix`` contains ``<LOCAL_HARNESS>``
(injected by local-gateway), replace the Agent with a lean copy.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PATCH_ATTR = "_creanova_lean_local_agent"

_LEAN_SOUL_FALLBACK = """\
<SOUL>
You are Creanova, a local AI assistant on this machine via Agent Canvas.
ALWAYS reply in Vietnamese. Short answers. Prefer tools over guessing.
CẤM invent params (no security_risk, no summary). Có reply_vi → copy rồi FinishTool.
</SOUL>"""


def _load_soul() -> str:
    for path in (
        Path("/home/openhands/.Creanova/SOUL.md"),
        Path("/home/openhands/.openhands/SOUL.md"),
    ):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            continue
        if text.startswith("<SOUL>"):
            return text
        return f"<SOUL>\n{text}\n</SOUL>"
    return _LEAN_SOUL_FALLBACK


def _is_lean(settings: object) -> bool:
    ctx = getattr(settings, "agent_context", None)
    suffix = getattr(ctx, "system_message_suffix", None) or ""
    return "<LOCAL_HARNESS>" in str(suffix)


def _install() -> None:
    try:
        from openhands.sdk.context.agent_context import AgentContext
        from openhands.sdk.context.condenser import NoOpCondenser
        from openhands.sdk.settings.model import OpenHandsAgentSettings
    except ImportError:
        try:
            from Creanova.sdk.context.agent_context import AgentContext  # type: ignore
            from Creanova.sdk.context.condenser import NoOpCondenser  # type: ignore
            from Creanova.sdk.settings.model import (  # type: ignore
                OpenHandsAgentSettings,
            )
        except ImportError:
            logger.warning("patch_lean_local_agent: settings model not found")
            return

    original = OpenHandsAgentSettings.create_agent
    if getattr(original, _PATCH_ATTR, False):
        return

    def _tiny_clock_suffix() -> str:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone(timedelta(hours=7)))
        return (
            f"CLOCK: {now.strftime('%d/%m/%Y %H:%M')} UTC+7. "
            f'Hôm nay theo mốc này.'
        )

    def create_agent(self):  # type: ignore[no-untyped-def]
        agent = original(self)
        if not _is_lean(self):
            return agent
        try:
            # SOUL already has VMS/SSH rules — drop the long LOCAL_HARNESS copy
            # from dynamic context (was ~1KB+ and inflated every prefill).
            lean_ctx = AgentContext(
                skills=[],
                load_public_skills=False,
                load_user_skills=False,
                load_project_skills=False,
                system_message_suffix=_tiny_clock_suffix(),
            )
            return agent.model_copy(
                update={
                    "system_prompt": _load_soul(),
                    "include_default_tools": ["FinishTool"],
                    "condenser": NoOpCondenser(),
                    "enable_switch_llm_tool": False,
                    "agent_context": lean_ctx,
                    "system_prompt_kwargs": {
                        **dict(getattr(agent, "system_prompt_kwargs", None) or {}),
                        "llm_security_analyzer": False,
                        "enable_browser": False,
                    },
                    "security_policy_filename": "",
                }
            )
        except Exception:  # noqa: BLE001
            logger.exception("patch_lean_local_agent: lean model_copy failed")
            return agent

    setattr(create_agent, _PATCH_ATTR, True)
    OpenHandsAgentSettings.create_agent = create_agent  # type: ignore[method-assign]
    logger.info("patch_lean_local_agent: create_agent wraps LOCAL_HARNESS → lean")


_install()
