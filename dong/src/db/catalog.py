"""Schema catalog cho VMS KCN Hưng Phú (dong v5).

Chứa thông tin cấu trúc các bảng VMS trong 5 Postgres database (its, virtual_fence,
smart_face, firesmoke, anomaly) để phục vụ tạo QueryPlan và validate SQL.
Hoàn toàn offline-friendly với catalog tĩnh; có thể mô tả động nếu DB sẵn sàng.
"""

from __future__ import annotations

from typing import Any

from src.config import settings

CATALOG: dict[str, dict[str, Any]] = {
    "plate_event": {
        "id": "its.plate_events",
        "database": "its",
        "table": "plate_event",
        "description": "Lượt xe ra/vào KCN, nhận diện biển số (ALPR), loại xe, hướng di chuyển.",
        "time_column": "event_time",
        "columns": {
            "event_time": {"type": "timestamp", "description": "Thời điểm xe qua camera"},
            "camera_code": {"type": "varchar", "description": "Mã camera"},
            "camera_name": {"type": "varchar", "description": "Tên camera vị trí cổng"},
            "direction": {
                "type": "varchar",
                "description": "Hướng di chuyển (IN: vào, OUT: ra)",
                "sample_values": ["IN", "OUT"],
            },
            "vehicle_type": {
                "type": "varchar",
                "description": "Loại phương tiện (chỉ 4 loại, không có xe 4/7 chỗ)",
                "sample_values": ["BUS", "CAR", "MOTORCYCLE", "TRUCK"],
            },
            "manufacturer": {"type": "varchar", "description": "Hãng xe ô tô (Toyota, Honda, ...)"},
            "license_plate": {"type": "varchar", "description": "Biển số xe đầy đủ"},
            "normalized_license_plate": {"type": "varchar", "description": "Biển số xe viết liền viết hoa"},
            "organization_id": {"type": "int", "description": "Mã tổ chức / KCN"},
        },
    },
    "zone_event": {
        "id": "virtual_fence.zone_events",
        "database": "virtual_fence",
        "table": "zone_event",
        "description": "Sự kiện xâm nhập khu vực hàng rào ảo / vùng cấm bảo vệ.",
        "time_column": "event_time",
        "columns": {
            "event_time": {"type": "timestamp", "description": "Thời điểm phát hiện xâm nhập"},
            "zone_name_cached": {"type": "varchar", "description": "Tên khu vực / hàng rào ảo cảnh báo"},
            "camera_name": {"type": "varchar", "description": "Tên camera quan sát"},
            "organization_id": {"type": "int", "description": "Mã tổ chức / KCN"},
        },
    },
    "smf_face_events": {
        "id": "smart_face.events",
        "database": "smart_face",
        "table": "smf_face_events",
        "description": "Lượt nhận diện khuôn mặt chấm công / nhân viên ra vào cổng.",
        "time_column": "access_time",
        "columns": {
            "access_time": {"type": "timestamp", "description": "Thời điểm nhận diện khuôn mặt (không dùng event_time)"},
            "direction": {
                "type": "varchar",
                "description": "Hướng ra/vào (IN: vào, OUT: ra)",
                "sample_values": ["IN", "OUT"],
            },
            "department_name": {"type": "varchar", "description": "Tên phòng ban"},
            "device_name": {"type": "varchar", "description": "Tên thiết bị nhận diện"},
            "area_name": {"type": "varchar", "description": "Khu vực quét mặt"},
            "user_name": {"type": "varchar", "description": "Tên nhân viên"},
            "organization_id": {"type": "int", "description": "Mã tổ chức / KCN"},
        },
    },
    "fire_smoke_event": {
        "id": "firesmoke.events",
        "database": "firesmoke",
        "table": "fire_smoke_event",
        "description": "Sự kiện cảnh báo phát hiện cháy và khói.",
        "time_column": "event_time",
        "columns": {
            "event_time": {"type": "timestamp", "description": "Thời điểm phát hiện cháy/khói"},
            "entity_type": {
                "type": "varchar",
                "description": "Loại sự kiện (FIRE: cháy, SMOKE: khói)",
                "sample_values": ["FIRE", "SMOKE"],
            },
            "alert_level": {
                "type": "varchar",
                "description": "Mức độ cảnh báo (HIGH, MEDIUM, LOW)",
                "sample_values": ["HIGH", "MEDIUM", "LOW"],
            },
            "camera_code": {"type": "varchar", "description": "Mã camera"},
            "camera_name": {"type": "varchar", "description": "Tên camera"},
            "organization_id": {"type": "int", "description": "Mã tổ chức / KCN"},
        },
    },
    "anomaly_event": {
        "id": "anomaly.events",
        "database": "anomaly",
        "table": "anomaly_event",
        "description": "Sự kiện bất thường AI: ẩu đả, đám đông, leo trèo hàng rào, mực nước ngập.",
        "time_column": "event_time",
        "columns": {
            "event_time": {"type": "timestamp", "description": "Thời điểm xảy ra sự kiện"},
            "event_type": {
                "type": "varchar",
                "description": "Loại sự kiện bất thường",
                "sample_values": ["FIGHT_DETECTION", "CROWD_DETECTION", "INTRUSION_DETECTION", "WATER_LEVEL_DETECTION"],
            },
            "severity": {
                "type": "varchar",
                "description": "Mức độ nghiêm trọng (HIGH, MEDIUM, LOW)",
                "sample_values": ["HIGH", "MEDIUM", "LOW"],
            },
            "zone_name": {"type": "varchar", "description": "Tên khu vực"},
            "camera_code": {"type": "varchar", "description": "Mã camera"},
            "camera_name": {"type": "varchar", "description": "Tên camera"},
            "organization_id": {"type": "int", "description": "Mã tổ chức / KCN"},
        },
    },
}


