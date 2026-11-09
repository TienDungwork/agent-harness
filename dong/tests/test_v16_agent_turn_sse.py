"""v16 Task 6 — AgentTurnService SSE contract."""

from __future__ import annotations

import json
from types import SimpleNamespace

from src.application.agent_turn import AgentTurnService, TurnInput


def test_iter_graph_events_complete_shape(monkeypatch):
    svc = AgentTurnService()

    def fake_stream(*_a, **_k):
        yield {
            "__final_result__": SimpleNamespace(
                question="q",
                answer="a",
                detail="query_data",
                query=SimpleNamespace(tool="sql", columns=[], row_count=0),
            )
        }

    monkeypatch.setattr("src.main.run_agent_stream", fake_stream)

    events = list(svc.iter_graph_events(TurnInput(question="q", user_id="u", session_id="s")))
    complete = next(p for p in events if p.get("complete") is True)
    assert complete["answer"] == "a"
    assert complete["question"] == "q"
    assert "detail" in complete


def test_stream_sse_emits_done(monkeypatch):
    svc = AgentTurnService()

    def fake_stream(*_a, **_k):
        yield {
            "__final_result__": SimpleNamespace(
                question="q",
                answer="a",
                detail="",
                query=None,
            )
        }

    monkeypatch.setattr("src.main.run_agent_stream", fake_stream)

    import asyncio

    async def _collect():
        out = []
        async for line in svc.stream_sse(TurnInput(question="q", user_id="u", session_id="s")):
            out.append(line)
        return out

    lines = asyncio.run(_collect())
    assert any("[DONE]" in line for line in lines)
    body = []
    for line in lines:
        if not line.startswith("data: ") or "[DONE]" in line:
            continue
        body.append(json.loads(line[len("data: ") :].strip()))
    assert any(p.get("complete") is True for p in body)
