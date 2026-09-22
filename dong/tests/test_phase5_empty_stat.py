"""Phase 5 — Empty số liệu trả đúng, có '0' khi rule yêu cầu."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.graph import respond_node
from src.agent.tools import QueryResult
from src.guardrails import EMPTY_TOOL_REPLY, check_output, empty_stat_reply
from src.main import app

client = TestClient(app)


def test_empty_stat_reply_contains_zero():
    msg = empty_stat_reply()
    assert "0" in msg
    assert EMPTY_TOOL_REPLY == msg


def test_respond_node_empty_rows_includes_zero():
    out = respond_node({
        "question": "Có bao nhiêu lượt đám đông?",
        "rows": [],
        "columns": [],
        "user_id": "u1",
        "session_id": "s1",
    })
    assert "0" in out["result"].answer
    assert out["events"][0]["output"]["answer_source"] == "empty"


def test_check_output_tool_empty_fabricated_uses_zero_reply():
    result = check_output(
        "Có 5 lượt xe vào hôm nay.",
        ["Hôm nay có bao nhiêu lượt xe vào?", "total=0"],
        tool_empty=True,
    )
    assert "0" in result.answer
    assert "5" not in result.answer
    assert "fabricated_numbers_on_empty_tool" in result.issues


def test_check_output_tool_empty_honest_normalized_to_zero():
    result = check_output(
        "Không có dữ liệu lượt xe vào hôm nay.",
        ["Hôm nay có bao nhiêu lượt xe vào?"],
        tool_empty=True,
    )
    assert "0" in result.answer
    assert "empty_stat_missing_zero" in result.issues


def test_api_chat_empty_query_answer_has_zero():
    from src.agent.graph import Agent_Output

    empty_out = Agent_Output(
        question="Hôm nay có phát hiện leo trèo không?",
        answer=empty_stat_reply(),
        query=QueryResult(tool="sql_builder", columns=[], rows=[], row_count=0),
        detail="query_data",
    )

    with patch("src.main.run_agent", return_value=empty_out):
        res = client.post(
            "/api/chat",
            json={
                "question": "Hôm nay có phát hiện leo trèo không?",
                "session_id": "sess-empty",
                "user_id": "user-empty",
            },
        )

    assert res.status_code == 200
    assert "0" in res.json()["answer"]
