"""Product test suite for Knowledge & RAG: AIOC doc retrieval, Pre-SQL contextual grounding, Document search, Resource path resolution."""
from __future__ import annotations

# ==============================================================================
# --- Sourced from test_aioc_docs.py ---
# ==============================================================================

"""Unit tests cho Phase 3c — AIOC YAML task cards & dataset catalog."""


from unittest.mock import patch

from src.db.dataset_catalog import (
    clear_dataset_catalog_cache,
    get_case_hints,
    get_table_for_keywords,
    load_dataset_catalog,
)
from src.knowledge.answer import _offline_answer_from_cards, answer_from_docs
from src.knowledge.loader import (
    aioc_docs_root,
    clear_docs_cache,
    load_aioc_cards,
    load_published_cards,
    load_vms_cards,
)
from src.knowledge.retrieval import retrieve_docs
from src.llm.schemas import DocsAnswer


def test_aioc_cards_load():
    """Kiểm tra AIOC cards load thành công với số lượng >= 7 và đủ trường theo schema."""
    aioc_root = aioc_docs_root()
    assert aioc_root.exists()
    assert (aioc_root / "index.yaml").exists()

    aioc_cards = load_aioc_cards()
    assert len(aioc_cards) >= 7

    required_ids = {
        "aioc.login_devices",
        "aioc.manage_camera",
        "aioc.add_camera",
        "aioc.camera_status",
        "aioc.diagram_login_devices",
        "aioc.diagram_add_camera",
        "aioc.vms_vs_devices",
    }
    loaded_ids = {c.get("id") for c in aioc_cards}
    assert required_ids.issubset(loaded_ids)

    for card in aioc_cards:
        assert card.get("id")
        assert card.get("title")
        assert card.get("route") == "/devices"
        assert card.get("menu_path") == ["Cấu hình & Thiết bị", "Quản Lý Camera"]
        assert len(card.get("steps") or []) > 0
        assert card.get("status") == "published"


def test_loader_merge_cards():
    """Kiểm tra load_published_cards merge cả VMS cards và AIOC cards."""
    vms_cards = load_vms_cards()
    aioc_cards = load_aioc_cards()
    merged = load_published_cards()

    assert len(vms_cards) == 40
    assert len(aioc_cards) >= 7
    assert len(merged) == len(vms_cards) + len(aioc_cards)

    # Đảm bảo có cả id VMS và AIOC
    merged_ids = {c.get("id") for c in merged}
    assert "devices.add_camera" in merged_ids
    assert "aioc.camera_status" in merged_ids


def test_retrieve_docs_aioc_camera_status():
    """Kiểm tra retrieve_docs tìm đúng card camera_status cho câu hỏi về trạng thái camera."""
    q = "Trên AIOC devices, trạng thái camera Trực Tuyến / Ngoại Tuyến / Bảo Trì nghĩa là gì và đổi ở đâu?"
    res = retrieve_docs(q)
    assert len(res) > 0
    top_id = res[0]["id"]
    assert "camera_status" in top_id


def test_retrieve_docs_aioc_diagram_add_camera():
    """Kiểm tra retrieve_docs tìm đúng card diagram_add_camera hoặc add_camera cho sơ đồ thêm camera."""
    q = "Vẽ sơ đồ quy trình thêm một camera mới trên AIOC (từ mở form đến tạo xong)."
    res = retrieve_docs(q)
    assert len(res) > 0
    top_id = res[0]["id"]
    assert top_id in {"aioc.diagram_add_camera", "aioc.add_camera"}


def test_retrieve_docs_aioc_other_queries():
    """Kiểm tra retrieve_docs cho các câu hỏi AIOC khác (login, manage, diagram, vms vs devices)."""
    # 1. Đăng nhập
    res_login = retrieve_docs("Làm sao đăng nhập Cloud Cam để vào trang quản lý camera https://aioc.atin.vn/devices?")
    assert len(res_login) > 0
    assert res_login[0]["id"] == "aioc.login_devices"

    # 2. Quản lý camera
    res_manage = retrieve_docs("Trên AIOC, vào đâu để quản lý camera / thiết bị (Quản Lý Camera)?")
    assert len(res_manage) > 0
    assert res_manage[0]["id"] == "aioc.manage_camera"

    # 3. Thêm camera trên AIOC
    res_add = retrieve_docs("Các bước thêm camera mới trên trang Quản Lý Camera của AIOC là gì?")
    assert len(res_add) > 0
    assert res_add[0]["id"] in {"aioc.add_camera", "devices.add_camera"}

    # 4. Phân biệt VMS vs devices
    res_diff = retrieve_docs("Vẽ sơ đồ phân biệt: hỏi thống kê sự kiện VMS (Postgres) với hỏi hướng dẫn dùng trang devices trên AIOC.")
    assert len(res_diff) > 0
    assert res_diff[0]["id"] == "aioc.vms_vs_devices"


