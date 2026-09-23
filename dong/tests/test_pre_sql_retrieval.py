"""Tests for scoped catalog retrieval (select_relevant_tables) and scoped retrieve_schema — Phase 3b."""

from __future__ import annotations

import pytest

from src.agent.graph import retrieve_schema_node
from src.db import (
    build_schema_excerpt,
    get_allowed_tables,
    select_relevant_tables,
)
from src.llm.schemas import RewrittenQuestion


@pytest.fixture
def allowed_tables() -> set[str]:
    return get_allowed_tables()


def test_import_from_src_db():
    from src.db import select_relevant_tables as fn

    assert callable(fn)


def test_vehicle_questions_select_plate_event(allowed_tables):
    questions = [
        "Hôm nay có bao nhiêu lượt xe vào?",
        "Thống kê ô tô và xe máy vào KCN",
        "Biển số 51F-12345 có vào cổng hôm nay không?",
        "Có bao nhiêu xe tải qua cổng?",
        "ALPR camera ghi nhận phương tiện nào?",
        "luot xe vao cong hom nay",
    ]
    for q in questions:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4, f"len > 4 for {q}: {tables}"
        assert set(tables).issubset(allowed_tables), f"Unknown table in {tables}"
        assert "plate_event" in tables, f"plate_event missing for {q}: {tables}"
        assert tables[0] == "plate_event", f"plate_event should be first for {q}: {tables}"


def test_fire_smoke_questions_select_fire_smoke_event(allowed_tables):
    questions = [
        "Có cảnh báo cháy nào hôm nay không?",
        "Phát hiện khói ở khu vực nào?",
        "Báo cháy hỏa hoạn lúc mấy giờ?",
        "bao chay va bao khoi",
        "firesmoke entity_type check",
    ]
    for q in questions:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4
        assert set(tables).issubset(allowed_tables)
        assert "fire_smoke_event" in tables, f"fire_smoke_event missing for {q}: {tables}"
        assert tables[0] == "fire_smoke_event"


def test_face_checkin_questions_select_smf_face_events(allowed_tables):
    questions = [
        "Hôm nay có bao nhiêu người quét mặt chấm công?",
        "Nhân viên nào ra vào cổng sáng nay?",
        "Nhận diện khuôn mặt lúc 8h",
        "cham cong nhan vien hom nay",
        "smart face access check",
    ]
    for q in questions:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4
        assert set(tables).issubset(allowed_tables)
        assert "smf_face_events" in tables, f"smf_face_events missing for {q}: {tables}"
        assert tables[0] == "smf_face_events"


def test_zone_fence_questions_select_zone_event(allowed_tables):
    questions = [
        "Có cảnh báo xâm nhập hàng rào ảo không?",
        "Vùng cấm có người vượt rào lúc nào?",
        "virtual fence zone_event",
        "canh bao xam nhap hang rao",
    ]
    for q in questions:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4
        assert set(tables).issubset(allowed_tables)
        assert "zone_event" in tables, f"zone_event missing for {q}: {tables}"


def test_anomaly_questions_select_anomaly_event(allowed_tables):
    questions = [
        "Có vụ ẩu đả đánh nhau nào không?",
        "Phát hiện đám đông tụ tập bất thường",
        "Mực nước ngập có cao không?",
        "AI anomaly loitering alert",
    ]
    for q in questions:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4
        assert set(tables).issubset(allowed_tables)
        assert "anomaly_event" in tables, f"anomaly_event missing for {q}: {tables}"


def test_multi_domain_scoped_and_ordered(allowed_tables):
    q = "Thống kê lượt xe và các cảnh báo cháy"
    tables = select_relevant_tables(q)
    assert len(tables) <= 4
    assert set(tables).issubset(allowed_tables)
    assert "plate_event" in tables
    assert "fire_smoke_event" in tables
    assert tables[0] == "plate_event"


