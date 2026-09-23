"""Node execute_sql — thực thi câu truy vấn SQL đọc-only trên Postgres (Phase 3c)."""

from __future__ import annotations

from typing import Any

from src.agent.node_io import node_event
from src.agent.sql_scope import apply_organization_scope
from src.db.executor import execute_sql
from src.db.validator import validate_sql
from src.llm.client import use_offline_tools
from src.monitoring.tracing import trace_substep


def execute_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """Re-validate SQL query and execute on read-only Postgres database.

    Returns ``{"rows": list, "columns": list, "error": str, "events": list}``.
    """
    sql = (state.get("sql") or "").strip()
    params = state.get("params") or []
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    with trace_substep("apply_org_scope", kind="tool", input={"sql": sql}) as sub:
        sql = apply_organization_scope(sql)
        sub["output"] = {"sql": sql}

    with trace_substep("revalidate_sql", kind="tool", input={"sql": sql}) as sub:
        val = validate_sql(sql)
        sub["output"] = val.to_dict()

    if not val.ok:
        err_msg = f"SQL không hợp lệ: {val.reason}"
        return {
            "rows": [],
            "columns": [],
            "error": err_msg,
            "events": [
                node_event(
                    "execute_sql",
                    input={"sql": sql, "params": params},
                    output={"rows": [], "columns": [], "error": err_msg, "revalidate_failed": True},
                    meta={"user_id": user_id, "session_id": session_id, "ok": False},
                )
            ],
        }

    if use_offline_tools():
        if "CROWD_DETECTION" in sql or "crowd" in sql.lower() or "đám đông" in sql.lower():
            offline_rows = [{"count": 0}]
        else:
            offline_rows = [{"count": 42}]
        columns = list(offline_rows[0].keys())
        return {
            "rows": offline_rows,
            "columns": columns,
            "error": "",
            "events": [
                node_event(
                    "execute_sql",
                    input={"sql": sql, "params": params, "offline": True},
                    output={"rows": offline_rows, "columns": columns, "row_count": len(offline_rows)},
                    meta={"user_id": user_id, "session_id": session_id, "offline": True},
                )
            ],
        }

    try:
        with trace_substep("postgres_query", kind="tool", input={"sql": sql, "params": params}) as sub:
            result = execute_sql(sql, params)
            if isinstance(result, tuple) and len(result) == 2:
                rows, db_columns = result
                columns = list(db_columns) if db_columns else (list(rows[0].keys()) if rows else [])
            else:
                rows = list(result) if result is not None else []
                columns = list(rows[0].keys()) if rows else []
            sub["output"] = {"row_count": len(rows), "columns": columns}
        return {
            "rows": rows,
            "columns": columns,
            "error": "",
            "events": [
                node_event(
                    "execute_sql",
                    input={"sql": sql, "params": params},
                    output={"rows": rows, "columns": columns, "row_count": len(rows)},
                    meta={"user_id": user_id, "session_id": session_id, "ok": True},
                )
            ],
        }
    except Exception as exc:
        err_msg = str(exc)
        return {
            "rows": [],
            "columns": [],
            "error": err_msg,
            "events": [
                node_event(
                    "execute_sql",
                    input={"sql": sql, "params": params},
                    output={"rows": [], "columns": [], "error": err_msg},
                    meta={"user_id": user_id, "session_id": session_id, "ok": False},
                )
            ],
        }
