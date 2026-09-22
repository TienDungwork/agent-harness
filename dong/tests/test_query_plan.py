"""Tests for Phase 2.3: Schema catalog, QueryPlan builder, validator, executor, and repair loop.

Chạy hoàn toàn offline (mock DB/LLM), không yêu cầu kết nối mạng hay DB thật.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent.query_plan import (
    _offline_plan_query,
    plan_and_execute,
    plan_query,
    repair_plan_query,
)
from src.db.catalog import (
    build_schema_excerpt,
    describe_table,
    get_allowed_columns,
    get_allowed_tables,
    get_catalog,
    get_database_for_table,
)
from src.db.executor import execute_sql
from src.db.query_builder import build_sql
from src.db.validator import ValidationResult, validate_sql
from src.llm.schemas import QueryPlan, RewrittenQuestion


# ── 1. Catalog & Schema Excerpt ───────────────────────────────────────────────

def test_catalog_structure_and_tables():
    catalog = get_catalog()
    assert "plate_event" in catalog
    assert "zone_event" in catalog
    assert "smf_face_events" in catalog
    assert "fire_smoke_event" in catalog
    assert "anomaly_event" in catalog

    allowed = get_allowed_tables()
    assert allowed == {"plate_event", "zone_event", "smf_face_events", "fire_smoke_event", "anomaly_event"}

    cols = get_allowed_columns("plate_event")
    assert "event_time" in cols
    assert "direction" in cols
    assert "vehicle_type" in cols

    assert get_database_for_table("plate_event") == "its"
    assert get_database_for_table("zone_event") == "virtual_fence"


def test_describe_table():
    desc = describe_table("plate_event")
    assert desc["table"] == "plate_event"
    assert desc["database"] == "its"
    assert len(desc["columns"]) > 0

    col_names = [c["column_name"] for c in desc["columns"]]
    assert "direction" in col_names
    assert "vehicle_type" in col_names

    with pytest.raises(ValueError, match="không tồn tại trong catalog"):
        describe_table("non_existent_table")


def test_build_schema_excerpt():
    excerpt = build_schema_excerpt(["plate_event", "zone_event"])
    assert "Table: plate_event" in excerpt
    assert "Table: zone_event" in excerpt
    assert "direction" in excerpt
    assert "zone_name_cached" in excerpt


# ── 2. QueryPlan -> SQL parameterized (query_builder) ─────────────────────────

def test_build_sql_parameterized_basic(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_organization_id", 0)
    plan = QueryPlan(
        tables=["plate_event"],
        selects=["count(*) AS so_luot"],
        filters=["direction = 'IN'"],
        limit=50,
    )
    sql, params = build_sql(plan)
    assert "SELECT count(*) AS so_luot FROM plate_event" in sql
    assert "WHERE direction = %s" in sql
    assert "LIMIT %s;" in sql
    assert params == ["IN", 50]


def test_build_sql_extra_filter_appears_in_where_and_params(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_organization_id", 0)
    plan = QueryPlan(
        tables=["plate_event"],
        selects=["vehicle_type", "count(*) AS so_luot"],
        filters=["direction = 'IN'", "vehicle_type = 'CAR'"],
        group_by=["vehicle_type"],
        order_by="so_luot DESC",
        limit=20,
    )
    sql, params = build_sql(plan)
    assert "WHERE direction = %s AND vehicle_type = %s" in sql
    assert "GROUP BY vehicle_type" in sql
    assert "ORDER BY so_luot DESC" in sql
    assert "LIMIT %s;" in sql
    assert params == ["IN", "CAR", 20]


def test_build_sql_injects_organization_id(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_organization_id", 106)
    plan = QueryPlan(
        tables=["plate_event"],
        selects=["count(*) AS so_luot"],
        filters=["direction = 'IN'"],
        limit=50,
    )
    sql, params = build_sql(plan)
    assert "WHERE organization_id = %s AND direction = %s" in sql
    assert params == [106, "IN", 50]


def test_build_sql_short_filters_and_numeric(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_organization_id", 0)
    plan = QueryPlan(
        tables=["plate_event"],
        selects=["*"],
        filters=["direction=IN", "event_time >= '2026-09-01'", "organization_id = 10"],
        limit=100,
    )
    sql, params = build_sql(plan)
    assert "direction = %s" in sql
    assert "event_time >= %s" in sql
    assert "organization_id = %s" in sql
    assert "IN" in params
    assert "2026-09-01" in params
    assert 10 in params


def test_build_sql_rejects_unknown_table():
    plan = QueryPlan(
        tables=["users_table"],
        selects=["*"],
        filters=[],
    )
    with pytest.raises(ValueError, match="không nằm trong whitelist"):
        build_sql(plan)


def test_build_sql_empty_tables_raises():
    plan = QueryPlan(
        tables=[],
        selects=["*"],
    )
    with pytest.raises(ValueError, match="tables rỗng"):
        build_sql(plan)


# ── 3. Validator (SELECT-only, DML/DDL reject, whitelist) ─────────────────────

def test_validate_sql_accepts_valid_select():
    sql = "SELECT vehicle_type, count(*) AS so_luot FROM plate_event WHERE direction = %s GROUP BY vehicle_type LIMIT %s;"
    res = validate_sql(sql)
    assert isinstance(res, ValidationResult)
    assert res.ok is True
    assert bool(res) is True
    assert res.reason == ""


def test_validate_sql_rejects_delete_and_insert():
    for bad_sql in [
        "DELETE FROM plate_event WHERE 1=1;",
        "INSERT INTO plate_event (direction) VALUES ('IN');",
        "UPDATE plate_event SET direction='OUT';",
        "DROP TABLE plate_event;",
        "ALTER TABLE plate_event ADD COLUMN x int;",
        "TRUNCATE plate_event;",
        "CREATE TABLE test (id int);",
    ]:
        res = validate_sql(bad_sql)
        assert res.ok is False, f"SQL '{bad_sql}' phải bị từ chối"
        assert res.reason != ""


def test_validate_sql_rejects_unknown_table():
    sql = "SELECT * FROM secret_accounts WHERE id = 1;"
    res = validate_sql(sql)
    assert res.ok is False
    assert "không nằm trong danh mục cho phép" in res.reason


def test_validate_sql_rejects_mixed_columns():
    # access_time thuộc smf_face_events, không thuộc plate_event
    sql = "SELECT access_time FROM plate_event WHERE 1=1;"
    res = validate_sql(sql)
    assert res.ok is False
    assert "không thuộc bảng plate_event" in res.reason


def test_validate_sql_rejects_multi_statement():
    sql = "SELECT * FROM plate_event; DELETE FROM plate_event;"
    res = validate_sql(sql)
    assert res.ok is False
    assert "multi-statement" in res.reason or "Cấm" in res.reason


def test_validate_sql_allows_string_with_blocked_words():
    # Từ 'DELETE' nằm trong string literal không được xem là lệnh DELETE
    sql = "SELECT * FROM plate_event WHERE camera_name = 'CAMERA_DELETE_ZONE' LIMIT 10;"
    res = validate_sql(sql)
    assert res.ok is True


# ── 4. Executor ───────────────────────────────────────────────────────────────

def test_execute_sql_raises_when_db_not_configured(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_host", "")
    monkeypatch.setattr("src.config.settings.db_user", "")
    with pytest.raises(RuntimeError, match="Database chưa được cấu hình"):
        execute_sql("SELECT * FROM plate_event LIMIT 10;")


def test_execute_sql_raises_when_sql_invalid():
    with pytest.raises(ValueError, match="SQL không hợp lệ"):
        execute_sql("DELETE FROM plate_event WHERE 1=1;")


def test_execute_sql_mock_db_success(monkeypatch):
    monkeypatch.setattr("src.config.settings.db_host", "localhost")
    monkeypatch.setattr("src.config.settings.db_user", "test_user")

    fake_cursor = MagicMock()
    fake_cursor.description = [("vehicle_type",), ("so_luot",)]
    fake_cursor.fetchall.return_value = [{"vehicle_type": "CAR", "so_luot": 15}]

    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    from contextlib import contextmanager

    @contextmanager
    def fake_get_connection(dbname: str):
        assert dbname == "its"
        yield fake_conn

    monkeypatch.setattr("src.db.executor.get_connection", fake_get_connection)

    rows = execute_sql("SELECT vehicle_type, count(*) AS so_luot FROM plate_event LIMIT 10;")
    assert len(rows) == 1
    assert rows[0]["vehicle_type"] == "CAR"
    assert rows[0]["so_luot"] == 15


# ── 5. Plan Query & Repair Loop ───────────────────────────────────────────────

def test_offline_plan_query_heuristic():
    plan_car = _offline_plan_query("Hôm nay có bao nhiêu ô tô vào cổng?")
    assert plan_car.tables == ["plate_event"]
    assert "direction = 'IN'" in plan_car.filters
    assert "vehicle_type = 'CAR'" in plan_car.filters

    plan_fence = _offline_plan_query("Có sự kiện xâm nhập hàng rào ảo nào không?")
    assert plan_fence.tables == ["zone_event"]

    plan_face = _offline_plan_query("Thống kê nhận diện khuôn mặt chấm công")
    assert plan_face.tables == ["smf_face_events"]

    plan_fire = _offline_plan_query("Có cảnh báo cháy khói không?")
    assert plan_fire.tables == ["fire_smoke_event"]

    plan_anomaly = _offline_plan_query("Thống kê sự kiện ẩu đả và ngập nước")
    assert plan_anomaly.tables == ["anomaly_event"]


def test_plan_query_with_rewritten_question():
    rewritten = RewrittenQuestion(
        text="Thống kê xe vào hôm nay",
        filters=["direction=IN", "vehicle_type=TRUCK"],
        time_range="today",
        intent_hint="query_data",
    )
    plan = plan_query(rewritten)
    assert plan.tables == ["plate_event"]
    assert "direction=IN" in plan.filters
    assert "vehicle_type=TRUCK" in plan.filters


@patch("src.agent.query_plan.use_offline_tools", return_value=False)
@patch("src.agent.query_plan.invoke_structured")
def test_plan_query_mock_structured(mock_structured, _mock_offline):
    expected = QueryPlan(
        tables=["plate_event"],
        selects=["vehicle_type", "count(*) AS so_luot"],
        filters=["direction = 'IN'"],
        group_by=["vehicle_type"],
        order_by="so_luot DESC",
        limit=100,
    )
    mock_structured.return_value = expected

    plan = plan_query("Bao nhiêu xe vào?")
    assert plan == expected
    assert mock_structured.called


@patch("src.agent.query_plan.use_offline_tools", return_value=False)
@patch("src.agent.query_plan.invoke_structured")
def test_repair_plan_query_mock(mock_structured, _mock_offline):
    bad_plan = QueryPlan(tables=["wrong_table"], selects=["*"])
    repaired_plan = QueryPlan(tables=["plate_event"], selects=["count(*)"])
    mock_structured.return_value = repaired_plan

    result = repair_plan_query("xe vào", "excerpt", bad_plan, "Bảng wrong_table không hợp lệ")
    assert result == repaired_plan
    assert mock_structured.called


def test_plan_and_execute_repair_loop_on_validation_failure(monkeypatch):
    """Khi plan đầu tiên sinh SQL vi phạm whitelist, repair hook được gọi để sửa."""
    bad_plan = QueryPlan(tables=["wrong_table"], selects=["*"])
    good_plan = QueryPlan(tables=["plate_event"], selects=["count(*) AS so_luot"])

    plans = [bad_plan, good_plan]

    def fake_plan_query(question, schema_excerpt=None):
        return plans.pop(0)

    def fake_repair(question, schema_excerpt, last_plan, error_msg):
        return plans.pop(0)

    monkeypatch.setattr("src.agent.query_plan.plan_query", fake_plan_query)
    monkeypatch.setattr("src.agent.query_plan.repair_plan_query", fake_repair)
    monkeypatch.setattr("src.agent.query_plan.execute_sql", lambda sql, params: [{"so_luot": 42}])

    res = plan_and_execute("Đếm xe", max_repairs=1)
    assert res["success"] is True
    assert res["rows"] == [{"so_luot": 42}]
    assert res["error"] is None