@patch("src.knowledge.answer.use_offline_tools", return_value=True)
def test_answer_from_docs_offline_case_015(_mock_offline):
    """Offline answer cho case 015 phải chứa 'trực tuyến' từ card content."""
    q = "Trên AIOC devices, trạng thái camera Trực Tuyến / Ngoại Tuyến / Bảo Trì nghĩa là gì và đổi ở đâu?"
    ans = answer_from_docs(q)
    assert isinstance(ans, DocsAnswer)
    assert "trực tuyến" in ans.answer_vi.lower()
    assert "aioc.camera_status" in ans.card_ids


@patch("src.knowledge.answer.use_offline_tools", return_value=True)
def test_answer_from_docs_offline_case_017(_mock_offline):
    """Offline answer cho case 017 phải chứa 'camera' từ card content."""
    q = "Vẽ sơ đồ quy trình thêm một camera mới trên AIOC (từ mở form đến tạo xong)."
    ans = answer_from_docs(q)
    assert isinstance(ans, DocsAnswer)
    assert "camera" in ans.answer_vi.lower()
    assert any("diagram_add_camera" in cid or "add_camera" in cid for cid in ans.card_ids)


def test_offline_answer_from_cards_empty_fallback():
    """Kiểm tra fallback khi không có cards nào truyền vào."""
    ans = _offline_answer_from_cards("Thời tiết thế nào?", [])
    assert isinstance(ans, DocsAnswer)
    assert ans.card_ids == []
    assert "không tìm thấy hướng dẫn" in ans.answer_vi.lower()


def test_dataset_catalog_loads_and_case_010_maps_to_fire_smoke_event():
    """Kiểm tra dataset_catalog.yaml tải được và case agent_stat_v2_010 map tới fire_smoke_event."""
    cat = load_dataset_catalog()
    assert cat.get("schema_version") == "1.0.0"
    assert "cases" in cat

    hint_010 = get_case_hints("agent_stat_v2_010")
    assert isinstance(hint_010, dict)
    assert hint_010.get("table") == "fire_smoke_event"


def test_dataset_catalog_key_fail_cases_hints():
    """Kiểm tra dataset catalog có hints cho các key fail cases 008, 009, 011, 015, 017, 023, 024."""
    key_cases = [
        "agent_stat_v2_008",
        "agent_stat_v2_009",
        "agent_stat_v2_010",
        "agent_stat_v2_011",
        "agent_stat_v2_015",
        "agent_stat_v2_017",
        "agent_stat_v2_023",
        "agent_stat_v2_024",
    ]
    for cid in key_cases:
        hints = get_case_hints(cid)
        assert hints != {}, f"Thiếu hint cho {cid}"

    # Kiểm tra helper get_table_for_keywords
    assert get_table_for_keywords("cháy nổ tại cơ sở") == "fire_smoke_event"
    assert get_table_for_keywords("phát hiện đám đông") == "anomaly_event"
    assert get_table_for_keywords("hôm nay leo trèo hàng rào") == "anomaly_event"
    assert get_table_for_keywords("mực nước ngập sâu") == "anomaly_event"


def test_clear_dataset_catalog_cache():
    """Kiểm tra clear_dataset_catalog_cache hoạt động bình thường."""
    cat1 = load_dataset_catalog()
    clear_dataset_catalog_cache()
    cat2 = load_dataset_catalog()
    assert cat1 == cat2

# ==============================================================================
# --- Sourced from test_docs.py ---
# ==============================================================================

"""Offline unit tests cho Phase 2.4 — Docs YAML (duy style): loader, retrieval, answer_from_docs."""


