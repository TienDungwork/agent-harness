from contextvars import copy_context

from agent.llm.profiles import resolve_profile
from agent.llm.runtime import get_llm_profile, reset_llm_profile, set_llm_profile


def test_reset_llm_profile_safe_across_contexts():
    profile = resolve_profile("local-8b")
    token_holder: dict = {}

    def _set():
        token_holder["token"] = set_llm_profile(profile)
        assert get_llm_profile().id == "local-8b"

    copy_context().run(_set)
    # Reset từ context khác — trước đây raise ValueError ContextVar.
    reset_llm_profile(token_holder["token"])
