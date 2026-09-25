from __future__ import annotations

from agent.graph.state import AgentState
from agent.tools.postgres.query import query


def execute_sql(state: AgentState) -> dict:
    datasets = state.get("relevant_datasets") or []
    sql = (state.get("sql") or "").lower()
    dbname = None
    for ds in datasets:
        table = str(ds.get("table") or "").lower()
        if table and table in sql:
            dbname = str(ds.get("database") or "")
            break
    if not dbname:
        for ds in datasets:
            if ds.get("database"):
                dbname = str(ds["database"])
                break
    if not dbname:
        return {"error": "Không xác định được database để chạy SQL.", "query_result": {}}
    try:
        result = query(dbname, state.get("sql") or "")
        return {"query_result": result, "error": ""}
    except Exception as exc:
        return {
            "error": str(exc),
            "query_result": {"database": dbname, "row_count": 0, "truncated": False, "rows": []},
        }
