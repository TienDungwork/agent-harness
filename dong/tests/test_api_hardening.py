"""API hardening — access key, long-term flag, recall SQL cap."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.shared.config import settings

client = TestClient(app)


def test_api_access_key_blocks_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "api_access_key", "secret-key")
    res = client.get("/api/memory?user_id=u1")
    assert res.status_code == 401
    res_ok = client.get("/api/memory?user_id=u1", headers={"X-API-Key": "secret-key"})
    assert res_ok.status_code in (200, 400)


def test_api_health_without_key_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "api_access_key", "secret-key")
    res = client.get("/api/health")
    assert res.status_code == 200


def test_memory_api_disabled_when_long_term_off(monkeypatch):
    monkeypatch.setattr(settings, "memory_long_term_enabled", False)
    monkeypatch.setattr(settings, "memory_enabled", True)
    res = client.get("/api/memory?user_id=test_user")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "disabled"
    assert data["facts"] == []


def test_recall_long_term_uses_qdrant_query(monkeypatch):
    from src.infra.memory import qdrant_longterm

    monkeypatch.setattr(qdrant_longterm.settings, "memory_long_term_enabled", True)
    monkeypatch.setattr(qdrant_longterm.settings, "qdrant_url", "http://localhost:6333")
    calls: dict = {}

    class FakeClient:
        def collection_exists(self, name):
            return True

        def query_points(self, **kwargs):
            calls.update(kwargs)
            return type("R", (), {"points": []})()

    monkeypatch.setattr(qdrant_longterm, "get_qdrant_client", lambda: FakeClient())
    monkeypatch.setattr(qdrant_longterm, "_embed_texts", lambda texts: [[0.1] * 3])
    qdrant_longterm.recall_long_term("u1", "câu hỏi có từ khóa", k=3)
    assert calls.get("limit") == 3
