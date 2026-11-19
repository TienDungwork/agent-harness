"""Preset GenerationParams — DETERMINISTIC / BALANCED / CREATIVE."""

from src.infra.llm.params import BALANCED, CREATIVE, DETERMINISTIC, GenerationParams


def test_preset_temperatures():
    assert DETERMINISTIC.temperature == 0.0
    assert BALANCED.temperature == 0.5
    assert CREATIVE.temperature == 0.9


def test_to_langchain_kwargs_omits_none_max_tokens():
    kw = GenerationParams(temperature=0.3).to_langchain_kwargs()
    assert kw["temperature"] == 0.3
    assert "max_tokens" not in kw


def test_to_langchain_kwargs_includes_max_tokens_when_set():
    kw = GenerationParams(temperature=0.0, max_tokens=128).to_langchain_kwargs()
    assert kw["temperature"] == 0.0
    assert kw["max_tokens"] == 128
