"""Schema catalog cho VMS KCN Hưng Phú — load từ resource/db/catalog.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config import settings

_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "resource" / "db" / "catalog.yaml"


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, Any]]:
    if not _CATALOG_PATH.exists():
        raise FileNotFoundError(f"Catalog not found: {_CATALOG_PATH}")
    data = yaml.safe_load(_CATALOG_PATH.read_text("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid catalog YAML: {_CATALOG_PATH}")
    return data


CATALOG: dict[str, dict[str, Any]] = _load_catalog()


def get_catalog() -> dict[str, dict[str, Any]]:
    """Trả về catalog toàn bộ bảng VMS."""
    return _load_catalog()


def get_allowed_tables() -> set[str]:
    """Tập tên bảng hợp lệ trong danh mục."""
    return set(_load_catalog().keys())


def get_allowed_columns(table: str) -> set[str]:
    """Tập tên cột hợp lệ cho bảng được chỉ định."""
    tbl = table.lower().strip()
    catalog = _load_catalog()
    if tbl in catalog:
        return set(catalog[tbl]["columns"].keys())
    return set()


def get_database_for_table(table: str) -> str:
    """Xác định tên database kết nối tương ứng với bảng."""
    tbl = table.lower().strip()
    entry = _load_catalog().get(tbl)
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
    catalog = _load_catalog()
    if tbl in catalog:
        info = catalog[tbl]
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
    catalog = _load_catalog()
    targets = [t.lower().strip() for t in tables] if tables else list(catalog.keys())
    sections: list[str] = []

    for tbl in targets:
        info = catalog.get(tbl)
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