from unittest.mock import MagicMock, patch

import pytest

from src.agent.docs import handle_docs_intent
from src.knowledge.answer import _offline_answer_from_cards, answer_from_docs
from src.knowledge.loader import (
    clear_docs_cache,
    docs_root,
    load_index,
    load_published_cards,
    load_vms_cards,
)
from src.knowledge.retrieval import card_excerpt_for_llm, retrieve_docs
from src.llm.schemas import DocsAnswer


def test_docs_root_and_load_published_cards():
    """Kiểm tra docs_root tồn tại và load đúng 40 cards published VMS cùng merged cards."""
    root = docs_root()
    assert root.exists()
    assert "resource" in root.parts
    assert root.as_posix().endswith("resource/docs/vms_yaml")
    assert (root / "index.yaml").exists()

    index = load_index()
    assert index.get("schema_version") == "1.0.0"

    vms_cards = load_vms_cards()
    assert len(vms_cards) == 40

    cards = load_published_cards()
    assert len(cards) == 47

    # Kiểm tra card needs_review (ai.search_face_journey) không được load
    card_ids = {c.get("id") for c in cards}
    assert "ai.search_face_journey" not in card_ids

    # Kiểm tra các trường thiết yếu
    for card in cards:
        assert card.get("id")
        assert card.get("title")
        assert card.get("type") in {"how_to", "troubleshooting", "concept"}
        assert card.get("_file")


def test_clear_docs_cache():
    """Kiểm tra hàm clear_docs_cache hoạt động bình thường."""
    cards_before = load_published_cards()
    clear_docs_cache()
    cards_after = load_published_cards()
    assert len(cards_before) == len(cards_after) == 47
    assert len(load_vms_cards()) == 40


def test_retrieve_docs_known_how_to():
    """Kiểm tra keyword retrieval tìm đúng task card cho các câu hỏi how-to phổ biến."""
    # 1. Thêm camera
    res_add_cam = retrieve_docs("Làm thế nào để thêm camera mới vào hệ thống?")
    assert len(res_add_cam) > 0
    assert res_add_cam[0]["id"] == "devices.add_camera"

    # 2. Xem lại camera
    res_playback = retrieve_docs("Hướng dẫn xem lại camera playback hôm qua")
    assert len(res_playback) > 0
    assert res_playback[0]["id"] == "operations.view_playback"

    # 3. Quên mật khẩu / đặt lại mật khẩu
    res_reset = retrieve_docs("Quên mật khẩu đăng nhập")
    assert len(res_reset) > 0
    assert res_reset[0]["id"] == "auth.reset_password"


def test_retrieve_docs_unknown_returns_empty():
    """Kiểm tra các câu hỏi ngoài lề hoặc rỗng trả về danh sách rỗng."""
    assert retrieve_docs("Thời tiết Hà Nội hôm nay thế nào?") == []
    assert retrieve_docs("Cách nấu phở bò truyền thống") == []
    assert retrieve_docs("") == []


def test_card_excerpt_for_llm():
    """Kiểm tra card_excerpt_for_llm rút gọn đúng các trường cốt lõi."""
    cards = retrieve_docs("thêm camera")
    assert cards
    excerpt = card_excerpt_for_llm(cards[0])
    assert excerpt["id"] == "devices.add_camera"
    assert excerpt["title"]
    assert "steps" in excerpt
    assert "_file" not in excerpt


def test_answer_from_docs_offline_with_cards():
    """Kiểm tra answer_from_docs chế độ offline khi có cards trả về DocsAnswer đầy đủ."""
    cards = retrieve_docs("thêm camera")
    ans = answer_from_docs("Cách thêm camera", cards)

    assert isinstance(ans, DocsAnswer)
    assert "devices.add_camera" in ans.card_ids
    assert ans.steps is not None
    assert len(ans.steps) > 0
    assert "Thêm camera" in ans.answer_vi
    assert "Đường dẫn menu" in ans.answer_vi


def test_answer_from_docs_offline_empty_cards():
    """Kiểm tra answer_from_docs khi không có card nào trả về thông báo tiếng Việt rõ ràng."""
    ans = answer_from_docs("Thời tiết hôm nay", [])
    assert isinstance(ans, DocsAnswer)
    assert ans.card_ids == []
    assert ans.steps is None
    assert "không tìm thấy hướng dẫn" in ans.answer_vi.lower() or "chưa có thông tin" in ans.answer_vi.lower()


