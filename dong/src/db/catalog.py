"""Schema catalog cho VMS KCN Hưng Phú — load từ resource/db/catalog.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
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


_TABLE_ALIASES: dict[str, str] = {
    "zone_events": "zone_event",
    "plate_events": "plate_event",
    "smf_face_event": "smf_face_events",
    "fire_smoke_events": "fire_smoke_event",
    "firesmoke_event": "fire_smoke_event",
    "anomaly_events": "anomaly_event",
    "water_events": "water_event",
}


_TABLE_REF = re.compile(
    r'\b(?:from|join)\s+(?:only\s+)?(?:(?:"?[a-zA-Z_][\w]*"?)\.)?"?([a-zA-Z_][\w]*)"?',
    re.IGNORECASE,
)


def get_database_for_table(table: str) -> str:
    """Xác định tên database kết nối tương ứng với bảng."""
    tbl = table.lower().strip().strip('"')
    tbl = _TABLE_ALIASES.get(tbl, tbl)
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


def get_database_for_sql(sql: str) -> str:
    """Xác định database kết nối bằng cách tìm bảng catalog có trong câu SQL."""
    catalog = _load_catalog()
    for m in _TABLE_REF.finditer(sql or ""):
        cand = m.group(1).lower().strip('"')
        cand = _TABLE_ALIASES.get(cand, cand)
        if cand in catalog:
            return get_database_for_table(cand)
    m = _TABLE_REF.search(sql or "")
    tbl_name = m.group(1).lower() if m else ""
    return get_database_for_table(tbl_name)


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


# Safe default table when question does not match any domain rule or token score.
# In VMS KCN Hưng Phú, plate_event (lượt xe ra/vào / ALPR) is the primary and most frequent dataset.
_DEFAULT_TABLE = "plate_event"

_STOP_WORDS = {
    "a", "an", "bao", "biết", "các", "cho", "có", "của", "cứu", "danh",
    "đang", "đó", "được", "gì", "hãy", "hôm", "kê", "là", "một", "nào",
    "nay", "này", "năm", "ngày", "những", "nhiêu", "ở", "qua", "ra", "sách",
    "tại", "tháng", "the", "thống", "tôi", "tra", "trong", "và", "vào", "với", "xem",
}

# Domain heuristics: map regex pattern to catalog table key.
# Ordered by domain specificity to avoid false positives (e.g. vehicle before generic terms).
_DOMAIN_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"ô\s*tô|o\s*to|xe\s*máy|xe\s*may|xe\s*đạp|xe\s*dap|xe\s*tải|xe\s*tai|"
            r"xe\s*buýt|xe\s*buyt|xe\s*bus|xe\s*hơi|xe\s*hoi|xe\s*con|"
            r"biển\s*số|bien\s*so|biển\s*kiểm\s*soát|bien\s*kiem\s*soat|"
            r"phương\s*tiện|phuong\s*tien|lượt\s*xe|luot\s*xe|\bxe\b|alpr|license\s*plate|"
            r"\bcar\b|\bcars\b|\bmotorcycle\b|\bmotorcycles\b|\btruck\b|\bbus\b|\bvehicle\b|\bvehicles\b|"
            r"camera\s+(?:phương\s*tiện|phuong\s*tien|biển\s*số|bien\s*so|xe)\b|plate_events?|its\.plate",
            re.IGNORECASE,
        ),
        "plate_event",
    ),
    (
        re.compile(
            r"cháy|chay|khói|khoi|hỏa\s*hoạn|hoa\s*hoan|báo\s*cháy|bao\s*chay|báo\s*khói|bao\s*khoi|"
            r"\bfire\b|\bsmoke\b|firesmoke|fire_smoke(?:_event)?",
            re.IGNORECASE,
        ),
        "fire_smoke_event",
    ),
    (
        re.compile(
            r"khuôn\s*mặt|khuon\s*mat|gương\s*mặt|guong\s*mat|nhận\s*diện\s*mặt|nhan\s*dien\s*mat|"
            r"quét\s*mặt|quet\s*mat|\bmặt\b|"
            r"chấm\s*công|cham\s*cong|nhân\s*viên|nhan\s*vien|công\s*nhân|cong\s*nhan|"
            r"smart\s*face|\bface\b|\bfaces\b|smf(?:_face_events)?",
            re.IGNORECASE,
        ),
        "smf_face_events",
    ),
    (
        re.compile(
            r"xâm\s*nhập|xam\s*nhap|hàng\s*rào\s*ảo|hang\s*rao\s*ao|hàng\s*rào|hang\s*rao|"
            r"vùng\s*cấm|vung\s*cam|khu\s*vực\s*bảo\s*vệ|khu\s*vuc\s*bao\s*ve|vượt\s*rào|vuot\s*rao|"
            r"virtual\s*fence|\bzone\b|\bzones\b|zone_events?",
            re.IGNORECASE,
        ),
        "zone_event",
    ),
    (
        re.compile(
            r"bất\s*thường|bat\s*thuong|ẩu\s*đả|au\s*da|đánh\s*nhau|danh\s*nhau|"
            r"đám\s*đông|dam\s*dong|tụ\s*tập|tu\s*tap|leo\s*trèo|leo\s*treo|trèo\s*rào|treo\s*rao|"
            r"mực\s*nước|muc\s*nuoc|ngập\s*nước|ngap\s*nuoc|\bngập\b|\bngap\b|"
            r"lảng\s*vảng|lang\s*vang|loitering|\banomaly\b|anomaly_events?|"
            r"fight_detection|crowd_detection|water_level",
            re.IGNORECASE,
        ),
        "anomaly_event",
    ),
]


def _extract_query_tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    raw = re.findall(r"[\w]+", lowered, flags=re.UNICODE)
    return [t for t in raw if len(t) >= 2 and t not in _STOP_WORDS]


def _score_table(tbl: str, info: dict[str, Any], query_text: str, tokens: list[str]) -> int:
    score = 0
    q_lower = query_text.lower()

    if tbl in q_lower:
        score += 15
    table_id = str(info.get("id", "")).lower()
    if table_id and table_id in q_lower:
        score += 15

    desc = str(info.get("description", "")).lower()
    for token in tokens:
        if token in desc:
            score += 2

    cols = info.get("columns", {})
    if isinstance(cols, dict):
        for col_name, meta in cols.items():
            col_lower = col_name.lower()
            if col_lower in q_lower:
                score += 10
            elif any(t == col_lower for t in tokens):
                score += 8

            if isinstance(meta, dict):
                col_desc = str(meta.get("description", "")).lower()
                for token in tokens:
                    if token in col_desc:
                        score += 1
                for sample in meta.get("sample_values") or []:
                    sample_str = str(sample).lower()
                    if sample_str and (sample_str in q_lower or sample_str in tokens):
                        score += 6
    return score


def select_relevant_tables(question: str, limit: int = 4) -> list[str]:
    """Chọn tối đa `limit` tên bảng từ catalog phù hợp nhất với câu hỏi (học duy).

    Thứ tự ưu tiên:
    1. Heuristics theo domain:
       - vehicle/biển số/ALPR/lượt xe -> plate_event
       - cháy/khói -> fire_smoke_event
       - mặt/chấm công -> smf_face_events
       - xâm nhập/hàng rào/zone -> zone_event
       - bất thường/anomaly -> anomaly_event
    2. Fallback scoring: so khớp tokens của câu hỏi với table id, description, column names,
       column descriptions và sample_values; xếp hạng và chọn top <= limit.
    3. Safe default set: nếu không khớp bảng nào, trả về `['plate_event']` (bảng nghiệp vụ
       chính và phổ biến nhất của VMS KCN Hưng Phú).

    Đảm bảo không bao giờ trả về bảng ngoài catalog và len(result) <= limit.
    """
    if limit <= 0:
        return []

    catalog = _load_catalog()
    allowed = set(catalog.keys())
    q = (question or "").strip()

    if re.search(
        r"tất\s*c(?:ả|à)\s*(?:các\s*)?(?:event|events|sự\s*kiện|su\s*kien)|"
        r"(?:toàn\s*bộ|mọi)\s*(?:các\s*)?(?:event|events|sự\s*kiện|su\s*kien)",
        q,
        re.IGNORECASE,
    ):
        all_event_tables = [
            "plate_event",
            "zone_event",
            "smf_face_events",
            "fire_smoke_event",
            "anomaly_event",
        ]
        picked_all = [t for t in all_event_tables if t in allowed]
        if picked_all:
            return picked_all

    # 1. Domain heuristics
    matched_domains: list[str] = []
    for pattern, tbl in _DOMAIN_RULES:
        if tbl in allowed and pattern.search(q):
            if tbl not in matched_domains:
                matched_domains.append(tbl)

    if matched_domains:
        return matched_domains[:limit]

    # 2. Fallback token-based scoring
    tokens = _extract_query_tokens(q)
    scored: list[tuple[int, str]] = []
    for tbl, info in catalog.items():
        s = _score_table(tbl, info, q, tokens)
        if s > 0:
            scored.append((s, tbl))

    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [tbl for _, tbl in scored[:limit]]
    if picked:
        return picked

    # 3. Safe default fallback
    default_tbl = _DEFAULT_TABLE if _DEFAULT_TABLE in allowed else (next(iter(allowed)) if allowed else "")
    return [default_tbl][:limit] if default_tbl else []
