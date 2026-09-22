"""Tests for structured node I/O events."""

from src.agent.node_io import json_safe, node_event


def test_node_event_preserves_structured_rows():
    ev = node_event(
        "execute",
        input={"sql": "SELECT 1", "params": ["IN"]},
        output={"columns": ["so_luot"], "rows": [{"so_luot": 847}], "row_count": 1},
    )
    assert ev["input"]["sql"] == "SELECT 1"
    assert ev["output"]["rows"][0]["so_luot"] == 847


def test_json_safe_datetime():
    from datetime import datetime

    dt = datetime(2026, 9, 22, 10, 0, 0)
    assert json_safe({"t": dt})["t"] == "2026-09-22T10:00:00"


def test_execute_node_emits_structured_rows(monkeypatch):
    from src.agent.graph import execute_node

    monkeypatch.setattr(
        "src.agent.graph.execute_sql",
        lambda sql, params: [
            {"direction": "IN", "so_luot": 10},
            {"direction": "OUT", "so_luot": 8},
        ],
    )
    out = execute_node({
        "sql": "SELECT direction, count(*) AS so_luot FROM plate_event GROUP BY direction",
        "params": [106],
        "user_id": "u1",
        "session_id": "s1",
    })
    ev = out["events"][0]
    assert ev["input"]["sql"]
    assert ev["output"]["row_count"] == 2
    assert ev["output"]["rows"][0]["so_luot"] == 10
    assert "Trả về" not in str(ev["output"])
