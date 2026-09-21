"""Tools Agent — function-calling tham số hoá: get_db_schema, list_khu_vuc
(PLATE/ZONE/FACE/FIRE/ANOMALY), count_vehicle_flow, trace_plate,
zone_intrusion_by_hour, count_face_events, count_fire_smoke_events,
count_anomaly_events + 1 tool SQL dự phòng.

Model CHỌN tool + điền tham số (ngày, loại xe, khu vực, biển số...) — KHÔNG
tự sinh SQL cho câu hỏi khớp tool. An toàn + chính xác hơn Text-to-SQL tự do
với model nhỏ (3-4B, 4GB VRAM): ít việc suy luận, không rủi ro sai cú pháp
Postgres/tên cột trên schema nhiều bảng. `run_sql_readonly` là fallback có
validate chặt cho câu hỏi lạ không khớp tool trên.

Chỉ dùng Postgres thật (không SQLite demo fallback như atin/) — `.env` của
project này luôn có sẵn DB thật, chế độ demo không nằm trong product-spec.
Nếu `DB_HOST` chưa cấu hình, mọi tool trả lỗi rõ ràng thay vì âm thầm dùng
dữ liệu giả.
"""

from __future__ import annotations

import re

from langchain_core.tools import tool
from pydantic import BaseModel

from src.config import settings
from src.db.connection import get_connection


class QueryResult(BaseModel):
    tool: str = ""
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    error: str = ""
    reply_vi: str = ""


def _not_configured(tool_name: str) -> str:
    return QueryResult(tool=tool_name, error="Chưa cấu hình DB thật (DB_HOST) trong .env.").model_dump_json()


_LIST_ZONES_KEYS = (
    "camera_its",
    "khu_vuc_hang_rao",
    "camera_face",
    "camera_fire",
    "camera_anomaly",
)


def _wrap_dict(tool_name: str, data: dict) -> str:
    """Chuẩn hoá dict trả về từ src/db/queries.py thành QueryResult JSON."""
    if "error" in data:
        return QueryResult(tool=tool_name, error=data["error"]).model_dump_json()
    if "camera_its" in data:  # list_zones — 1 hàng, mỗi cột 1 nhóm module
        columns = [k for k in _LIST_ZONES_KEYS if k in data]
        return QueryResult(
            tool=tool_name,
            columns=columns,
            rows=[[data.get(k, []) for k in columns]],
            row_count=1,
        ).model_dump_json()
    return QueryResult(
        tool=tool_name,
        columns=data.get("columns", []),
        rows=data.get("rows", []),
        row_count=data.get("row_count", 0),
    ).model_dump_json()


@tool
def get_db_schema() -> str:
    """Xem schema/mô tả nguồn dữ liệu hiện có trước khi hỏi câu phức tạp hoặc dùng run_sql_readonly."""
    return (
        "its.plate_event — mỗi dòng 1 lượt xe qua camera ITS: event_time, direction "
        "(IN/OUT), vehicle_type (BUS/CAR/MOTORCYCLE/TRUCK), manufacturer (hãng xe), "
        "license_plate_text/normalized_license_plate, camera_code/camera_name.\n"
        "virtual_fence.zone_event — mỗi dòng 1 lượt xâm nhập khu vực hàng rào ảo: "
        "event_time, zone_name_cached (tên khu vực), camera_code/camera_name, "
        "entity_type (PERSON/VEHICLE).\n"
        "Dùng các tool tham số hoá bên dưới cho câu hỏi thống kê thường gặp; chỉ dùng "
        "run_sql_readonly (SELECT trên plate_event/zone_event) cho câu hỏi không khớp."
    )


@tool
def list_khu_vuc() -> str:
    """Liệt kê camera/khu vực hợp lệ theo module AI — tránh đoán sai giá trị
    lọc trước khi gọi tool khác. Trả về các nhóm:
      - camera_its (PLATE / giám sát phương tiện)
      - khu_vuc_hang_rao (ZONE / vùng cấm)
      - camera_face (FACE / nhận diện khuôn mặt — device_name, area_name)
      - camera_fire (FIRE / cháy khói)
      - camera_anomaly (ANOMALY — kèm event_type: FIGHT_DETECTION /
        CROWD_DETECTION / INTRUSION_DETECTION / WATER_LEVEL_DETECTION)
    Danh sách rỗng ở 1 nhóm = chưa có sự kiện ghi nhận (không phải lỗi)."""
    if not settings.db_configured:
        return _not_configured("list_khu_vuc")
    from src.db.queries import list_zones

    return _wrap_dict("list_khu_vuc", list_zones())


