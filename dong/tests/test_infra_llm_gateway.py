"""Unit tests cho infra.llm.gateway — catalog, resolve model, cap tokens."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest

from src.infra.llm import gateway
from src.shared.config import settings


@pytest.fixture(autouse=True)
def _clear_catalog_cache():
    gateway.clear_gateway_catalog_cache()
    yield
    gateway.clear_gateway_catalog_cache()


def _mock_urlopen(payload: dict):
    body = json.dumps(payload).encode("utf-8")
    resp = BytesIO(body)
    resp.status = 200  # type: ignore[attr-defined]
    return resp


def test_resolve_model_and_cap_tokens_from_catalog(monkeypatch):
    monkeypatch.setattr(settings, "llm_backend", "self_hosted")
    monkeypatch.setattr(settings, "model_base_url", "http://gw.example/v1")
    monkeypatch.setattr(settings, "model_name", "bonsai-27b")
    catalog = {
        "data": [{"id": "bonsai-27b"}, {"id": "other"}],
        "limits": {"max_output_tokens": 8190},
    }
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(catalog)):
        assert gateway.resolve_self_hosted_model() == "bonsai-27b"
        assert gateway.cap_output_tokens(9000) == 8190
        assert gateway.cap_output_tokens(None) is None


def test_failed_catalog_not_cached(monkeypatch):
    monkeypatch.setattr(settings, "model_base_url", "http://gw.example/v1")
    calls = {"n": 0}

    def _fail(*_a, **_k):
        calls["n"] += 1
        raise OSError("connection refused")

    with patch("urllib.request.urlopen", side_effect=_fail):
        r1 = gateway.fetch_gateway_catalog()
        r2 = gateway.fetch_gateway_catalog()
    assert r1.get("error") and r2.get("error")
    assert calls["n"] == 2


def test_successful_catalog_cached(monkeypatch):
    monkeypatch.setattr(settings, "model_base_url", "http://gw.example/v1")
    catalog = {"data": [{"id": "m1"}], "limits": {}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(catalog)) as mock_open:
        gateway.fetch_gateway_catalog()
        gateway.fetch_gateway_catalog()
    assert mock_open.call_count == 1
