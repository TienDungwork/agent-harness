"""Pytest defaults — bật memory trong test dù .env local tắt MEMORY_ENABLED."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_memory_layers_for_tests(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "memory_enabled", True, raising=False)
    monkeypatch.setattr(settings, "memory_short_term_enabled", True, raising=False)
    monkeypatch.setattr(settings, "memory_long_term_enabled", True, raising=False)
    monkeypatch.setattr(settings, "cache_enabled", True, raising=False)
