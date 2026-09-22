"""QueryPlan generation, repair hook, and execution pipeline (dong v5).

Phục vụ sinh QueryPlan từ câu hỏi + schema excerpt, tự động sửa lỗi (repair loop)
nếu validate hoặc execute thất bại tối đa SQL_REPAIR_MAX lần.
"""

from __future__ import annotations

from typing import Any

from src.config import settings
from src.db.catalog import build_schema_excerpt
from src.db.executor import execute_sql
from src.db.query_builder import build_sql
from src.db.validator import validate_sql
from src.llm.client import use_offline_tools
from src.llm.schemas import QueryPlan, RewrittenQuestion
from src.llm.structured import invoke_structured
from src.prompts import registry


def _offline_plan_query(question: str | RewrittenQuestion) -> QueryPlan:
    """Heuristic offline sinh QueryPlan hợp lệ mà không cần gọi LLM LAN."""
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    low = text.lower().strip()

    filters: list[str] = []
    if isinstance(question, RewrittenQuestion) and question.filters:
        filters = list(question.filters)
    else:
        if "vào" in low or "in" in low.split():
            filters.append("direction = 'IN'")
        elif "ra" in low or "out" in low.split():
            filters.append("direction = 'OUT'")

        if "xe tải" in low or "truck" in low:
            filters.append("vehicle_type = 'TRUCK'")
        elif "xe máy" in low or "motorcycle" in low:
            filters.append("vehicle_type = 'MOTORCYCLE'")
        elif "xe buýt" in low or "bus" in low:
            filters.append("vehicle_type = 'BUS'")
        elif "ô tô" in low or "xe con" in low or "car" in low:
            filters.append("vehicle_type = 'CAR'")

    if any(k in low for k in ("xâm nhập", "hàng rào", "vùng cấm", "zone")):
        return QueryPlan(
            tables=["zone_event"],
            selects=["count(*) AS so_luot"],
            filters=filters,
            limit=100,
        )
    if any(k in low for k in ("khuôn mặt", "chấm công", "nhân viên", "face")):
        return QueryPlan(
            tables=["smf_face_events"],
            selects=["direction", "count(*) AS so_luot"],
            filters=filters,
            group_by=["direction"],
            order_by="so_luot DESC",
            limit=100,
        )
    if any(k in low for k in ("cháy", "khói", "fire", "smoke")):
        return QueryPlan(
            tables=["fire_smoke_event"],
            selects=["entity_type", "count(*) AS so_luot"],
            filters=filters,
            group_by=["entity_type"],
            order_by="so_luot DESC",
            limit=100,
        )
    if any(k in low for k in ("ẩu đả", "đám đông", "leo trèo", "mực nước", "ngập", "bất thường", "anomaly")):
        if not any("event_type" in f for f in filters):
            if any(k in low for k in ("đám đông", "crowd")):
                filters.append("event_type = 'CROWD_DETECTION'")
            elif any(k in low for k in ("leo trèo", "intrusion")):
                filters.append("event_type = 'INTRUSION_DETECTION'")
            elif any(k in low for k in ("mực nước", "water", "ngập")):
                filters.append("event_type = 'WATER_LEVEL_DETECTION'")
            elif any(k in low for k in ("ẩu đả", "fight")):
                filters.append("event_type = 'FIGHT_DETECTION'")

        has_event_type = any("event_type" in f for f in filters)
        selects = ["count(*) AS so_luot"] if has_event_type else ["event_type", "count(*) AS so_luot"]
        group_by = [] if has_event_type else ["event_type"]
        order_by = "so_luot DESC" if group_by else None
        return QueryPlan(
            tables=["anomaly_event"],
            selects=selects,
            filters=filters,
            group_by=group_by,
            order_by=order_by,
            limit=100,
        )

    # Mặc định: plate_event
    selects = ["count(*) AS so_luot"] if filters else ["vehicle_type", "count(*) AS so_luot"]
    group_by = [] if filters else ["vehicle_type"]
    order_by = "so_luot DESC" if group_by else None
    return QueryPlan(
        tables=["plate_event"],
        selects=selects,
        filters=filters,
        group_by=group_by,
        order_by=order_by,
        limit=100,
    )