@patch("src.knowledge.answer.use_offline_tools", return_value=False)
@patch("src.knowledge.answer.invoke_structured")
def test_answer_from_docs_online_mock_structured(mock_structured, mock_offline):
    """Kiểm tra answer_from_docs chế độ online gọi invoke_structured đúng schema."""
    expected_answer = DocsAnswer(
        answer_vi="Bước 1: Mở Quản lý camera. Bước 2: Nhấn Thêm camera.",
        card_ids=["devices.add_camera"],
        steps=["Mở Quản lý camera", "Nhấn Thêm camera"],
    )
    mock_structured.return_value = expected_answer

    cards = retrieve_docs("thêm camera")
    res = answer_from_docs("Làm sao thêm camera?", cards)

    assert res == expected_answer
    assert mock_structured.call_count == 1
    args, kwargs = mock_structured.call_args
    assert args[1] is DocsAnswer
    messages = args[0]
    assert any("Bạn là trợ lý hướng dẫn sử dụng hệ thống VMS" in m["content"] for m in messages if m["role"] == "system")


@patch("src.knowledge.answer.use_offline_tools", return_value=False)
@patch("src.knowledge.answer.invoke_structured", side_effect=RuntimeError("LLM API timeout"))
def test_answer_from_docs_online_failure_fallback(mock_structured, mock_offline):
    """Kiểm tra khi invoke_structured lỗi thì fallback sang offline heuristic thay vì crash."""
    cards = retrieve_docs("thêm camera")
    res = answer_from_docs("Làm sao thêm camera?", cards)

    assert isinstance(res, DocsAnswer)
    assert "devices.add_camera" in res.card_ids
    assert len(res.steps or []) > 0
    assert "Thêm camera" in res.answer_vi


def test_handle_docs_intent_adapter():
    """Kiểm tra adapter handle_docs_intent trả về chuỗi str cho graph v4."""
    ans_text = handle_docs_intent("Làm sao thêm camera?")
    assert isinstance(ans_text, str)
    assert "Thêm camera" in ans_text

    ans_empty = handle_docs_intent("Thời tiết ngày mai")
    assert isinstance(ans_empty, str)
    assert "không tìm thấy hướng dẫn" in ans_empty.lower() or "chưa có thông tin" in ans_empty.lower()


def test_how_to_path_does_not_call_db():
    """Kiểm tra nhánh how-to tài liệu VMS hoàn toàn không gọi DB."""
    with patch("src.db.executor.execute_sql") as mock_exec, \
         patch("src.db.connection.get_connection") as mock_conn:
        ans = handle_docs_intent("Làm thế nào để thêm camera?")
        assert ans != ""
        mock_exec.assert_not_called()
        mock_conn.assert_not_called()

    # Thử gọi qua Agent graph v4
    from src.agent.graph import Agent_Input, run_agent
    with patch("src.db.executor.execute_sql") as mock_exec, \
         patch("src.db.connection.get_connection") as mock_conn, \
         patch("src.agent.intent.use_offline_tools", return_value=False), \
         patch("src.agent.intent.invoke_structured") as mock_intent:
        from src.llm.schemas import IntentResult
        mock_intent.return_value = IntentResult(intent="how_to", reason="hỏi hướng dẫn")

        inp = Agent_Input(question="Cách xem lại camera")
        out = run_agent(inp)

        assert out.detail == "docs"
        assert "xem lại" in out.answer.lower() or "playback" in out.answer.lower()
        mock_exec.assert_not_called()
        mock_conn.assert_not_called()

# ==============================================================================
# --- Sourced from test_pre_sql_retrieval.py ---
# ==============================================================================

"""Tests for scoped catalog retrieval (select_relevant_tables) and scoped retrieve_schema — Phase 3b."""


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

# ==============================================================================
# --- Sourced from test_phase3b_pre_sql_context.py ---
# ==============================================================================

