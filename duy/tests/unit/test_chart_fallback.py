from agent.services.chart_fallback import (
    fallback_vehicle_type_chart,
    should_retry_vehicle_chart,
)
from agent.services.chart_hint import build_chart_sql_hint


def test_chart_hint_vehicle_type():
    hint = build_chart_sql_hint("Vẽ biểu đồ số lượng phương tiện ngày 13/09/2026")
    assert "vehicle_type" in hint
    assert "direction" in hint


def test_should_retry_wrong_group_by():
    rows = [{"direction": "IN", "n": 17}]
    sql = (
        "SELECT direction, COUNT(*) AS n FROM plate_event "
        "WHERE event_time::date = DATE '2026-09-13' GROUP BY direction"
    )
    q = "vẽ biểu đồ số lượng phương tiện ngày 13/09/2026"
    assert should_retry_vehicle_chart(question=q, sql=sql, rows=rows)


def test_fallback_vehicle_type_chart():
    rows = [{"direction": "IN", "n": 17}]
    sql = (
        "SELECT direction, COUNT(*) AS n FROM plate_event "
        "WHERE event_time::date = DATE '2026-09-13' GROUP BY direction"
    )
    q = "vẽ biểu đồ số lượng phương tiện ngày 13/09/2026"
    out = fallback_vehicle_type_chart(question=q, sql=sql, rows=rows)
    assert out is not None
    assert len(out["query_result"]["rows"]) >= 2
    assert "vehicle_type" in out["query_result"]["rows"][0]
