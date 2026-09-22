"""Offline unit tests cho Phase 2.4 — Docs YAML (duy style): loader, retrieval, answer_from_docs."""

from __future__ import annotations

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