def plan_query(
    question: str | RewrittenQuestion,
    schema_excerpt: str | None = None,
) -> QueryPlan:
    """Sinh QueryPlan cấu trúc thông qua structured LLM từ câu hỏi và schema excerpt."""
    if use_offline_tools():
        return _offline_plan_query(question)

    excerpt = schema_excerpt or build_schema_excerpt()
    text = question.text if isinstance(question, RewrittenQuestion) else str(question)

    messages = [
        {"role": "system", "content": registry().render("plan_query")},
        {
            "role": "user",
            "content": f"Schema excerpt:\n{excerpt}\n\nCâu hỏi của người dùng:\n{text}",
        },
    ]
    return invoke_structured(messages, QueryPlan)


def plan_query_safe(
    question: str | RewrittenQuestion,
    schema_excerpt: str | None = None,
) -> QueryPlan:
    """plan_query với fallback offline heuristic khi LLM lỗi."""
    try:
        return plan_query(question, schema_excerpt)
    except Exception:
        return _offline_plan_query(question)


def repair_plan_query(
    question: str | RewrittenQuestion,
    schema_excerpt: str,
    last_plan: QueryPlan,
    error_message: str,
) -> QueryPlan:
    """Replan sinh QueryPlan mới khi kế hoạch trước gặp lỗi validate hoặc execute."""
    if use_offline_tools():
        return _offline_plan_query(question)

    text = question.text if isinstance(question, RewrittenQuestion) else str(question)
    messages = [
        {"role": "system", "content": registry().render("plan_query_repair")},
        {
            "role": "user",
            "content": (
                f"Schema excerpt:\n{schema_excerpt}\n\n"
                f"Câu hỏi:\n{text}\n\n"
                f"QueryPlan trước đó:\n{last_plan.model_dump_json()}\n\n"
                f"Lỗi gặp phải:\n{error_message}\n\n"
                "Hãy sửa lại QueryPlan để khắc phục lỗi trên."
            ),
        },
    ]
    return invoke_structured(messages, QueryPlan)


def plan_and_execute(
    question: str | RewrittenQuestion,
    schema_excerpt: str | None = None,
    max_repairs: int | None = None,
) -> dict[str, Any]:
    """Quy trình thuần: plan -> build SQL -> validate -> execute kèm repair loop.

    Lặp lại tối đa `sql_repair_max` lần nếu validate hoặc execute gặp lỗi.
    Hàm thuần — graph gọi ở Phase 3.
    """
    excerpt = schema_excerpt or build_schema_excerpt()
    limit_repairs = settings.sql_repair_max if max_repairs is None else max_repairs
    plan = plan_query_safe(question, excerpt)

    for attempt in range(limit_repairs + 1):
        # 1. Build SQL
        try:
            sql, params = build_sql(plan)
        except Exception as e:
            err = f"Lỗi tạo SQL: {e}"
            if attempt < limit_repairs:
                plan = repair_plan_query(question, excerpt, plan, err)
                continue
            return {
                "success": False,
                "plan": plan,
                "sql": "",
                "params": [],
                "rows": [],
                "error": err,
            }

        # 2. Validate SQL
        val = validate_sql(sql)
        if not val.ok:
            err = f"Lỗi validate SQL: {val.reason}"
            if attempt < limit_repairs:
                plan = repair_plan_query(question, excerpt, plan, err)
                continue
            return {
                "success": False,
                "plan": plan,
                "sql": sql,
                "params": params,
                "rows": [],
                "error": err,
            }

        # 3. Execute SQL
        try:
            rows = execute_sql(sql, params)
            return {
                "success": True,
                "plan": plan,
                "sql": sql,
                "params": params,
                "rows": rows,
                "error": None,
            }
        except Exception as e:
            err = f"Lỗi thực thi SQL: {e}"
            if attempt < limit_repairs:
                plan = repair_plan_query(question, excerpt, plan, err)
                continue
            return {
                "success": False,
                "plan": plan,
                "sql": sql,
                "params": params,
                "rows": [],
                "error": err,
            }

    return {
        "success": False,
        "plan": plan,
        "sql": "",
        "params": [],
        "rows": [],
        "error": "Vượt quá số lần sửa truy vấn cho phép.",
    }
