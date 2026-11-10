"""Preset GenerationParams — tách SQL deterministic vs respond."""

from src.infra.llm.params import DETERMINISTIC, GenerationParams, RESPOND, TASK
from src.shared.config import settings


def test_deterministic_is_zero_temp():
    assert DETERMINISTIC.temperature == 0.0


def test_respond_uses_respond_temperature_setting():
    assert RESPOND.temperature == settings.llm_respond_temperature


def test_task_uses_default_temperature():
    assert TASK.temperature == settings.llm_temperature


def test_to_langchain_kwargs_omits_none_max_tokens():
    kw = GenerationParams(temperature=0.3).to_langchain_kwargs()
    assert kw["temperature"] == 0.3
    assert "max_tokens" not in kw


def test_to_langchain_kwargs_includes_max_tokens_when_set():
    kw = GenerationParams(temperature=0.0, max_tokens=128).to_langchain_kwargs()
    assert kw["temperature"] == 0.0
    assert kw["max_tokens"] == 128
