"""Node execute_sql — thực thi câu truy vấn SQL đọc-only trên Postgres (Phase 3c)."""

from __future__ import annotations

from typing import Any

from src.domain.agents.nodes.io import node_event
from src.domain.agents.sql.scope import apply_organization_scope
from src.infra.db.executor import execute_sql
from src.infra.db.validator import validate_sql
from src.infra.llm.client import use_offline_tools
from src.infra.monitoring.tracing import current_span, trace_step


def execute_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """Re-validate SQL query and execute on read-only Postgres database.

    Returns ``{"rows": list, "columns": list, "error": str, "events": list}``.
    Batch multi-hop: ``sql_batch_results`` — một entry mỗi sub-question.
    """
    sql_batch = state.get("sql_batch") or []
    user_id = state.get("user_id") or "default"
    session_id = state.get("session_id") or "default"

    if len(sql_batch) >= 2:
        batch_results: list[dict[str, Any]] = []
        for item in sql_batch:
            sq = item.get("sub_question", "")
            sql = (item.get("sql") or "").strip()
            entry: dict[str, Any] = {
                "sub_question": sq,
                "sql": sql,
                "rows": [],
                "columns": [],
                "error": "",
            }
            with trace_step(current_span(), "apply_org_scope", input={"sub_question": sq}, as_type="tool") as sub:
                sql = apply_organization_scope(sql)
                entry["sql"] = sql
                sub["output"] = {"sql_len": len(sql)}
            with trace_step(current_span(), "revalidate_sql", input={"sql_len": len(sql)}, as_type="tool") as sub:
                val = validate_sql(sql)
                sub["output"] = val.to_dict()
            if not val.ok:
                entry["error"] = val.reason
                batch_results.append(entry)
                continue
            try:
                with trace_step(
                    current_span(),
                    "postgres_query",
                    input={"sub_question": sq, "sql_len": len(sql)},
                    as_type="tool",
                ) as sub:
                    if use_offline_tools():
                        if "CROWD_DETECTION" in sql or "crowd" in sql.lower():
                            rows = [{"count": 0}]
                        elif "zone_event" in sql:
                            rows = [{"count": 12}]
                        elif "plate_event" in sql:
                            rows = [{"count": 42}]
                        else:
                            rows = [{"count": 42}]
                        columns = ["count"]
                    else:
                        result = execute_sql(sql, [])
                        if isinstance(result, tuple) and len(result) == 2:
                            rows, db_columns = result
                            columns = list(db_columns) if db_columns else (list(rows[0].keys()) if rows else [])
                        else:
                            rows = list(result) if result is not None else []
                            columns = list(rows[0].keys()) if rows else []
                    entry["rows"] = rows
                    entry["columns"] = columns
                    sub["output"] = {"row_count": len(rows), "columns": columns}
            except Exception as exc:
                entry["error"] = str(exc)
            batch_results.append(entry)
        last = batch_results[-1] if batch_results else {}
        return {
            "sql_batch_results": batch_results,
            "rows": last.get("rows") or [],
            "columns": last.get("columns") or [],
            "error": "",
            "events": [node_event(
                "execute_sql",
                input={"sql_batch": sql_batch, "batch_size": len(sql_batch)},
                output={"sql_batch_results": batch_results, "batch_size": len(batch_results)},
                meta={"user_id": user_id, "session_id": session_id, "batch": True, "ok": True},
            )],
        }

    sql = (state.get("sql") or "").strip()
    params = state.get("params") or []

    with trace_step(current_span(), "apply_org_scope", input={"sql": sql}, as_type="tool") as sub:
        sql = apply_organization_scope(sql)
        sub["output"] = {"sql": sql}

    with trace_step(current_span(), "revalidate_sql", input={"sql": sql}, as_type="tool") as sub:
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

    try:
        with trace_step(current_span(), "postgres_query", input={"sql": sql, "params": params}, as_type="tool") as sub:
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
