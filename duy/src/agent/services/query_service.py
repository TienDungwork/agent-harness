from __future__ import annotations

import json

from agent.config.settings import get_settings
from agent.services.connection import connect
from agent.tools.postgres.validator import validate_sql


def execute_query(dbname: str, sql: str) -> dict:
    check = validate_sql(sql)
    if not check.ok:
        raise ValueError(f"SQL bị từ chối: {check.reason}")

    s = get_settings()
    with connect(dbname) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchmany(s.max_rows)
            truncated = cur.fetchone() is not None
            payload = {
                "database": dbname,
                "row_count": len(rows),
                "truncated": truncated,
                "rows": [dict(r) for r in rows],
            }
    encoded = json.dumps(payload, default=str, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > s.max_result_bytes:
        raise ValueError("Kết quả vượt MAX_RESULT_BYTES")
    return payload
