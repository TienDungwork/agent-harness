"""Các câu SQL tham số hoá — mỗi hàm ứng với 1 tool trong src/agent/tools.py
(Phase 4).

Toàn bộ dùng placeholder %s (psycopg2 tự escape) — không nối chuỗi giá trị
người dùng vào SQL. Model chỉ chọn tool + điền tham số, KHÔNG tự sinh SQL cho
các câu hỏi khớp tool (an toàn + chính xác hơn Text-to-SQL tự do với model
nhỏ — xem README). Tool SQL fallback (Phase 4) sẽ có validate chặt riêng,
cho câu hỏi không khớp tool nào.

Aggregate CHẠY TRỰC TIẾP trên bảng raw (plate_event/zone_event), KHÔNG dùng
materialized view `plate_dashboard.pd_*` — job aggregate của mart đó đã
ngừng cập nhật (dừng ở 2026-09-07, raw data vẫn tiếp tục tới hiện tại) nên
mart không đáng tin. Nếu team backend sửa lại job aggregate, cân nhắc đọc
`pd_flow_daily`/`pd_vehicle_mix` cho khoảng thời gian dài (nhiều tháng) để
nhanh hơn — raw table vẫn ổn ở volume hiện tại nhờ index theo event_time.
"""

from __future__ import annotations

from src.config import settings
from src.db.connection import get_connection

_VEHICLE_TYPES = {"BUS", "CAR", "MOTORCYCLE", "TRUCK"}
_DIRECTIONS = {"IN", "OUT"}


def _org_filter() -> tuple[str, tuple]:
    if settings.db_organization_id:
        return "organization_id = %s", (settings.db_organization_id,)
    return "1=1", ()


_GROUP_COLUMNS = {
    "vehicle_type": "vehicle_type",
    "direction": "direction",
    "manufacturer": "manufacturer",
}


def count_vehicle_flow(
    date_from: str,
    date_to: str,
    direction: str | None,
    vehicle_type: str | None,
    group_by: str = "vehicle_type,direction",
) -> dict:
    """Đếm lượt xe ra/vào theo khoảng thời gian, group theo 1+ cột trong
    {vehicle_type, direction, manufacturer} (mặc định vehicle_type,direction).
    group_by="manufacturer" trả lượt xe theo hãng — nên kèm vehicle_type=CAR
    vì hãng xe chỉ có ý nghĩa với ô tô.

    GIỚI HẠN SCHEMA: vehicle_type chỉ có 4 giá trị (BUS/CAR/MOTORCYCLE/TRUCK)
    — DB KHÔNG phân loại ô tô theo số chỗ ngồi (5/7/9/16/29/40 chỗ). Câu hỏi
    kiểu "bao nhiêu xe 7 chỗ" không trả lời chính xác được bằng dữ liệu hiện
    có; Answer (Phase 4) cần nêu rõ giới hạn này thay vì bịa số theo số chỗ."""
    group_cols = [c.strip() for c in group_by.split(",") if c.strip()]
    invalid = [c for c in group_cols if c not in _GROUP_COLUMNS]
    if invalid or not group_cols:
        return {"error": f"group_by chỉ nhận {sorted(_GROUP_COLUMNS)}, nhận '{group_by}'."}

    org_sql, org_params = _org_filter()
    clauses = [org_sql, "event_time >= %s", "event_time < %s"]
    params: list = list(org_params) + [date_from, date_to]

    if direction:
        d = direction.strip().upper()
        if d not in _DIRECTIONS:
            return {"error": f"direction phải là IN/OUT, nhận '{direction}'."}
        clauses.append("direction = %s")
        params.append(d)

    if vehicle_type:
        v = vehicle_type.strip().upper()
        if v not in _VEHICLE_TYPES:
            return {"error": f"vehicle_type phải thuộc {sorted(_VEHICLE_TYPES)}, nhận '{vehicle_type}'."}
        clauses.append("vehicle_type = %s")
        params.append(v)

    if "manufacturer" in group_cols:
        clauses.append("manufacturer IS NOT NULL")

    select_cols = ", ".join(group_cols)
    sql = f"""
        SELECT {select_cols}, count(*) AS so_luot
        FROM plate_event
        WHERE {" AND ".join(clauses)}
        GROUP BY {select_cols}
        ORDER BY so_luot DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_its) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": [*group_cols, "so_luot"],
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
    }


def trace_plate(plate_text: str, date_from: str | None, date_to: str | None) -> dict:
    """Lịch sử di chuyển (camera, thời điểm, chiều ra/vào) của 1 biển số."""
    if not plate_text or not plate_text.strip():
        return {"error": "Thiếu plate_text."}
    normalized = "".join(ch for ch in plate_text.upper() if ch.isalnum())

    org_sql, org_params = _org_filter()
    clauses = [org_sql, "normalized_license_plate = %s"]
    params: list = list(org_params) + [normalized]

    if date_from:
        clauses.append("event_time >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("event_time < %s")
        params.append(date_to)

    sql = f"""
        SELECT event_time, camera_code, camera_name, direction, vehicle_type
        FROM plate_event
        WHERE {" AND ".join(clauses)}
        ORDER BY event_time DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_its) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": ["event_time", "camera_code", "camera_name", "direction", "vehicle_type"],
        "rows": [[str(v) for v in r] for r in rows],
        "row_count": len(rows),
    }


