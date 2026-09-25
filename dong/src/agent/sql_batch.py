"""Batch SQL — gom sub-question cùng query_data, sinh & execute nhiều câu SQL."""

from __future__ import annotations

import re
from typing import Any

from src.agent.generate_sql import extract_sql
from src.agent.pre_sql import get_time_column_for_table, time_range_to_filter
from src.agent.sql_scope import apply_organization_scope
from src.db.executor import execute_sql as db_execute
from src.db.validator import validate_sql

_SQL_FENCE_ALL = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_DATE_RANGE_RE = re.compile(
    r"từ\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*đến\s*(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)


def extract_sqls(text: str) -> list[str]:
    """Trích một hoặc nhiều khối SQL từ output LLM."""
    blocks = [b.strip().rstrip(";") for b in _SQL_FENCE_ALL.findall(text or "") if b.strip()]
    if blocks:
        return blocks
    one = extract_sql(text or "")
    return [one] if one else []


def _date_range_filter(q_lower: str, time_col: str) -> str | None:
    m = _DATE_RANGE_RE.search(q_lower)
    if not m:
        return None
    d1, mo1, y1, d2, mo2, y2 = (int(m.group(i)) for i in range(1, 7))
    start = f"{y1}-{mo1:02d}-{d1:02d}"
    end = f"{y2}-{mo2:02d}-{d2:02d}"
    return f"{time_col}::date BETWEEN DATE '{start}' AND DATE '{end}'"


def _date_filter_for_question(q_lower: str, table: str) -> str:
    time_col = get_time_column_for_table(table)
    ranged = _date_range_filter(q_lower, time_col)
    if ranged:
        return ranged
    if any(kw in q_lower for kw in ("hôm nay", "hom nay", "today", "ngày hôm nay")):
        return time_range_to_filter("today", time_col) or "TRUE"
    if any(kw in q_lower for kw in ("hôm qua", "hom qua", "yesterday")):
        return time_range_to_filter("yesterday", time_col) or "TRUE"
    if any(kw in q_lower for kw in ("tháng này", "thang nay", "this month")):
        return time_range_to_filter("this_month", time_col) or "TRUE"
    return "TRUE"


def _resolve_offline_table(sub_question: str) -> tuple[str, str]:
    """Trả (table, điều kiện bổ sung) từ sub-question."""
    q_lower = (sub_question or "").lower()
    if any(kw in q_lower for kw in ("vùng cấm", "vung cam", "xâm nhập", "xam nhap", "hàng rào", "hang rao")):
        return "zone_event", ""
    if any(kw in q_lower for kw in ("đám đông", "dam dong", "crowd")):
        return "anomaly_event", "event_type = 'CROWD_DETECTION'"
    if any(kw in q_lower for kw in ("ẩu đả", "au da", "fight")):
        return "anomaly_event", "event_type = 'FIGHT_DETECTION'"
    if any(kw in q_lower for kw in ("cháy", "chay", "khói", "khoi", "fire", "smoke")):
        return "fire_smoke_event", ""
    if any(kw in q_lower for kw in ("khuôn mặt", "khuon mat", "face")):
        return "smf_face_events", ""
    if any(kw in q_lower for kw in ("bất thường", "bat thuong", "anomaly")):
        return "anomaly_event", ""
    if any(kw in q_lower for kw in ("phương tiện", "phuong tien", "lượt xe", "luot xe", "biển số", "bien so", "xe")):
        return "plate_event", ""
    return "plate_event", ""


def offline_sql_for_sub_question(sub_question: str) -> str:
    """Sinh SQL offline theo từ khóa sub-question."""
    q_lower = (sub_question or "").lower()
    table, extra = _resolve_offline_table(sub_question)
    clauses = [c for c in (_date_filter_for_question(q_lower, table), extra) if c and c != "TRUE"]
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f"SELECT COUNT(*) AS count FROM {table} WHERE {where}"
    return apply_organization_scope(sql)


def query_text_for_state(state: dict[str, Any]) -> str:
    """Câu hỏi đưa vào schema/SQL — ưu tiên batch sub-question khi multi-hop."""
    batch = state.get("orchestrator_batch_sub_questions") or []
    if batch:
        return "\n".join(f"{i + 1}. {q}" for i, q in enumerate(batch))
    if state.get("orchestrator_multi_active"):
        return (state.get("question") or "").strip()
    question = state.get("question", "")
    rewritten = state.get("rewritten")
    if rewritten is not None:
        if hasattr(rewritten, "text"):
            return rewritten.text or question
        if isinstance(rewritten, dict):
            return rewritten.get("text") or question
    return question


def build_sql_batch(sub_questions: list[str], raw_llm: str = "") -> list[dict[str, str]]:
    """Ghép sub-question với SQL (offline hoặc từ LLM)."""
    if raw_llm:
        sqls = extract_sqls(raw_llm)
    else:
        sqls = []
    out: list[dict[str, str]] = []
    for i, sq in enumerate(sub_questions):
        sql = sqls[i] if i < len(sqls) else offline_sql_for_sub_question(sq)
        out.append({"sub_question": sq, "sql": apply_organization_scope(sql)})
    return out


def validate_sql_batch(sql_batch: list[dict[str, str]]) -> dict[str, Any]:
    items = []
    ok = True
    for item in sql_batch:
        val = validate_sql(item.get("sql") or "")
        d = val.to_dict()
        d["sub_question"] = item.get("sub_question", "")
        items.append(d)
        if not val.ok:
            ok = False
    return {"ok": ok, "batch": items, "reason": "" if ok else "batch_validation_failed"}


def execute_sql_batch(sql_batch: list[dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in sql_batch:
        sq = item.get("sub_question", "")
        sql = apply_organization_scope((item.get("sql") or "").strip())
        entry: dict[str, Any] = {
            "sub_question": sq,
            "sql": sql,
            "rows": [],
            "columns": [],
            "error": "",
        }
        val = validate_sql(sql)
        if not val.ok:
            entry["error"] = val.reason
            results.append(entry)
            continue
        try:
            rows, columns = db_execute(sql)
            entry["rows"] = rows
            entry["columns"] = list(columns) if columns else (list(rows[0].keys()) if rows else [])
        except Exception as exc:
            entry["error"] = str(exc)
        results.append(entry)
    return results
