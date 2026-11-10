"""Camera Master Registry helper — VMS KCN Hưng Phú (dong v8).

Đồng bộ Master Data từ resource/db/camera_registry.yaml (10 camera ONLINE).
Hỗ trợ fast-path trả lời số lượng và danh sách camera toàn hệ thống.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import yaml
logger = logging.getLogger(__name__)
REGISTRY_PATH = Path(__file__).resolve().parents[6] / 'resource' / 'db' / 'camera_registry.yaml'
FALLBACK_CAMERAS: list[dict[str, Any]] = [{'camera_code': 'CVN_CONG_BOH', 'camera_name': 'Cổng Ra Vào BOH', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT VÙNG CẤM'}, {'camera_code': 'CVN_KHO_TANG2_BOH', 'camera_name': 'CVN_KHO_TANG2_BOH', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'CẢNH BÁO CHÁY KHÓI'}, {'camera_code': 'CVN_P_CAP_PHAT_DONG_PHUC', 'camera_name': 'CVN_P_CAP_PHAT_DONG_PHUC', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'CẢNH BÁO CHÁY KHÓI'}, {'camera_code': 'CVNTT', 'camera_name': 'CVNTT', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT VÙNG CẤM'}, {'camera_code': 'congvanle4', 'camera_name': 'congvanle4', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}, {'camera_code': 'congvanle3', 'camera_name': 'congvanle3', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}, {'camera_code': 'congvanle2', 'camera_name': 'congvanle2', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}, {'camera_code': 'congvanle1', 'camera_name': 'congvanle1', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}, {'camera_code': 'congchinh2', 'camera_name': 'congchinh2', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}, {'camera_code': 'congchinh1', 'camera_name': 'congchinh1', 'area': 'Sản xuất & lắp ráp', 'status': 'ONLINE', 'ai_service': 'GIÁM SÁT PHƯƠNG TIỆN'}]

def load_camera_registry() -> dict[str, Any]:
    """Đọc camera_registry.yaml an toàn, có fallback nếu thiếu hoặc lỗi định dạng."""
    if REGISTRY_PATH.exists():
        try:
            content = REGISTRY_PATH.read_text(encoding='utf-8')
            data = yaml.safe_load(content)
            if isinstance(data, dict) and (data['cameras'] if 'cameras' in data else None):
                return data
        except Exception as exc:
            logger.warning('Lỗi đọc camera_registry.yaml, dùng fallback: %s', exc)
    return {'organization_id': 103, 'organization_name': 'Tập đoàn GELEXIMCO - KCN Hưng Phú', 'area_name': 'Sản xuất & lắp ráp', 'total_cameras': len(FALLBACK_CAMERAS), 'cameras': FALLBACK_CAMERAS, 'virtual_zones': [{'zone_code': 'POLY_789629', 'camera_name': 'Cổng Ra Vào BOH', 'camera_code': 'CVN_CONG_BOH'}, {'zone_code': 'POLY_393453', 'camera_name': 'hàng rào 01', 'camera_code': 'hang_rao_01'}]}

def is_camera_count_query(question: str) -> bool:
    """Kiểm tra câu hỏi có phải hỏi tổng số camera / số lượng camera đang hoạt động không."""
    q_low = question.lower()
    has_cam = any((k in q_low for k in ('camera', 'cam')))
    if not has_cam:
        return False
    if any((k in q_low for k in ('phương tiện', 'biển số', 'plate', 'xe cộ'))):
        return False
    count_keywords = ('bao nhiêu', 'mấy camera', 'mấy cái camera', 'số lượng', 'đếm', 'tổng số', 'có bao nhiêu')
    return any((k in q_low for k in count_keywords))

def is_camera_list_query(question: str) -> bool:
    """Kiểm tra câu hỏi có phải yêu cầu liệt kê danh sách camera trong hệ thống không."""
    q_low = question.lower()
    has_cam = any((k in q_low for k in ('camera', 'cam')))
    if not has_cam:
        return False
    if any((k in q_low for k in ('phương tiện', 'biển số', 'plate'))):
        return False
    list_keywords = ('danh sách', 'kể tên', 'ke ten', 'liệt kê', 'liet ke', 'tên các camera', 'các camera', 'những camera nào', 'gồm những camera', 'tất cả camera', 'hiện có camera nào')
    return any((k in q_low for k in list_keywords))

def format_camera_count_answer(registry_data: dict[str, Any] | None=None) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Trả về (answer_text, rows, columns) cho câu hỏi đếm camera."""
    reg = registry_data or load_camera_registry()
    cams = reg['cameras'] if 'cameras' in reg else FALLBACK_CAMERAS
    v_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'GIÁM SÁT PHƯƠNG TIỆN']
    z_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'GIÁM SÁT VÙNG CẤM']
    f_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'CẢNH BÁO CHÁY KHÓI']

    def _cam_label(c: dict[str, Any]) -> str:
        name = c['camera_name'] if 'camera_name' in c else ''
        code = c['camera_code'] if 'camera_code' in c else ''
        if name and code and (name != code):
            return f'{name} ({code})'
        return name or code
    v_str = ', '.join((_cam_label(c) for c in v_cams))
    z_str = ', '.join((_cam_label(c) for c in z_cams))
    f_str = ', '.join((_cam_label(c) for c in f_cams))
    total = len(cams)
    ans = f'Hiện tại hệ thống có {total} camera đang hoạt động (ONLINE), thuộc 3 phân hệ:\n- {len(v_cams)} camera giám sát phương tiện ({v_str})\n- {len(z_cams)} camera giám sát vùng cấm ({z_str})\n- {len(f_cams)} camera cảnh báo cháy khói ({f_str})'
    columns = ['camera_code', 'camera_name', 'area', 'status', 'ai_service']
    rows = [{'camera_code': c['camera_code'] if 'camera_code' in c else '', 'camera_name': c['camera_name'] if 'camera_name' in c else '', 'area': c['area'] if 'area' in c else reg['area_name'] if 'area_name' in reg else 'Sản xuất & lắp ráp', 'status': c['status'] if 'status' in c else 'ONLINE', 'ai_service': c['ai_service'] if 'ai_service' in c else ''} for c in cams]
    return (ans, rows, columns)

