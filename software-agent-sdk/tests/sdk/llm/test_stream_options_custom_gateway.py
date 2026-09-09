"""Custom OpenAI-compatible gateways reject LiteLLM stream_options."""

from pydantic import SecretStr

from Creanova.sdk.llm import LLM


def test_prepare_transport_kwargs_omits_stream_options_for_custom_base_url():
    """LAN OpenAI-compatible gateways 400 on stream_options (param=stream_options)."""
    llm = LLM(
        usage_id="test-llm",
        model="openai/qwen3-4b",
        api_key=SecretStr("test_key"),
        base_url="http://192.168.1.196:18083/v1",
        num_retries=1,
        retry_min_wait=1,
        retry_max_wait=2,
    )
    kwargs = llm._prepare_transport_kwargs(
        messages=[{"role": "user", "content": "Hello"}],
        enable_streaming=True,
    )
    assert "stream_options" not in kwargs
    assert "stream_options" in (kwargs.get("additional_drop_params") or [])


def test_prepare_transport_kwargs_keeps_stream_options_without_base_url():
    llm = LLM(
        usage_id="test-llm",
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=1,
        retry_min_wait=1,
        retry_max_wait=2,
    )
    kwargs = llm._prepare_transport_kwargs(
        messages=[{"role": "user", "content": "Hello"}],
        enable_streaming=True,
    )
    assert kwargs.get("stream_options") == {"include_usage": True}