"""Phase 3b acceptance tests — Pre-SQL context assertions.

Covers ALL four checklist items from Phase 3b final pytest task:

  a) Excerpt smaller than full catalog:
       retrieve_schema_node / select_relevant_tables + build_schema_excerpt for a
       single-domain vehicle question yields an excerpt smaller than the full
       catalog; related table present; unrelated tables absent.

  b) time_range in context:
       Online-mocked generate_sql_node (use_offline_tools=False + mock invoke_text)
       with RewrittenQuestion(time_range="today") → user prompt contains
       time_range hint ("Khoảng thời gian" / "time_range": today).

  c) chart hint in context:
       Same style mock with chart question ("Vẽ biểu đồ…") → user prompt
       contains chart hint (GROUP BY / vehicle_type or generic GROUP BY).
       One combined test has BOTH time_range + chart hint in the same user
       prompt (order: time → chart → schema → question).

  d) Graph-level offline stream/node smoke:
       retrieve_schema event has selected_tables ≤ 4 and schema_excerpt scoped.

All tests run offline / mocked — no live LLM or DB required.
"""


import uuid
from unittest.mock import patch

import pytest

from src.agent.generate_sql import generate_sql_node
from src.agent.graph import retrieve_schema_node
from src.db.catalog import build_schema_excerpt, select_relevant_tables
from src.llm.schemas import RewrittenQuestion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FULL_CATALOG_TABLES = [
    "plate_event",
    "zone_event",
    "smf_face_events",
    "fire_smoke_event",
    "anomaly_event",
]


def _full_catalog_excerpt() -> str:
    return build_schema_excerpt()


# ---------------------------------------------------------------------------
# a) Excerpt smaller than full catalog
# ---------------------------------------------------------------------------


class TestExcerptSmallerThanFullCatalog:
    """Assert scoped excerpt is strictly smaller than full catalog."""

    def test_single_domain_vehicle_excerpt_smaller_than_full(self):
        """select_relevant_tables + build_schema_excerpt for vehicle question
        yields excerpt smaller than full catalog; plate_event present;
        unrelated tables absent."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Hôm nay có bao nhiêu lượt xe vào cổng?", limit=4)

        assert len(tables) <= 4
        assert "plate_event" in tables

        scoped = build_schema_excerpt(tables)
        assert len(scoped) < len(full), (
            f"Scoped excerpt length {len(scoped)} must be < full catalog {len(full)}"
        )
        assert "Table: plate_event" in scoped
        # Unrelated tables must be absent
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in scoped, f"Unrelated table {tbl!r} found in scoped excerpt"

    def test_retrieve_schema_node_vehicle_scoped_smaller_than_full(self):
        """retrieve_schema_node for a vehicle question yields scoped excerpt
        (uses plate_event only) that is strictly smaller than full catalog."""
        full = _full_catalog_excerpt()
        state = {
            "question": "Có bao nhiêu xe tải qua cổng hôm nay?",
            "rewritten": RewrittenQuestion(text="Có bao nhiêu xe tải qua cổng hôm nay?"),
            "intent": "query_data",
            "user_id": "u-test",
            "session_id": "s-test",
        }
        result = retrieve_schema_node(state)

        assert "schema_excerpt" in result
        excerpt = result["schema_excerpt"]
        selected = result.get("selected_tables", [])

        # Must select ≤ 4 tables
        assert len(selected) <= 4
        # plate_event must be included for a vehicle question
        assert "plate_event" in selected
        # Excerpt strictly smaller than full catalog
        assert len(excerpt) < len(full), (
            f"Scoped excerpt ({len(excerpt)} chars) must be < full catalog ({len(full)} chars)"
        )
        assert "Table: plate_event" in excerpt
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in excerpt

    def test_fire_domain_excerpt_smaller_than_full(self):
        """Fire-domain question yields excerpt smaller than full, fire_smoke_event present."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Phát hiện khói ở khu vực nào hôm nay?", limit=4)
        scoped = build_schema_excerpt(tables)

        assert len(scoped) < len(full)
        assert "Table: fire_smoke_event" in scoped
        assert "Table: plate_event" not in scoped

    def test_face_domain_excerpt_smaller_than_full(self):
        """Face-domain question yields excerpt smaller than full, smf_face_events present."""
        full = _full_catalog_excerpt()
        tables = select_relevant_tables("Hôm nay có bao nhiêu người chấm công khuôn mặt?", limit=4)
        scoped = build_schema_excerpt(tables)

        assert len(scoped) < len(full)
        assert "Table: smf_face_events" in scoped
        assert "Table: plate_event" not in scoped

    def test_full_catalog_excerpt_contains_all_tables(self):
        """Sanity: full catalog excerpt contains all 5 tables."""
        full = _full_catalog_excerpt()
        for tbl in _FULL_CATALOG_TABLES:
            assert f"Table: {tbl}" in full, f"Full catalog must include Table: {tbl}"


