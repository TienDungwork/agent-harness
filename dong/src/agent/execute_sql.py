"""Node execute_sql — thực thi câu truy vấn SQL đọc-only trên Postgres (Phase 3c)."""

from __future__ import annotations

from typing import Any

from src.agent.node_io import node_event
from src.db.executor import execute_sql
from src.db.validator import validate_sql
from src.llm.client import use_offline_tools


def execute_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """Re-validate SQL query and execute on read-only Postgres database.

    Returns ``{"rows": list, "columns": list, "error": str, "events": list}``.
    """
    sql = (state.get("sql") or "").strip()
    params = state.get("params") or []
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    # 1. Re-validate SQL (Layer 1 before DB call)
    val = validate_sql(sql)
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

    # 2. Offline mock fallback
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

    # 3. Execute query on Postgres (Layer 2 in executor also validates)
    try:
        result = execute_sql(sql, params)
        # execute_sql returns (rows, columns) tuple in production; test mocks may return a list
        if isinstance(result, tuple) and len(result) == 2:
            rows, db_columns = result
            columns = list(db_columns) if db_columns else (list(rows[0].keys()) if rows else [])
        else:
            rows = list(result) if result is not None else []
            columns = list(rows[0].keys()) if rows else []
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
