"""Human feedback — PostgreSQL (agent DB)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from psycopg2.extras import Json

from src.infra.memory.db import AgentStorageError, get_memory_connection, is_postgres_configured

logger = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO human_feedback (
    id, ts, session_id, user_id, rating, feedback_reason,
    attachment_path, question, answer, agent_trace
) VALUES (
    %(id)s, %(ts)s::timestamptz, %(session_id)s, %(user_id)s, %(rating)s, %(feedback_reason)s,
    %(attachment_path)s, %(question)s, %(answer)s, %(agent_trace)s
)
ON CONFLICT (id) DO NOTHING
"""

_SELECT_ALL_SQL = """
SELECT id, ts, session_id, user_id, rating, feedback_reason,
       attachment_path, question, answer, agent_trace
FROM human_feedback
ORDER BY ts ASC
"""


def postgres_feedback_enabled() -> bool:
    return is_postgres_configured()


def _row_to_record(row: tuple) -> dict[str, Any]:
    ts = row[1]
    ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return {
        "id": row[0],
        "timestamp": ts_str,
        "session_id": row[2],
        "user_id": row[3],
        "rating": row[4],
        "feedback_reason": row[5],
        "attachment_path": row[6],
        "question": row[7],
        "answer": row[8],
        "agent_trace": row[9],
    }


def insert_feedback(record: dict[str, Any]) -> None:
    if not postgres_feedback_enabled():
        raise AgentStorageError("Agent Postgres chưa cấu hình cho feedback.")
    trace = record.get("agent_trace")
    params = {
        "id": record["id"],
        "ts": record["timestamp"],
        "session_id": record["session_id"],
        "user_id": record["user_id"],
        "rating": record["rating"],
        "feedback_reason": record.get("feedback_reason"),
        "attachment_path": record.get("attachment_path"),
        "question": record["question"],
        "answer": record["answer"],
        "agent_trace": Json(trace) if trace is not None else None,
    }
    with get_memory_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_INSERT_SQL, params)


def fetch_all_feedback() -> list[dict[str, Any]]:
    if not postgres_feedback_enabled():
        return []
    with get_memory_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_SELECT_ALL_SQL)
            rows = cur.fetchall()
    return [_row_to_record(r) for r in rows]


def migrate_legacy_records(records: list[dict[str, Any]]) -> int:
    if not records or not postgres_feedback_enabled():
        return 0
    migrated = 0
    with get_memory_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM human_feedback")
            if int(cur.fetchone()[0]) > 0:
                return 0
            for rec in records:
                if not isinstance(rec, dict) or not rec.get("id"):
                    continue
                trace = rec.get("agent_trace")
                cur.execute(
                    _INSERT_SQL,
                    {
                        "id": rec["id"],
                        "ts": rec.get("timestamp"),
                        "session_id": rec.get("session_id") or "default",
                        "user_id": rec.get("user_id") or "default",
                        "rating": rec.get("rating") or "positive",
                        "feedback_reason": rec.get("feedback_reason"),
                        "attachment_path": rec.get("attachment_path"),
                        "question": rec.get("question") or "",
                        "answer": rec.get("answer") or "",
                        "agent_trace": Json(trace) if trace is not None else None,
                    },
                )
                migrated += 1
    if migrated:
        logger.info("Đã migrate %d bản ghi feedback sang Postgres.", migrated)
    return migrated


def ensure_feedback_storage(legacy_loader: Callable[[], list[dict[str, Any]]]) -> None:
    if not postgres_feedback_enabled():
        return
    try:
        migrate_legacy_records(legacy_loader())
    except Exception as exc:
        logger.warning("Migrate feedback legacy thất bại (bỏ qua): %s", exc)