def format_camera_list_answer(registry_data: dict[str, Any] | None=None) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Trả về (answer_text, rows, columns) cho câu hỏi liệt kê camera."""
    reg = registry_data or load_camera_registry()
    cams = reg['cameras'] if 'cameras' in reg else FALLBACK_CAMERAS
    v_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'GIÁM SÁT PHƯƠNG TIỆN']
    z_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'GIÁM SÁT VÙNG CẤM']
    f_cams = [c for c in cams if (c['ai_service'] if 'ai_service' in c else None) == 'CẢNH BÁO CHÁY KHÓI']

    def _cam_label(c: dict[str, Any]) -> str:
        name = c['camera_name'] if 'camera_name' in c else ''
        code = c['camera_code'] if 'camera_code' in c else ''
        if name and code and (name != code):
            return f'{name} ({code})'
        return name or code
    total = len(cams)
    v_str = ', '.join((_cam_label(c) for c in v_cams))
    z_str = ', '.join((_cam_label(c) for c in z_cams))
    f_str = ', '.join((_cam_label(c) for c in f_cams))
    ans = f'Danh sách {total} camera đang hoạt động (ONLINE) trong hệ thống KCN Hưng Phú:\n- Giám sát phương tiện ({len(v_cams)} camera): {v_str}\n- Giám sát vùng cấm ({len(z_cams)} camera): {z_str}\n- Cảnh báo cháy khói ({len(f_cams)} camera): {f_str}'
    columns = ['camera_code', 'camera_name', 'area', 'status', 'ai_service']
    rows = [{'camera_code': c['camera_code'] if 'camera_code' in c else '', 'camera_name': c['camera_name'] if 'camera_name' in c else '', 'area': c['area'] if 'area' in c else reg['area_name'] if 'area_name' in reg else 'Sản xuất & lắp ráp', 'status': c['status'] if 'status' in c else 'ONLINE', 'ai_service': c['ai_service'] if 'ai_service' in c else ''} for c in cams]
    return (ans, rows, columns)