def zone_intrusion_by_hour(date_from: str, date_to: str, zone_code: str | None = None) -> dict:
    """Số lượt xâm nhập khu vực hàng rào ảo, theo từng giờ — tìm khung giờ nhiều nhất."""
    org_sql, org_params = _org_filter()
    clauses = [org_sql, "event_time >= %s", "event_time < %s"]
    params: list = list(org_params) + [date_from, date_to]

    if zone_code:
        clauses.append("zone_name_cached = %s")
        params.append(zone_code)

    sql = f"""
        SELECT date_trunc('hour', event_time) AS gio, count(*) AS so_luot
        FROM zone_event
        WHERE {" AND ".join(clauses)}
        GROUP BY 1
        ORDER BY so_luot DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_fence) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": ["gio", "so_luot"],
        "rows": [[str(v) for v in r] for r in rows],
        "row_count": len(rows),
    }


_FACE_GROUP_COLUMNS = {"direction": "direction", "department_name": "department_name"}


def count_face_events(
    date_from: str,
    date_to: str,
    direction: str | None = None,
    group_by: str = "direction",
) -> dict:
    """Đếm lượt nhận diện khuôn mặt theo khoảng thời gian, group theo 1+ cột
    trong {direction, department_name} (mặc định direction). Dùng access_time
    (KHÔNG phải event_time) — cột thời gian của smf_face_events."""
    group_cols = [c.strip() for c in group_by.split(",") if c.strip()]
    invalid = [c for c in group_cols if c not in _FACE_GROUP_COLUMNS]
    if invalid or not group_cols:
        return {"error": f"group_by chỉ nhận {sorted(_FACE_GROUP_COLUMNS)}, nhận '{group_by}'."}

    org_sql, org_params = _org_filter()
    clauses = [org_sql, "access_time >= %s", "access_time < %s"]
    params: list = list(org_params) + [date_from, date_to]

    if direction:
        d = direction.strip().upper()
        if d not in _DIRECTIONS:
            return {"error": f"direction phải là IN/OUT, nhận '{direction}'."}
        clauses.append("direction = %s")
        params.append(d)

    select_cols = ", ".join(group_cols)
    sql = f"""
        SELECT {select_cols}, count(*) AS so_luot
        FROM smf_face_events
        WHERE {" AND ".join(clauses)}
        GROUP BY {select_cols}
        ORDER BY so_luot DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_face) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": [*group_cols, "so_luot"],
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
    }


_FIRE_ENTITY_TYPES = {"FIRE", "SMOKE"}