def test_fallback_token_scoring(allowed_tables):
    # Alert level in fire_smoke_event
    tables = select_relevant_tables("Kiểm tra alert_level")
    assert len(tables) <= 4
    assert set(tables).issubset(allowed_tables)
    assert "fire_smoke_event" in tables

    # Severity in anomaly_event
    tables = select_relevant_tables("Tra cứu severity")
    assert len(tables) <= 4
    assert set(tables).issubset(allowed_tables)
    assert "anomaly_event" in tables

    # Department name in smf_face_events
    tables = select_relevant_tables("Lọc theo department_name")
    assert len(tables) <= 4
    assert set(tables).issubset(allowed_tables)
    assert "smf_face_events" in tables

    # Zone name cached in zone_event
    tables = select_relevant_tables("Lọc theo zone_name_cached")
    assert len(tables) <= 4
    assert set(tables).issubset(allowed_tables)
    assert "zone_event" in tables


def test_safe_default_when_no_match(allowed_tables):
    for q in ["", "   ", "xyz 123 !@#", "asdfghjkl"]:
        tables = select_relevant_tables(q)
        assert len(tables) <= 4
        assert set(tables).issubset(allowed_tables)
        assert tables == ["plate_event"]


def test_limit_parameter(allowed_tables):
    # limit=1
    tables = select_relevant_tables("Thống kê lượt xe và cảnh báo cháy", limit=1)
    assert len(tables) == 1
    assert tables[0] == "plate_event"

    # limit=2
    tables = select_relevant_tables("Thống kê lượt xe và cảnh báo cháy", limit=2)
    assert len(tables) == 2

    # limit=0 and negative
    assert select_relevant_tables("lượt xe", limit=0) == []
    assert select_relevant_tables("lượt xe", limit=-1) == []


def test_all_returned_tables_always_in_catalog(allowed_tables):
    queries = [
        "Hôm nay có bao nhiêu lượt xe vào?",
        "Cháy nổ ở đâu?",
        "Chấm công nhân viên",
        "Xâm nhập hàng rào",
        "Đám đông bất thường",
        "Camera CAM01",
        "Báo cáo tổng hợp",
        "",
    ]
    for q in queries:
        for limit in [1, 2, 4]:
            res = select_relevant_tables(q, limit=limit)
            assert len(res) <= limit
            assert len(res) == len(set(res)), f"Duplicates in {res}"
            assert set(res).issubset(allowed_tables), f"Invalid table in {res}"


def test_build_schema_excerpt_no_args_still_full_catalog():
    """Verify build_schema_excerpt() without arguments still returns all 5 tables."""
    full = build_schema_excerpt()
    for tbl in ["plate_event", "zone_event", "smf_face_events", "fire_smoke_event", "anomaly_event"]:
        assert f"Table: {tbl}" in full


def test_retrieve_schema_node_vehicle_scoped_excerpt():
    """Vehicle question: excerpt contains plate_event and excludes unrelated tables (strictly smaller than full)."""
    full = build_schema_excerpt()
    state = {
        "question": "Hôm nay có bao nhiêu lượt xe vào cổng?",
        "rewritten": RewrittenQuestion(text="Hôm nay có bao nhiêu lượt xe vào cổng?"),
        "intent": "query_data",
        "user_id": "u1",
        "session_id": "s1",
    }
    res = retrieve_schema_node(state)

    assert "schema_excerpt" in res
    assert res.get("selected_tables") == ["plate_event"]

    excerpt = res["schema_excerpt"]
    assert len(excerpt) < len(full), "Scoped excerpt must be strictly smaller than full catalog"
    assert "Table: plate_event" in excerpt

    # Unrelated tables should be absent
    assert "Table: fire_smoke_event" not in excerpt
    assert "Table: smf_face_events" not in excerpt
    assert "Table: zone_event" not in excerpt
    assert "Table: anomaly_event" not in excerpt

    # Verify node event payload
    events = res.get("events", [])
    assert len(events) == 1
    ev = events[0]
    assert ev["node_id"] == "retrieve_schema"
    assert ev["output"]["schema_excerpt"] == excerpt
    assert ev["output"]["selected_tables"] == ["plate_event"]
    assert ev["meta"]["selected_tables"] == ["plate_event"]
    assert ev["meta"]["schema_length"] == len(excerpt)
    assert ev["meta"]["user_id"] == "u1"
    assert ev["meta"]["session_id"] == "s1"


