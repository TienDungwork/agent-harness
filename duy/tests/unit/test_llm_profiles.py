from agent.config.settings import get_settings
from agent.llm.profiles import default_profile_id, list_profiles, resolve_profile
from agent.llm.provider import get_llm
from agent.llm.runtime import get_llm_profile, reset_llm_profile, set_llm_profile


def test_profiles_include_local_and_remote_when_configured(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_REMOTE_BASE_URL", "http://192.168.1.198:8080/v1")
    monkeypatch.setenv("LLM_REMOTE_MODEL", "qwen3:4b-q4_K_M")
    monkeypatch.setenv("LLM_REMOTE_API_KEY", "test-key")
    monkeypatch.setenv("LLM_DEFAULT_PROFILE", "remote-4b")
    get_settings.cache_clear()

    ids = [p.id for p in list_profiles()]
    assert "local-8b" in ids
    assert "remote-4b" in ids
    assert default_profile_id() == "remote-4b"
    remote = resolve_profile("remote-4b")
    assert remote.model == "qwen3:4b-q4_K_M"
    assert remote.base_url.endswith("/v1")


def test_get_llm_uses_runtime_profile(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_REMOTE_BASE_URL", "http://192.168.1.198:8080/v1")
    monkeypatch.setenv("LLM_REMOTE_MODEL", "qwen3:4b-q4_K_M")
    monkeypatch.setenv("LLM_REMOTE_API_KEY", "test-key")
    get_settings.cache_clear()

    profile = resolve_profile("remote-4b")
    token = set_llm_profile(profile)
    try:
        assert get_llm_profile().id == "remote-4b"
        llm = get_llm(max_tokens=8)
        assert llm.model_name == "qwen3:4b-q4_K_M"
    finally:
        reset_llm_profile(token)