# ---------------------------------------------------------------------------
# b) time_range in context
# ---------------------------------------------------------------------------


class TestTimeRangeInContext:
    """Assert time_range hint appears in generate_sql_node user prompt."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_time_range_today_in_user_message(self, mock_invoke, _mock_offline):
        """generate_sql online mock: RewrittenQuestion(time_range='today') →
        user prompt contains 'Khoảng thời gian (time_range): today'."""
        rewritten = RewrittenQuestion(
            text="Hôm nay có bao nhiêu xe vào?",
            filters=["direction=IN"],
            time_range="today",
        )
        state = {
            "question": "Hôm nay có bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event\nColumns: event_time, direction",
        }
        generate_sql_node(state)

        assert mock_invoke.called
        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian (time_range): today" in user_prompt, (
            f"time_range hint missing from user prompt:\n{user_prompt[:500]}"
        )
        assert "today" in user_prompt
        assert "CURRENT_DATE" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_time_range_yesterday_in_user_message(self, mock_invoke, _mock_offline):
        """generate_sql: time_range='yesterday' → user prompt contains yesterday hint."""
        rewritten = RewrittenQuestion(
            text="Hôm qua bao nhiêu xe ra?",
            time_range="yesterday",
        )
        state = {
            "question": "Hôm qua bao nhiêu xe ra?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian (time_range): yesterday" in user_prompt
        assert "CURRENT_DATE - 1" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_no_time_range_when_none(self, mock_invoke, _mock_offline):
        """generate_sql: time_range=None → user prompt does NOT contain time_range hint."""
        rewritten = RewrittenQuestion(text="Bao nhiêu xe vào?", time_range=None)
        state = {
            "question": "Bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "Khoảng thời gian" not in user_prompt
        # Schema and question still present
        assert "Table: plate_event" in user_prompt
        assert "Bao nhiêu xe vào?" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_schema_and_question_always_in_user_message(self, mock_invoke, _mock_offline):
        """Regardless of time_range, schema_excerpt and question text are always present."""
        for tr in ("today", None):
            mock_invoke.reset_mock()
            rewritten = RewrittenQuestion(text="Đếm xe tải vào hôm nay", time_range=tr)
            state = {
                "question": "Đếm xe tải vào hôm nay",
                "rewritten": rewritten,
                "schema_excerpt": "Table: plate_event\nColumns: vehicle_type",
            }
            generate_sql_node(state)

            user_prompt = mock_invoke.call_args[0][1]

            assert "Table: plate_event" in user_prompt, f"Schema missing (time_range={tr})"
            assert "Đếm xe tải vào hôm nay" in user_prompt, f"Question missing (time_range={tr})"


# ---------------------------------------------------------------------------
# c) chart hint in context
# ---------------------------------------------------------------------------


class TestChartHintInContext:
    """Assert chart hint appears in generate_sql_node user prompt for chart questions."""

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type")
    def test_chart_hint_in_user_message_for_bieu_do(self, mock_invoke, _mock_offline):
        """generate_sql online mock: chart question → user prompt contains GROUP BY hint."""
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ cột lượt xe theo loại hôm nay",
            time_range=None,
        )
        state = {
            "question": "Vẽ biểu đồ cột lượt xe theo loại hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower(), (
            f"GROUP BY hint missing from chart question user prompt:\n{user_prompt[:500]}"
        )
        assert "vehicle_type" in user_prompt

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT count(*) FROM plate_event")
    def test_no_chart_hint_for_plain_count(self, mock_invoke, _mock_offline):
        """generate_sql: plain count question (no 'biểu đồ') → no chart hint in user prompt."""
        rewritten = RewrittenQuestion(text="Hôm nay có bao nhiêu xe vào?", time_range=None)
        state = {
            "question": "Hôm nay có bao nhiêu xe vào?",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        # Chart-specific marker absent
        assert "Yêu cầu biểu đồ" not in user_prompt

    # --- Combined: BOTH time_range + chart hint in the SAME user message ---

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT vehicle_type, count(*) FROM plate_event GROUP BY vehicle_type")
    def test_combined_time_range_and_chart_hint_in_user_message(self, mock_invoke, _mock_offline):
        """COMBINED — Both time_range AND chart hint present in user prompt.
        Order must be: time_range hint → chart hint → schema excerpt → question.
        """
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ số lượng xe theo loại hôm nay",
            filters=["direction=IN"],
            time_range="today",
        )
        state = {
            "question": "Vẽ biểu đồ số lượng xe theo loại hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: plate_event\nColumns: vehicle_type, event_time",
        }
        generate_sql_node(state)

        assert mock_invoke.called
        user_prompt = mock_invoke.call_args[0][1]

        # 1. time_range hint present
        assert "Khoảng thời gian (time_range): today" in user_prompt, (
            f"time_range hint missing:\n{user_prompt[:600]}"
        )
        # 2. chart hint present
        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower(), (
            f"chart GROUP BY hint missing:\n{user_prompt[:600]}"
        )
        assert "vehicle_type" in user_prompt
        # 3. schema excerpt present
        assert "Table: plate_event" in user_prompt
        # 4. question present
        assert "Vẽ biểu đồ số lượng xe theo loại hôm nay" in user_prompt

        # Order check: time_range before chart hint before schema before question
        pos_time = user_prompt.index("Khoảng thời gian")
        chart_marker = "Yêu cầu biểu đồ"
        if chart_marker in user_prompt:
            pos_chart = user_prompt.index(chart_marker)
        else:
            pos_chart = user_prompt.upper().index("GROUP BY")
        pos_schema = user_prompt.index("Table: plate_event")
        pos_question = user_prompt.index("Vẽ biểu đồ số lượng xe theo loại hôm nay")

        assert pos_time < pos_chart, "time_range hint must appear before chart hint"
        assert pos_chart < pos_schema, "chart hint must appear before schema excerpt"
        assert pos_schema < pos_question, "schema excerpt must appear before question"

    @patch("src.agent.generate_sql.use_offline_tools", return_value=False)
    @patch("src.agent.generate_sql.invoke_text", return_value="SELECT entity_type, count(*) FROM fire_smoke_event GROUP BY entity_type")
    def test_generic_chart_hint_non_vehicle_domain(self, mock_invoke, _mock_offline):
        """Non-vehicle chart question → generic GROUP BY hint (no vehicle_type push)."""
        rewritten = RewrittenQuestion(
            text="Vẽ biểu đồ thống kê sự kiện cháy khói hôm nay",
            time_range="today",
        )
        state = {
            "question": "Vẽ biểu đồ thống kê sự kiện cháy khói hôm nay",
            "rewritten": rewritten,
            "schema_excerpt": "Table: fire_smoke_event\nColumns: entity_type, event_time",
        }
        generate_sql_node(state)

        user_prompt = mock_invoke.call_args[0][1]

        # Generic GROUP BY hint present
        assert "GROUP BY" in user_prompt.upper() or "group by" in user_prompt.lower()
        # vehicle_type NOT pushed for a fire question
        assert "vehicle_type" not in user_prompt


# ---------------------------------------------------------------------------
# d) Graph-level offline stream/node smoke
# ---------------------------------------------------------------------------


class TestGraphLevelOfflineSmoke:
    """Graph offline stream smoke: retrieve_schema event has ≤4 selected_tables
    and a scoped schema_excerpt."""

    def test_graph_retrieve_schema_event_scoped_vehicle(self):
        """Offline graph stream: retrieve_schema event for vehicle question has
        selected_tables ≤ 4 and scoped schema_excerpt (plate_event present,
        unrelated absent)."""
        from src.agent.graph import Agent_Input, run_agent_stream

        full_len = len(_full_catalog_excerpt())
        inp = Agent_Input(question="Hôm nay có bao nhiêu lượt xe vào?")
        mock_rows = [{"so_luot": 5}]
        with (
            patch("src.llm.client.use_offline_tools", return_value=True),
            patch("src.agent.graph.execute_sql", return_value=mock_rows),
        ):
            events = list(run_agent_stream(inp, session_id=f"smoke-{uuid.uuid4().hex}"))

        schema_events = [
            ev for ev in events
            if ev.get("node_id") == "retrieve_schema" and ev.get("status") == "done"
        ]
        assert len(schema_events) == 1, f"Expected 1 retrieve_schema done event, got {len(schema_events)}"

        ev = schema_events[0]
        output = ev.get("output", {})
        selected = output.get("selected_tables", [])
        excerpt = output.get("schema_excerpt", "")

        # selected_tables ≤ 4
        assert len(selected) <= 4, f"selected_tables exceeds 4: {selected}"
        # plate_event selected for vehicle question
        assert "plate_event" in selected, f"plate_event missing from {selected}"
        # schema_excerpt scoped (shorter than full)
        assert len(excerpt) < full_len, (
            f"Scoped excerpt ({len(excerpt)} chars) must be < full catalog ({full_len} chars)"
        )
        assert "Table: plate_event" in excerpt
        for tbl in ("fire_smoke_event", "smf_face_events", "zone_event", "anomaly_event"):
            assert f"Table: {tbl}" not in excerpt, f"Unrelated {tbl} found in scoped excerpt"

    def test_graph_retrieve_schema_event_scoped_fire(self):
        """Offline graph stream: retrieve_schema for fire question → fire_smoke_event selected."""
        from src.agent.graph import Agent_Input, run_agent_stream

        inp = Agent_Input(question="Có cảnh báo cháy nào hôm nay không?")
        mock_rows = [{"so_luot": 0}]
        with (
            patch("src.llm.client.use_offline_tools", return_value=True),
            patch("src.agent.graph.execute_sql", return_value=mock_rows),
        ):
            events = list(run_agent_stream(inp, session_id=f"smoke-{uuid.uuid4().hex}"))

        schema_events = [
            ev for ev in events
            if ev.get("node_id") == "retrieve_schema" and ev.get("status") == "done"
        ]
        assert len(schema_events) == 1

        output = schema_events[0].get("output", {})
        selected = output.get("selected_tables", [])
        excerpt = output.get("schema_excerpt", "")

        assert len(selected) <= 4
        assert "fire_smoke_event" in selected
        assert "Table: fire_smoke_event" in excerpt
        assert "Table: plate_event" not in excerpt

    def test_retrieve_schema_node_selected_tables_max_4_all_domains(self):
        """retrieve_schema_node never returns more than 4 tables for any question."""
        questions = [
            "Hôm nay có bao nhiêu lượt xe vào và cảnh báo cháy?",
            "Thống kê tất cả các sự kiện trong KCN",
            "Xe vào + chấm công + cháy + xâm nhập hôm nay",
            "ALPR và fire smoke và zone và face và anomaly",
        ]
        for q in questions:
            state = {"question": q}
            result = retrieve_schema_node(state)
            selected = result.get("selected_tables", [])
            assert len(selected) <= 4, f"selected_tables > 4 for {q!r}: {selected}"

# ==============================================================================
# --- Sourced from test_resource_paths.py ---
# ==============================================================================

"""Phase 1 — resource/ layout và default paths."""

from pathlib import Path

from src.config import get_settings
from src.db.catalog import get_catalog
from src.prompts.registry import registry


def test_resource_dirs_exist():
    root = Path(__file__).resolve().parent.parent
    assert (root / "resource" / "prompts").is_dir()
    assert (root / "resource" / "docs" / "vms_yaml" / "index.yaml").is_file()
    assert (root / "resource" / "db" / "catalog.yaml").is_file()


def test_default_docs_root_and_prompts_dir():
    settings = get_settings()
    assert settings.docs_root == "resource/docs/vms_yaml"
    assert (settings.effective_docs_root / "index.yaml").exists()

    reg = registry()
    assert reg.prompts_dir.name == "prompts"
    assert reg.prompts_dir.parent.name == "resource"
    assert (reg.prompts_dir / "sql_agent" / "production.txt").exists()


def test_catalog_loads_from_yaml():
    catalog = get_catalog()
    assert "plate_event" in catalog
    assert "fire_smoke_event" in catalog

