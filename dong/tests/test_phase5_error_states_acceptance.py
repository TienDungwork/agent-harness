"""Phase 5 Acceptance Tests — Validation and Error States.

Kiểm tra 5 tiêu chí của Phase 5:
1. SQL invalid / hết lần repair -> message ngắn tiếng Việt; không crash stream.
2. LLM timeout / DB fail -> message ngắn, không leak SQL/traceback.
3. Classify lỗi -> fallback an toàn, không im lặng.
4. Empty số liệu -> trả lời đúng chuẩn (chứa số "0").
5. SSE stream __answer__ trả về status error kèm thông báo thân thiện.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import Agent_Input, run_agent, run_agent_stream
from src.agent.intent import classify_intent_safe
from src.db.validator import ValidationResult
from src.guardrails import empty_stat_reply
from src.main import USER_ERROR_MAX_LEN, _format_error_message, app

client = TestClient(app)


def test_sql_repair_max_exhausted_yields_friendly_message_no_crash():
    """1. SQL invalid / hết lần repair: trả về message ngắn tiếng Việt trong stream mà không crash."""
    inp = Agent_Input(question="Hôm nay có bao nhiêu xe vào?")

    # Mock validate_sql luôn trả về lỗi để hết số lần repair (settings.sql_repair_max)
    with (
        patch("src.llm.client.use_offline_tools", return_value=True),
        patch(
            "src.agent.validate_sql.validate_sql",
            return_value=ValidationResult(ok=False, reason="Cú pháp không hợp lệ"),
        ),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": inp.question, "session_id": "test-repair-fail"},
        )

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    node_ids = [e.get("node_id") for e in events]
    assert "generate_sql" in node_ids
    assert "validate_sql" in node_ids
    assert "repair_sql" in node_ids
    assert "__answer__" in node_ids

    answer_ev = next(e for e in events if e.get("node_id") == "__answer__")
    ans_text = answer_ev.get("output", "")
    assert "Lỗi" in ans_text or "không hợp lệ" in ans_text or "Không thể" in ans_text
    assert len(ans_text) <= 300


def test_llm_timeout_and_db_fail_message_no_leak():
    """2. LLM timeout / DB fail: message ngắn thân thiện, không leak traceback hay raw SQL."""
    exc_timeout = TimeoutError("Request timed out after 30s to http://192.168.1.196:11434")
    exc_db = RuntimeError("psycopg2.OperationalError: could not connect to server 192.168.1.196 port 5432")

    msg_timeout = _format_error_message(exc_timeout)
    msg_db = _format_error_message(exc_db)

    assert len(msg_timeout) <= USER_ERROR_MAX_LEN
    assert len(msg_db) <= USER_ERROR_MAX_LEN
    assert "192.168.1.196" not in msg_timeout
    assert "192.168.1.196" not in msg_db
    assert "traceback" not in msg_timeout.lower()
    assert "traceback" not in msg_db.lower()


def test_classify_error_safe_fallback_not_silent():
    """3. Classify lỗi: fallback an toàn sang query_data, không trả về rỗng hay im lặng."""
    from src.llm.schemas import RewrittenQuestion

    q = RewrittenQuestion(text="Hôm nay có cảnh báo cháy hoặc khói không?")
    with (
        patch("src.agent.intent.use_offline_tools", return_value=False),
        patch("src.agent.intent.invoke_structured", side_effect=Exception("LLM down")),
    ):
        res = classify_intent_safe(q)

    assert res.intent in ("query_data", "docs", "chat", "out_of_scope")
    assert res.intent == "query_data"  # Domain cháy khói -> query_data fallback


def test_empty_statistical_data_contains_zero():
    """4. Empty số liệu: trả lời chuẩn tiếng Việt có chứa số '0'."""
    ans = empty_stat_reply()
    assert "0" in ans
    assert "không có" in ans.lower() or "không tìm thấy" in ans.lower()


def test_stream_error_emits_friendly_answer_status_error():
    """5. Lỗi stream phát ra __answer__ status error với câu thông báo ngắn gọn."""
    from src.main import _cache
    _cache.clear()

    with patch(
        "src.agent.graph.run_agent_stream",
        side_effect=RuntimeError("Database connection lost"),
    ):
        res = client.post(
            "/api/agent/stream",
            json={"question": "Hôm nay có bao nhiêu xe vào?"},
        )

    assert res.status_code == 200
    events = []
    for line in res.text.splitlines():
        if line.startswith("data: "):
            raw = line[6:].strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))

    answer_ev = next(e for e in events if e.get("node_id") == "__answer__")
    assert answer_ev.get("status") == "error"
    ans_text = answer_ev.get("output", "")
    assert "Lỗi" in ans_text or "không thể" in ans_text.lower()
    assert "Database connection lost" not in ans_text  # Sanitized