@tool
def count_vehicle_flow(
    date_from: str,
    date_to: str,
    direction: str = "",
    vehicle_type: str = "",
    group_by: str = "vehicle_type,direction",
) -> str:
    """Đếm lượt xe ra/vào trong khoảng thời gian [date_from, date_to).
    CHỈ đặt vehicle_type khi câu hỏi hỏi ĐÚNG 1 loại xe cụ thể — nếu câu hỏi
    liệt kê/so sánh NHIỀU loại xe (vd. "phân loại theo xe máy, ô tô") hoặc hỏi
    tổng quát, để vehicle_type="" và dùng group_by="vehicle_type" (hoặc kèm
    direction) để lấy đủ TẤT CẢ loại xe trong 1 lần gọi.
    group_by: 1+ cột trong {vehicle_type, direction, manufacturer}, phân
    cách bằng dấu phẩy — dùng group_by="manufacturer" (kèm vehicle_type=CAR,
    vì hãng xe chỉ có ý nghĩa với ô tô) để thống kê theo hãng xe. DB KHÔNG
    phân loại xe theo số chỗ ngồi (5/7/9/16/29/40 chỗ) — chỉ có
    BUS/CAR/MOTORCYCLE/TRUCK, cần nêu rõ giới hạn này nếu câu hỏi đòi số chỗ.
    date_from/date_to định dạng 'YYYY-MM-DD HH:MM:SS'."""
    if not settings.db_configured:
        return _not_configured("count_vehicle_flow")
    from src.db.queries import count_vehicle_flow as query

    data = query(date_from, date_to, direction or None, vehicle_type or None, group_by)
    return _wrap_dict("count_vehicle_flow", data)


@tool
def trace_plate(plate_text: str, date_from: str = "", date_to: str = "") -> str:
    """Truy vết lịch sử di chuyển (camera, thời điểm, chiều ra/vào) của 1 biển số xe.
    date_from/date_to tuỳ chọn để giới hạn khoảng thời gian."""
    if not settings.db_configured:
        return _not_configured("trace_plate")
    from src.db.queries import trace_plate as query

    data = query(plate_text, date_from or None, date_to or None)
    return _wrap_dict("trace_plate", data)


@tool
def zone_intrusion_by_hour(date_from: str, date_to: str, zone_code: str = "") -> str:
    """Số lượt xâm nhập khu vực hàng rào ảo theo từng giờ trong khoảng thời gian —
    dùng để tìm khung giờ xảy ra xâm nhập nhiều nhất. zone_code tuỳ chọn (xem list_khu_vuc)."""
    if not settings.db_configured:
        return _not_configured("zone_intrusion_by_hour")
    from src.db.queries import zone_intrusion_by_hour as query

    data = query(date_from, date_to, zone_code or None)
    return _wrap_dict("zone_intrusion_by_hour", data)


@tool
def count_face_events(
    date_from: str,
    date_to: str,
    direction: str = "",
    group_by: str = "direction",
) -> str:
    """Đếm lượt nhận diện khuôn mặt trong khoảng thời gian [date_from, date_to).
    group_by: 1+ cột trong {direction, department_name}, phân cách bằng dấu
    phẩy (mặc định "direction"). direction tuỳ chọn, chỉ nhận IN/OUT.
    date_from/date_to định dạng 'YYYY-MM-DD HH:MM:SS'."""
    if not settings.db_configured:
        return _not_configured("count_face_events")
    from src.db.queries import count_face_events as query

    data = query(date_from, date_to, direction or None, group_by)
    return _wrap_dict("count_face_events", data)


@tool
def count_fire_smoke_events(date_from: str, date_to: str, entity_type: str = "") -> str:
    """CHỈ dùng cho câu hỏi về CHÁY hoặc KHÓI. Nếu câu hỏi nhắc "mực nước"
    (kể cả kèm chữ "cảnh báo"/"ngưỡng cảnh báo"), KHÔNG được dùng tool này —
    dùng count_anomaly_events(event_type="WATER_LEVEL_DETECTION") thay
    thế, vì mực nước và cháy/khói là 2 nguồn dữ liệu HOÀN TOÀN KHÁC NHAU.

    Đếm cảnh báo cháy/khói trong khoảng thời gian [date_from, date_to).
    entity_type tuỳ chọn, chỉ nhận FIRE (cháy) hoặc SMOKE (khói) — để trống
    để lấy cả 2. date_from/date_to định dạng 'YYYY-MM-DD HH:MM:SS'.
    LƯU Ý: nguồn dữ liệu này hiện CHƯA có bất kỳ cảnh báo nào được ghi nhận
    (row_count=0 là dữ liệu THẬT, không phải lỗi tool/kết nối) — nếu kết quả
    rỗng, trả lời đúng là "không có dữ liệu", KHÔNG được bịa ra 1 cảnh báo."""
    if not settings.db_configured:
        return _not_configured("count_fire_smoke_events")
    from src.db.queries import count_fire_smoke_events as query

    data = query(date_from, date_to, entity_type or None)
    return _wrap_dict("count_fire_smoke_events", data)


