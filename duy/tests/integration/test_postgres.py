import pytest

from agent.services.connection import ping
from agent.tools.postgres.query import query


@pytest.mark.integration
def test_select_1():
    row = ping()
    assert row.get("ok") == 1
    assert row.get("current_user") == "vinhdq"


@pytest.mark.integration
def test_query_select_1():
    result = query("postgres", "SELECT 1 AS ok")
    assert result["row_count"] == 1
    assert result["rows"][0]["ok"] == 1


@pytest.mark.integration
def test_query_rejects_insert():
    with pytest.raises(ValueError, match="từ chối"):
        query("postgres", "INSERT INTO pg_catalog.pg_class SELECT * FROM pg_catalog.pg_class")


@pytest.mark.integration
def test_camera_status_sample_includes_online():
    from agent.services.schema_service import describe_table

    info = describe_table("vms_db", "camera")
    status = next(c for c in info["columns"] if c["column_name"] == "status")
    assert "ONLINE" in (status.get("sample_values") or [])
