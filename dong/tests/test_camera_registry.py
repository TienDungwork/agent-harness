"""Unit tests cho Master Registry 10 Camera (dong v8 Phase 3).

Kiểm tra:
- AC-1: Đếm đủ 10 camera ONLINE thuộc 3 phân hệ.
- AC-2: Liệt kê đủ 10 camera cả mã đặc thù (CVN_CONG_BOH, CVNTT...).
- Fallback an toàn khi file yaml bị lỗi hoặc thiếu.
- Cấu trúc rows/columns trong QueryResult.
"""

from __future__ import annotations

from unittest.mock import patch
from src.agent.camera_registry import (
    load_camera_registry,
    is_camera_count_query,
    is_camera_list_query,
    format_camera_count_answer,
    format_camera_list_answer,
    FALLBACK_CAMERAS,
)
from src.agent.graph import Agent_Input, run_agent


def test_load_camera_registry_success():
    """Đọc thành công 10 camera từ resource/db/camera_registry.yaml."""
    data = load_camera_registry()
    assert data["total_cameras"] == 10
    assert len(data["cameras"]) == 10
    cam_names = [c["camera_name"] for c in data["cameras"]]
    assert "Cổng Ra Vào BOH" in cam_names or "CVN_CONG_BOH" in [c["camera_code"] for c in data["cameras"]]
    assert "congchinh1" in cam_names


def test_load_camera_registry_fallback_on_error():
    """Khi file yaml bị thiếu hoặc lỗi cú pháp, tự động fallback an toàn."""
    with patch("pathlib.Path.exists", return_value=False):
        data = load_camera_registry()
        assert data["total_cameras"] == 10
        assert len(data["cameras"]) == len(FALLBACK_CAMERAS)


def test_load_camera_registry_corrupt_yaml_syntax():
    """Khi file yaml có lỗi cú pháp YAML, tự động bắt lỗi và fallback an toàn."""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value="invalid: yaml: [syntax error:"):
        data = load_camera_registry()
        assert data["total_cameras"] == 10
        assert len(data["cameras"]) == len(FALLBACK_CAMERAS)


def test_is_camera_count_query_detection():
    """Phát hiện chính xác các câu hỏi đếm camera toàn hệ thống."""
    assert is_camera_count_query("Hiện có bao nhiêu camera đang hoạt động?") is True
    assert is_camera_count_query("Có bao nhiêu camera trong hệ thống?") is True
    assert is_camera_count_query("Số lượng camera hiện có") is True
    assert is_camera_count_query("Hệ thống có mấy camera?") is True
    assert is_camera_count_query("Tổng số camera") is True

    # Không can thiệp nếu hỏi riêng camera phương tiện
    assert is_camera_count_query("Có bao nhiêu camera phương tiện?") is False
    assert is_camera_count_query("Bao nhiêu xe ra vào hôm nay?") is False


def test_is_camera_list_query_detection():
    """Phát hiện chính xác các câu hỏi liệt kê danh sách camera."""
    assert is_camera_list_query("Kể tên các camera trong hệ thống") is True
    assert is_camera_list_query("Danh sách camera") is True
    assert is_camera_list_query("Các camera trong hệ thống") is True
    assert is_camera_list_query("Liệt kê các camera") is True
    assert is_camera_list_query("Hệ thống gồm những camera nào") is True


def test_format_camera_count_answer_ac1():
    """AC-1: Đếm camera chuẩn xác 10 camera ONLINE thuộc 3 phân hệ."""
    ans, rows, columns = format_camera_count_answer()
    assert "10 camera đang hoạt động" in ans
    assert "6 camera giám sát phương tiện" in ans
    assert "2 camera giám sát vùng cấm" in ans
    assert "2 camera cảnh báo cháy khói" in ans
    assert len(rows) == 10
    assert "camera_code" in columns
    assert "camera_name" in columns


def test_format_camera_list_answer_ac2():
    """AC-2: Liệt kê đủ 10 camera với các mã đặc thù."""
    ans, rows, columns = format_camera_list_answer()
    assert "10 camera đang hoạt động" in ans
    assert "CVN_CONG_BOH" in ans
    assert "CVNTT" in ans
    assert "CVN_KHO_TANG2_BOH" in ans
    assert "CVN_P_CAP_PHAT_DONG_PHUC" in ans
    assert "congchinh1" in ans
    assert "congvanle4" in ans
    assert len(rows) == 10


def test_run_agent_camera_count_integration():
    """End-to-end: Hỏi số lượng camera -> Agent trả lời 10 camera."""
    out = run_agent(Agent_Input(question="Hiện có bao nhiêu camera đang hoạt động?"))
    assert "10 camera đang hoạt động" in out.answer
    assert "6 camera giám sát phương tiện" in out.answer
    assert "2 camera giám sát vùng cấm" in out.answer
    assert "2 camera cảnh báo cháy khói" in out.answer
    assert out.query is not None
    assert out.query.row_count == 10


def test_run_agent_camera_list_integration():
    """End-to-end: Hỏi danh sách camera -> Agent liệt kê đủ 10 camera."""
    out = run_agent(Agent_Input(question="Kể tên các camera trong hệ thống"))
    assert "10 camera đang hoạt động" in out.answer
    assert "CVN_CONG_BOH" in out.answer
    assert "CVNTT" in out.answer
    assert "CVN_KHO_TANG2_BOH" in out.answer
    assert "CVN_P_CAP_PHAT_DONG_PHUC" in out.answer
    assert "congchinh1" in out.answer
    assert out.query is not None
    assert out.query.row_count == 10
