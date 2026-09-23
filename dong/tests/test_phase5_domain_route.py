"""Phase 5 — Classify/route sai domain fire/anomaly/water: fallback, không im lặng."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.graph import Agent_Input, run_agent
from src.agent.intent import classify_intent_safe, is_stat_event_domain
from src.db.catalog import select_relevant_tables
from src.llm.schemas import IntentResult, RewrittenQuestion


@pytest.mark.parametrize(
    "question",
    [
        "Hôm nay có phát hiện leo trèo không?",
        "Hôm nay có cảnh báo cháy hoặc khói không?",
        "Hôm nay mực nước có vượt ngưỡng cảnh báo không?",
    ],
)
def test_is_stat_event_domain_fire_anomaly_water(question: str):
    assert is_stat_event_domain(question) is True


def test_classify_intent_safe_falls_back_on_llm_error():
    q = RewrittenQuestion(text="Hôm nay có cảnh báo cháy hoặc khói không?", filters=[])
    with patch("src.agent.intent.use_offline_tools", return_value=False), patch(
        "src.agent.intent.invoke_structured", side_effect=RuntimeError("LLM timeout")
    ):
        res = classify_intent_safe(q)
    assert res.intent == "query_data"


def test_select_relevant_tables_fire():
    q = "Hôm nay có cảnh báo cháy hoặc khói không?"
    tables = select_relevant_tables(q)
    assert tables == ["fire_smoke_event"]


def test_wrong_classify_out_of_scope_still_routes_query_data():
    """Classify sai out_of_scope cho leo trèo → orchestrator/query path, không im lặng."""
    q = "Hôm nay có phát hiện leo trèo không?"
    wrong = IntentResult(intent="out_of_scope", reason="mock wrong classify")

    with patch("src.agent.graph.classify_intent_safe", return_value=wrong):
        res = run_agent(Agent_Input(question=q))

    assert res.detail == "query_data"
    assert res.answer.strip() != ""
    assert res.query is not None


def test_wrong_classify_how_to_fire_still_routes_query_data():
    """Classify sai how_to cho cháy/khói → orchestrator ưu tiên query_data."""
    q = "Hôm nay có cảnh báo cháy hoặc khói không?"
    wrong = IntentResult(intent="how_to", reason="mock wrong classify")

    with patch("src.agent.graph.classify_intent_safe", return_value=wrong):
        res = run_agent(Agent_Input(question=q))

    assert res.detail == "query_data"
    assert res.query is not None
    assert select_relevant_tables(q) == ["fire_smoke_event"]