def get_catalog() -> dict[str, dict[str, Any]]:
    """Trả về catalog toàn bộ bảng VMS."""
    return CATALOG


def get_allowed_tables() -> set[str]:
    """Tập tên bảng hợp lệ trong danh mục."""
    return set(CATALOG.keys())


def get_allowed_columns(table: str) -> set[str]:
    """Tập tên cột hợp lệ cho bảng được chỉ định."""
    tbl = table.lower().strip()
    if tbl in CATALOG:
        return set(CATALOG[tbl]["columns"].keys())
    return set()


def get_database_for_table(table: str) -> str:
    """Xác định tên database kết nối tương ứng với bảng."""
    tbl = table.lower().strip()
    entry = CATALOG.get(tbl)
    if entry:
        db_key = entry["database"]
        if db_key == "its":
            return settings.db_name_its
        if db_key == "virtual_fence":
            return settings.db_name_fence
        if db_key == "smart_face":
            return settings.db_name_face
        if db_key == "firesmoke":
            return settings.db_name_fire
        if db_key == "anomaly":
            return settings.db_name_anomaly
        return db_key
    return settings.db_name_its


def describe_table(table: str, dbname: str | None = None) -> dict[str, Any]:
    """Mô tả chi tiết cấu trúc bảng (cột, kiểu dữ liệu, mô tả, giá trị mẫu)."""
    tbl = table.lower().strip()
    if tbl in CATALOG:
        info = CATALOG[tbl]
        db = dbname or get_database_for_table(tbl)
        return {
            "database": db,
            "table": tbl,
            "description": info["description"],
            "time_column": info["time_column"],
            "columns": [
                {
                    "column_name": col_name,
                    "data_type": meta["type"],
                    "description": meta["description"],
                    "sample_values": meta.get("sample_values", []),
                }
                for col_name, meta in info["columns"].items()
            ],
        }

    # Nếu DB đã cấu hình và bảng không nằm trong catalog tĩnh, có thể introspect động
    if settings.db_configured and dbname:
        try:
            from src.db.connection import get_connection

            with get_connection(dbname) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (tbl,),
                )
                cols = cur.fetchall()
                if cols:
                    return {
                        "database": dbname,
                        "table": tbl,
                        "description": "Bảng được mô tả động qua information_schema",
                        "time_column": None,
                        "columns": [{"column_name": r[0], "data_type": r[1]} for r in cols],
                    }
        except Exception:
            pass

    raise ValueError(f"Bảng '{table}' không tồn tại trong catalog danh mục.")


def build_schema_excerpt(tables: list[str] | None = None) -> str:
    """Tạo chuỗi schema excerpt rút gọn làm context cho prompt LLM sinh QueryPlan."""
    targets = [t.lower().strip() for t in tables] if tables else list(CATALOG.keys())
    sections: list[str] = []

    for tbl in targets:
        info = CATALOG.get(tbl)
        if not info:
            continue
        db_name = get_database_for_table(tbl)
        lines = [
            f"Table: {tbl} (Database: {db_name})",
            f"Mô tả: {info['description']}",
            f"Cột thời gian: {info['time_column']}",
            "Cột:",
        ]
        for col, meta in info["columns"].items():
            samples = ""
            if "sample_values" in meta and meta["sample_values"]:
                samples = f" [giá trị mẫu: {', '.join(meta['sample_values'])}]"
            lines.append(f"  - {col} ({meta['type']}): {meta['description']}{samples}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections).strip()