def count_fire_smoke_events(date_from: str, date_to: str, entity_type: str | None = None) -> dict:
    """Đếm cảnh báo cháy/khói theo khoảng thời gian, group theo entity_type
    (FIRE/SMOKE) + alert_level (HIGH/MEDIUM/LOW).

    LƯU Ý DATA: firesmoke.fire_smoke_event hiện RỖNG HOÀN TOÀN (verify
    2026-09-17, xem specs/change-log.md) — row_count=0 là ĐÚNG dữ liệu
    thật cho MỌI khoảng thời gian, không phải lỗi tool/kết nối."""
    org_sql, org_params = _org_filter()
    clauses = [org_sql, "event_time >= %s", "event_time < %s"]
    params: list = list(org_params) + [date_from, date_to]

    if entity_type:
        e = entity_type.strip().upper()
        if e not in _FIRE_ENTITY_TYPES:
            return {"error": f"entity_type phải thuộc {sorted(_FIRE_ENTITY_TYPES)}, nhận '{entity_type}'."}
        clauses.append("entity_type = %s")
        params.append(e)

    sql = f"""
        SELECT entity_type, alert_level, count(*) AS so_luot
        FROM fire_smoke_event
        WHERE {" AND ".join(clauses)}
        GROUP BY entity_type, alert_level
        ORDER BY so_luot DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_fire) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": ["entity_type", "alert_level", "so_luot"],
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
    }


_ANOMALY_EVENT_TYPES = {"FIGHT_DETECTION", "CROWD_DETECTION", "INTRUSION_DETECTION", "WATER_LEVEL_DETECTION"}
_ANOMALY_GROUP_COLUMNS = {"severity": "severity", "zone_name": "zone_name"}


def count_anomaly_events(
    date_from: str,
    date_to: str,
    event_type: str,
    group_by: str | None = None,
) -> dict:
    """Đếm sự kiện trong anomaly.anomaly_event theo khoảng thời gian — DÙNG
    CHUNG cho 4 sự kiện: FIGHT_DETECTION (ẩu đả), CROWD_DETECTION (đám đông),
    INTRUSION_DETECTION (leo trèo — KHÁC zone_intrusion_by_hour/"vùng cấm":
    leo trèo dùng bảng anomaly_event, vùng cấm dùng bảng zone_event, đừng
    nhầm dù cả 2 đều có thể dịch là "xâm nhập"), WATER_LEVEL_DETECTION
    (mực nước).

    event_type BẮT BUỘC, chỉ nhận đúng 4 giá trị trên (validate whitelist —
    bảng còn có event_type khác như SIDEWALK_ENCROACHMENT/
    LITTERING_DETECTION nhưng KHÔNG thuộc 8 domain của sản phẩm này, xem
    specs/product-spec.md). Để so sánh nhiều event_type, gọi hàm này NHIỀU
    LẦN (mỗi lần 1 event_type) — giống cách count_vehicle_flow được gọi
    nhiều lần cho nhiều vehicle_type.

    group_by tuỳ chọn, group thêm theo 1+ cột trong {severity, zone_name} —
    để trống chỉ trả tổng số lượt."""
    if not event_type or event_type.strip().upper() not in _ANOMALY_EVENT_TYPES:
        return {"error": f"event_type phải thuộc {sorted(_ANOMALY_EVENT_TYPES)}, nhận '{event_type}'."}
    event_type = event_type.strip().upper()

    group_cols: list[str] = []
    if group_by:
        group_cols = [c.strip() for c in group_by.split(",") if c.strip()]
        invalid = [c for c in group_cols if c not in _ANOMALY_GROUP_COLUMNS]
        if invalid:
            return {"error": f"group_by chỉ nhận {sorted(_ANOMALY_GROUP_COLUMNS)}, nhận '{group_by}'."}

    org_sql, org_params = _org_filter()
    clauses = [org_sql, "event_time >= %s", "event_time < %s", "event_type = %s"]
    params: list = list(org_params) + [date_from, date_to, event_type]

    select_cols = ", ".join(group_cols) if group_cols else ""
    select_clause = f"{select_cols}, count(*) AS so_luot" if select_cols else "count(*) AS so_luot"
    group_sql = f"GROUP BY {select_cols}" if select_cols else ""

    sql = f"""
        SELECT {select_clause}
        FROM anomaly_event
        WHERE {" AND ".join(clauses)}
        {group_sql}
        ORDER BY so_luot DESC
        LIMIT {settings.db_max_rows};
    """
    with get_connection(settings.db_name_anomaly) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {
        "columns": [*group_cols, "so_luot"],
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
    }


def list_zones() -> dict:
    """Liệt kê camera/khu vực hợp lệ theo module AI — tránh agent đoán sai
    giá trị lọc. PLATE/ZONE giữ shape cũ; FACE/FIRE/ANOMALY lấy DISTINCT từ
    bảng sự kiện tương ứng (không có bảng camera master riêng).

    FACE dùng device_name/area_name (smf_face_events không có camera_code).
    ANOMALY kèm event_type để phân biệt ẩu đả/đám đông/leo trèo/mực nước."""
    org_sql, org_params = _org_filter()

    its_sql = f"""
        SELECT DISTINCT camera_code, camera_name
        FROM plate_event
        WHERE {org_sql}
        ORDER BY 1;
    """
    fence_sql = f"""
        SELECT DISTINCT zone_name_cached, camera_name
        FROM zone_event
        WHERE {org_sql}
        ORDER BY 1;
    """
    face_sql = f"""
        SELECT DISTINCT device_name, area_name
        FROM smf_face_events
        WHERE {org_sql}
        ORDER BY 1;
    """
    fire_sql = f"""
        SELECT DISTINCT camera_code, camera_name
        FROM fire_smoke_event
        WHERE {org_sql}
        ORDER BY 1;
    """
    anomaly_sql = f"""
        SELECT DISTINCT event_type, camera_code, camera_name, zone_name
        FROM anomaly_event
        WHERE {org_sql}
          AND event_type IN (
              'FIGHT_DETECTION', 'CROWD_DETECTION',
              'INTRUSION_DETECTION', 'WATER_LEVEL_DETECTION'
          )
        ORDER BY 1, 2;
    """

    with get_connection(settings.db_name_its) as conn, conn.cursor() as cur:
        cur.execute(its_sql, org_params)
        its_rows = cur.fetchall()
    with get_connection(settings.db_name_fence) as conn, conn.cursor() as cur:
        cur.execute(fence_sql, org_params)
        fence_rows = cur.fetchall()
    with get_connection(settings.db_name_face) as conn, conn.cursor() as cur:
        cur.execute(face_sql, org_params)
        face_rows = cur.fetchall()
    with get_connection(settings.db_name_fire) as conn, conn.cursor() as cur:
        cur.execute(fire_sql, org_params)
        fire_rows = cur.fetchall()
    with get_connection(settings.db_name_anomaly) as conn, conn.cursor() as cur:
        cur.execute(anomaly_sql, org_params)
        anomaly_rows = cur.fetchall()

    return {
        "camera_its": [list(r) for r in its_rows],
        "khu_vuc_hang_rao": [list(r) for r in fence_rows],
        "camera_face": [[str(v) if v is not None else "" for v in r] for r in face_rows],
        "camera_fire": [[str(v) if v is not None else "" for v in r] for r in fire_rows],
        "camera_anomaly": [
            [str(v) if v is not None else "" for v in r] for r in anomaly_rows
        ],
    }
