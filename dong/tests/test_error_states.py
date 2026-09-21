"""Unit tests for Phase 6: Error States (DB Connection Loss, Model Timeout, Rate Limits)."""

from __future__ import annotations

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.main import _format_error_message, app

client = TestClient(app)


def test_format_error_message_database_error():
    exc = RuntimeError("psycopg2.OperationalError: could not connect to server: Connection refused")
    msg = _format_error_message(exc)
    assert "cơ sở dữ liệu" in msg.lower()
    assert "Database" in msg


def test_format_error_message_model_timeout():
    exc = TimeoutError("Request timed out after 30.0 seconds")
    msg = _format_error_message(exc)
    assert "mô hình ai" in msg.lower()
    assert "timeout" in msg.lower()


def test_format_error_message_rate_limit():
    exc = RuntimeError("openai.RateLimitError: 429 Too Many Requests")
    msg = _format_error_message(exc)
    assert "rate limit" in msg.lower()


def test_api_chat_handles_database_error_gracefully():
    with patch("backend.main.run_agent", side_effect=RuntimeError("psycopg2.OperationalError: Connection refused")):
        res = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu lượt xe vào?"})
        assert res.status_code == 503
        data = res.json()
        assert "cơ sở dữ liệu" in data["detail"].lower()


def test_api_chat_handles_model_timeout_gracefully():
    with patch("backend.main.run_agent", side_effect=TimeoutError("Model connection timed out")):
        res = client.post("/api/chat", json={"question": "Hôm nay có bao nhiêu lượt xe vào?"})
        assert res.status_code == 503
        data = res.json()
        assert "timeout" in data["detail"].lower()


def test_ask_endpoint_handles_error_gracefully():
    with patch("backend.main.run_agent", side_effect=RuntimeError("psycopg2.OperationalError: could not connect")):
        res = client.post("/ask", json={"question": "Hôm nay có bao nhiêu lượt xe vào?"})
        assert res.status_code == 503
        data = res.json()
        assert "cơ sở dữ liệu" in data["detail"].lower()
