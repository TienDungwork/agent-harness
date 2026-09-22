"""Unit tests cho Phase 3c — AIOC YAML task cards & dataset catalog."""

from __future__ import annotations

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