@tool
def count_anomaly_events(
    date_from: str,
    date_to: str,
    event_type: str,
    group_by: str = "",
) -> str:
    """Đếm sự kiện bất thường trong khoảng thời gian [date_from, date_to) —
    DÙNG CHUNG cho 4 loại sự kiện, event_type BẮT BUỘC và CHỈ được nhận
    ĐÚNG 1 trong 4 giá trị sau (không được tự bịa giá trị khác):
      - "FIGHT_DETECTION"      — ẩu đả
      - "CROWD_DETECTION"      — đám đông
      - "INTRUSION_DETECTION"  — leo trèo (KHÁC "vùng cấm"/xâm nhập hàng
        rào ảo — câu hỏi về vùng cấm/hàng rào ảo phải dùng
        zone_intrusion_by_hour, KHÔNG dùng tool này)
      - "WATER_LEVEL_DETECTION" — mực nước vượt ngưỡng cảnh báo (KHÔNG
        dùng count_fire_smoke_events cho câu hỏi mực nước dù cũng có chữ
        "cảnh báo" — 2 tool khác nguồn dữ liệu hoàn toàn)
    Để so sánh nhiều loại sự kiện, gọi tool này NHIỀU LẦN (mỗi lần 1
    event_type) rồi tự tổng hợp — KHÔNG được gộp nhiều event_type vào 1
    lần gọi. group_by tuỳ chọn, 1+ cột trong {severity, zone_name}, để
    trống chỉ lấy tổng số lượt. date_from/date_to định dạng
    'YYYY-MM-DD HH:MM:SS'."""
    if not settings.db_configured:
        return _not_configured("count_anomaly_events")
    from src.db.queries import count_anomaly_events as query

    data = query(date_from, date_to, event_type, group_by or None)
    return _wrap_dict("count_anomaly_events", data)


_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|truncate)\b",
    re.IGNORECASE,
)
_ALLOWED_TABLES = {"plate_event", "zone_event"}
# Khớp tên bảng THẬT SỰ sau FROM/JOIN — không dùng substring-match toàn câu
# (substring lọt qua nếu tên bảng chỉ xuất hiện trong string literal/comment,
# trong khi FROM thực sự trỏ tới bảng khác ngoài whitelist, vd. plate_blacklist
# — đã phát hiện lỗ hổng này khi review, xem change-log).
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


@tool
def run_sql_readonly(sql: str) -> str:
    """Fallback: chạy 1 câu SQL SELECT read-only trên plate_event/zone_event khi
    câu hỏi KHÔNG khớp các tool trên. Chỉ dùng khi thực sự cần — ưu tiên tool có sẵn."""
    if not settings.db_configured:
        return _not_configured("run_sql_readonly")

    text = (sql or "").strip().rstrip(";")
    if not text:
        return QueryResult(tool="run_sql_readonly", error="SQL rỗng.").model_dump_json()
    low = text.lower()
    if not low.startswith("select"):
        return QueryResult(tool="run_sql_readonly", error="Chỉ cho phép câu SELECT (đọc-only).").model_dump_json()
    if _WRITE_KEYWORDS.search(text):
        return QueryResult(tool="run_sql_readonly", error="SQL chứa từ khoá ghi/DDL — bị chặn.").model_dump_json()

    referenced_tables = {m.lower() for m in _TABLE_REF.findall(text)}
    if not referenced_tables or not referenced_tables.issubset(_ALLOWED_TABLES):
        return QueryResult(
            tool="run_sql_readonly",
            error=f"Chỉ cho phép SELECT trên bảng {sorted(_ALLOWED_TABLES)}.",
        ).model_dump_json()
    if "limit" not in low:
        text = f"{text} LIMIT {settings.db_max_rows}"

    dbname = settings.db_name_fence if "zone_event" in referenced_tables else settings.db_name_its
    try:
        with get_connection(dbname) as conn, conn.cursor() as cur:
            cur.execute(text)
            columns = [d.name for d in (cur.description or [])]
            rows = [[str(v) for v in r] for r in cur.fetchall()]
        return QueryResult(tool="run_sql_readonly", columns=columns, rows=rows, row_count=len(rows)).model_dump_json()
    except Exception as exc:  # psycopg2 errors: lỗi cú pháp/timeout/permission
        return QueryResult(tool="run_sql_readonly", error=f"Lỗi SQL: {exc}").model_dump_json()


TOOLS = [
    get_db_schema,
    list_khu_vuc,
    count_vehicle_flow,
    trace_plate,
    zone_intrusion_by_hour,
    count_face_events,
    count_fire_smoke_events,
    count_anomaly_events,
    run_sql_readonly,
]
