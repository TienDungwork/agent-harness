"""Tests for Phase 3a: Skip rewrite khi chat hoặc TTL cache hit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from src.agent.graph import Agent_Input, rewrite_node, run_agent
from src.agent.intent import is_chat_greeting, is_chat_like
from src.agent.rewrite import rewrite_question, rewrite_question_safe
from src.llm.schemas import RewrittenQuestion
from src.main import AskRequest, ChatRequest, ask, chat, stream_agent
from src.memory.ttl_cache import clear_ttl_cache, make_cache_key, set_ttl_cached


@pytest.fixture(autouse=True)
def reset_state():
    clear_ttl_cache()
    yield
    clear_ttl_cache()


def test_is_chat_greeting_heuristics():
    """Verify shared greeting keywords heuristic."""
    assert is_chat_greeting("xin chào") is True
    assert is_chat_greeting("chào bạn") is True
    assert is_chat_greeting("Xin chào bạn!") is True
    assert is_chat_greeting("hello") is True
    assert is_chat_greeting("hi") is True
    assert is_chat_greeting("hi bot") is True
    assert is_chat_greeting("cảm ơn") is True
    assert is_chat_greeting("cảm ơn bạn nhé!") is True
    assert is_chat_greeting("bạn làm được gì") is True
    assert is_chat_like("chào") is True

    # Non-chat queries must be False
    assert is_chat_greeting("Hôm nay có bao nhiêu xe vào cổng 1?") is False
    assert is_chat_greeting("Cách xem lại camera") is False
    assert is_chat_greeting("Tại sao camera mất kết nối?") is False
    assert is_chat_greeting("AIOC là gì?") is False
    assert is_chat_greeting("Thời tiết hôm nay thế nào?") is False


@patch("src.agent.rewrite.use_offline_tools", return_value=False)
@patch("src.agent.rewrite.invoke_structured")
def test_chat_greeting_skips_invoke_structured(mock_invoke_structured, _mock_offline):
    """Chat greeting passthrough does not call LLM structured rewrite."""
    greetings = ["xin chào", "chào bạn", "hello", "cảm ơn", "bạn làm được gì"]
    for g in greetings:
        res = rewrite_question(g)
        assert isinstance(res, RewrittenQuestion)
        assert res.text == g
        assert res.intent_hint == "chat"
        assert res.filters == []

        res_safe = rewrite_question_safe(g)
        assert res_safe.text == g

    mock_invoke_structured.assert_not_called()


@patch("src.llm.client.use_offline_tools", return_value=False)
@patch("src.agent.rewrite.invoke_structured")
def test_rewrite_node_meta_llm_used_false_for_chat(mock_invoke, _mock_offline):
    """rewrite_node marks llm_used=False in event meta for chat questions even when online."""
    out = rewrite_node({"question": "xin chào bạn", "events": []})
    assert len(out["events"]) == 1
    ev = out["events"][0]
    assert ev["node_id"] == "rewrite"
    assert ev["output"]["rewritten"]["text"] == "xin chào bạn"
    assert ev["meta"]["llm_used"] is False
    assert ev["meta"].get("skipped") is True
    mock_invoke.assert_not_called()


def test_stat_question_rewrites_normally_offline():
    """Stat question still rewrites normally offline with filters/time_range."""
    res = rewrite_question("hôm nay có bao nhiêu xe vào cổng 1?")
    assert res.time_range == "today"
    assert "direction=IN" in res.filters
    assert res.intent_hint == "query_data"


@patch("src.agent.rewrite.use_offline_tools", return_value=False)
@patch("src.agent.rewrite.invoke_structured")
def test_stat_question_calls_invoke_structured_online(mock_invoke_structured, _mock_offline):
    """Stat question online calls invoke_structured as normal."""
    expected = RewrittenQuestion(
        text="Thống kê xe vào hôm nay",
        filters=["direction=IN"],
        time_range="today",
        intent_hint="query_data",
    )
    mock_invoke_structured.return_value = expected

    res = rewrite_question("hôm nay có bao nhiêu xe vào")
    assert mock_invoke_structured.called
    assert res == expected


@patch("src.llm.client.use_offline_tools", return_value=False)
@patch("src.agent.rewrite.invoke_structured")
def test_rewrite_node_meta_llm_used_true_for_stat(mock_invoke, _mock_offline):
    """rewrite_node marks llm_used=True for stat questions when online."""
    mock_invoke.return_value = RewrittenQuestion(text="xe vào", filters=["direction=IN"])
    out = rewrite_node({"question": "hôm nay có bao nhiêu xe vào", "events": []})
    ev = out["events"][0]
    assert ev["meta"]["llm_used"] is True
    assert ev["meta"].get("skipped") is not True


def test_ttl_cache_hit_chat_skips_rewrite_and_agent(monkeypatch):
    """Chat endpoint on TTL cache hit returns answer without calling rewrite or agent."""
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Hôm nay có 150 lượt xe vào.",
        "tool": "query_traffic",
        "columns": ["so_luot"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_rewrite = MagicMock()
    mock_run = MagicMock()
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", mock_rewrite)
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = chat(ChatRequest(question=q))
    assert resp.answer == "Hôm nay có 150 lượt xe vào."
    assert resp.detail.get("cache_hit") is True
    mock_rewrite.assert_not_called()
    mock_run.assert_not_called()


def test_ttl_cache_hit_stream_skips_rewrite_and_stream(monkeypatch):
    """Stream endpoint on TTL cache hit yields cached answer without calling rewrite or stream."""
    from fastapi.testclient import TestClient
    from src.main import app

    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Tổng cộng 200 lượt xe.",
        "tool": "query_traffic",
        "columns": ["total"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_rewrite = MagicMock()
    mock_stream = MagicMock()
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", mock_rewrite)
    monkeypatch.setattr("src.agent.graph.run_agent_stream", mock_stream)

    client = TestClient(app)
    res = client.post("/api/agent/stream", json={"question": q})
    assert res.status_code == 200
    body = res.text

    assert "Tổng cộng 200 lượt xe." in body
    assert '"cache_hit": true' in body
    mock_rewrite.assert_not_called()
    mock_stream.assert_not_called()


def test_ttl_cache_hit_ask_skips_rewrite_and_agent(monkeypatch):
    """Ask endpoint on TTL cache hit returns answer without calling rewrite or agent."""
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    q = "Hôm nay có bao nhiêu lượt xe vào cổng?"
    store_key = make_cache_key(q, route="query_data")
    set_ttl_cached(store_key, {
        "question": q,
        "answer": "Tổng cộng 200 lượt xe.",
        "tool": "query_traffic",
        "columns": ["total"],
        "row_count": 1,
        "agent_detail": "query_data",
    })

    mock_rewrite = MagicMock()
    mock_run = MagicMock()
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", mock_rewrite)
    monkeypatch.setattr("src.main.run_agent", mock_run)

    resp = ask(AskRequest(question=q))
    assert resp.answer == "Tổng cộng 200 lượt xe."
    mock_rewrite.assert_not_called()
    mock_run.assert_not_called()


def test_main_chat_greeting_skips_rewrite_safe_before_agent(monkeypatch):
    """Chat endpoint for greetings bypasses rewrite_question_safe completely."""
    monkeypatch.setattr("src.config.settings.cache_enabled", True)
    monkeypatch.setattr("src.config.settings.memory_ttl_seconds", 300)

    mock_rewrite_safe = MagicMock()
    monkeypatch.setattr("src.agent.rewrite.rewrite_question_safe", mock_rewrite_safe)

    with patch("src.main.in_scope", return_value=True), \
         patch("src.llm.client.use_offline_tools", return_value=True):
        resp = chat(ChatRequest(question="xin chào bạn"))

    mock_rewrite_safe.assert_not_called()
    assert resp.answer
    assert resp.detail.get("agent_detail") in ("chat", "clarify")
