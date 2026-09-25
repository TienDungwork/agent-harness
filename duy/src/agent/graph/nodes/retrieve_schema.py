from __future__ import annotations

import json

from agent.catalog.retrieval import retrieve_datasets
from agent.graph.state import AgentState
from agent.tools.postgres.schema import describe_table


def retrieve_schema(state: AgentState) -> dict:
    question = state.get("question") or ""
    datasets = retrieve_datasets(question)
    parts: list[str] = []
    usable: list[dict] = []
    errors: list[str] = []
    for ds in datasets:
        db = ds.get("database")
        table = ds.get("table")
        if not db or not table:
            continue
        try:
            info = describe_table(str(db), str(table))
            usable.append({**ds, "schema": info})
            parts.append(json.dumps({**ds, "schema": info}, ensure_ascii=False, default=str))
        except Exception as exc:  # table name may differ on .200
            errors.append(f"{db}.{table}: {exc}")
    excerpt = "\n\n".join(parts) if parts else "Không lấy được schema bảng catalog."
    if errors:
        excerpt += "\n\nLỗi schema:\n" + "\n".join(errors)
    return {
        "relevant_datasets": usable or datasets,
        "schema_excerpt": excerpt,
    }
