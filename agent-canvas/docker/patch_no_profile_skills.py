"""Disable profile skill catalog for the local VMS/SSH agent.

Creanova profile launch calls ``discover_profile_skills()`` which merges ~60
public coding skills into ``agent_context.skills`` (~480KB). That alone
exceeds LiteLLM project message limits on small LAN models.

Loaded via ``--import-modules`` next to ``patch_vms_reply_vi_finish``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _install() -> None:
    try:
        from openhands.agent_server import skills_service as ss
    except ImportError:
        try:
            from Creanova.agent_server import skills_service as ss  # type: ignore
        except ImportError:
            logger.warning("patch_no_profile_skills: skills_service not found")
            return

    if getattr(ss.discover_profile_skills, "_creanova_no_skills", False):
        return

    def _empty_catalog() -> list:
        return []

    _empty_catalog._creanova_no_skills = True  # type: ignore[attr-defined]
    ss.discover_profile_skills = _empty_catalog  # type: ignore[assignment]
    logger.info("patch_no_profile_skills: discover_profile_skills → []")


_install()
