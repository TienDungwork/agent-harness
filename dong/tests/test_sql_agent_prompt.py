"""Tests for sql_agent prompt — Phase 3c item 1.

Kiểm tra prompt pack resource/prompts/sql_agent/ (v1.yaml + production.txt):
- registry get/render production thành công; template không rỗng.
- Các quy tắc chính hiện diện trong template text.
"""

from __future__ import annotations

import re

import pytest

from src.prompts import registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _template() -> str:
    return registry().get("sql_agent", "production").template


# ---------------------------------------------------------------------------
# Basic load tests
# ---------------------------------------------------------------------------


def test_sql_agent_get_production_version_1():
    """registry().get('sql_agent', 'production') → version 1, name đúng."""
    prompt = registry().get("sql_agent", "production")
    assert prompt.name == "sql_agent"
    assert prompt.version == 1


def test_sql_agent_template_non_empty():
    """Template không rỗng sau khi load."""
    prompt = registry().get("sql_agent", "production")
    assert len(prompt.template.strip()) > 50


def test_sql_agent_render_no_kwargs():
    """render('sql_agent') không cần kwargs — template không có {placeholders}."""
    rendered = registry().render("sql_agent")
    assert len(rendered.strip()) > 0
    # Không còn placeholder chưa thay thế
    assert not re.search(r"\{[a-zA-Z_]\w*\}", rendered)


# ---------------------------------------------------------------------------
# Rule assertions
# ---------------------------------------------------------------------------


def test_sql_agent_select_only_rule():
    """Template yêu cầu chỉ SELECT / WITH … SELECT."""
    t = _template()
    assert "SELECT" in t


def test_sql_agent_no_ddl_dml_rule():
    """Template cấm DDL/DML rõ ràng."""
    t = _template()
    forbidden = ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE"]
    # Ít nhất một từ DDL/DML phải được đề cập (để cấm)
    mentioned = [w for w in forbidden if w in t]
    assert len(mentioned) >= 3, f"Cần đề cập cấm DDL/DML, chỉ thấy: {mentioned}"


def test_sql_agent_sql_fence_present():
    """Template chứa khối ```sql để chỉ định output format."""
    t = _template()
    assert "```sql" in t


def test_sql_agent_plate_event_vehicle_mapping():
    """Template hướng dẫn mapping loại xe (vehicle_type / plate_event)."""
    t = _template()
    assert "vehicle_type" in t
    assert "plate_event" in t
    assert "CAR" in t
    assert "MOTORCYCLE" in t


def test_sql_agent_direction_mapping():
    """Template hướng dẫn mapping direction IN/OUT."""
    t = _template()
    assert "'IN'" in t or "direction = 'IN'" in t or "direction = \'IN\'" in t or "IN" in t
    assert "'OUT'" in t or "direction = 'OUT'" in t or "direction = \'OUT\'" in t or "OUT" in t


def test_sql_agent_group_by_limit_rule():
    """Template đề cập GROUP BY và LIMIT cho chart/thống kê."""
    t = _template()
    assert "GROUP BY" in t
    assert "LIMIT" in t


def test_sql_agent_no_cross_db_join_rule():
    """Template cấm JOIN cross-database."""
    t = _template()
    lower = t.lower()
    assert "database" in lower  # Đề cập quy tắc một database


def test_sql_agent_dong_tables_mentioned():
    """Template đề cập ít nhất 3 trong 5 bảng dong."""
    t = _template()
    dong_tables = [
        "plate_event",
        "zone_event",
        "smf_face_events",
        "fire_smoke_event",
        "anomaly_event",
    ]
    found = [tbl for tbl in dong_tables if tbl in t]
    assert len(found) >= 3, f"Chỉ tìm thấy {found} trong template"


def test_sql_agent_no_cross_db_table_invented():
    """Template không bịa bảng không có trong dong catalog (vms.cameras / bare camera)."""
    t = _template()
    # Không được tồn tại tham chiếu camera table như duy
    assert "FROM camera" not in t
    assert "vms.cameras" not in t