def test_retrieve_schema_node_fire_smoke_scoped_excerpt():
    """Fire question: excerpt centers on fire_smoke_event and is smaller than full catalog."""
    full = build_schema_excerpt()
    state = {
        "question": "Có cảnh báo cháy nào hôm nay không?",
        "rewritten": RewrittenQuestion(text="Có cảnh báo cháy nào hôm nay không?"),
    }
    res = retrieve_schema_node(state)

    assert res.get("selected_tables") == ["fire_smoke_event"]
    excerpt = res["schema_excerpt"]
    assert len(excerpt) < len(full)
    assert "Table: fire_smoke_event" in excerpt
    assert "Table: plate_event" not in excerpt
    assert "Table: smf_face_events" not in excerpt
    assert "Table: zone_event" not in excerpt
    assert "Table: anomaly_event" not in excerpt


def test_retrieve_schema_node_prefers_rewritten_over_question():
    """retrieve_schema_node prefers rewritten.text over question if both are provided."""
    state = {
        "question": "Có cảnh báo cháy không?",  # would pick fire_smoke_event
        "rewritten": RewrittenQuestion(text="Biển số 51F-12345 có vào cổng hôm nay không?"),  # plate_event
    }
    res = retrieve_schema_node(state)

    assert res.get("selected_tables") == ["plate_event"]
    assert "Table: plate_event" in res["schema_excerpt"]
    assert "Table: fire_smoke_event" not in res["schema_excerpt"]


def test_retrieve_schema_node_fallback_to_question_without_rewritten():
    """retrieve_schema_node falls back to question when rewritten is not in state."""
    state = {
        "question": "Hôm nay có bao nhiêu người quét mặt chấm công?",
    }
    res = retrieve_schema_node(state)

    assert res.get("selected_tables") == ["smf_face_events"]
    assert "Table: smf_face_events" in res["schema_excerpt"]
    assert "Table: plate_event" not in res["schema_excerpt"]


def test_retrieve_schema_node_empty_question_safe_default():
    """Empty question safely falls back to default table (plate_event) with scoped excerpt."""
    state = {"question": ""}
    res = retrieve_schema_node(state)

    assert res.get("selected_tables") == ["plate_event"]
    assert "Table: plate_event" in res["schema_excerpt"]
    assert len(res["schema_excerpt"]) < len(build_schema_excerpt())


def test_graph_run_emits_scoped_retrieve_schema_event():
    """Graph execution emits retrieve_schema event containing scoped tables and schema_excerpt."""
    import uuid
    from unittest.mock import patch
    from src.agent.graph import Agent_Input, run_agent_stream

    mock_rows = [{"so_luot": 42}]
    inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
    with patch("src.llm.client.use_offline_tools", return_value=True), \
         patch("src.agent.graph.execute_sql", return_value=mock_rows):
        events = list(run_agent_stream(inp, session_id=f"test_session_{uuid.uuid4().hex}"))

    schema_events = [ev for ev in events if ev.get("node_id") == "retrieve_schema" and ev.get("status") == "done"]
    assert len(schema_events) == 1
    ev = schema_events[0]
    output = ev.get("output", {})
    assert output.get("selected_tables") == ["plate_event"]
    assert "Table: plate_event" in output.get("schema_excerpt", "")
    assert "Table: fire_smoke_event" not in output.get("schema_excerpt", "")
