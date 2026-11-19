"""Human Feedback — Postgres agent DB (production); SQLite file khi test/offline.

I/O nằm ở `src.infra.storage.feedback` (postgres.py / local.py); module này chỉ dựng record và chọn backend.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import uuid
from src.infra.llm.schemas import FeedbackRequest
from src.infra.storage.feedback import local
from src.infra.storage.feedback.local import (
    ATTACHMENTS_DIR,
    FEEDBACK_DB,
    FEEDBACK_FILE,
    load_legacy_feedback_for_migration,
)
_pg_migrate_done = False

def _use_postgres() -> bool:
    from src.infra.storage.feedback.postgres import postgres_feedback_enabled
    if not postgres_feedback_enabled():
        return False
    return local.uses_default_paths()

def _ensure_postgres_migrated() -> None:
    global _pg_migrate_done
    if _pg_migrate_done or not _use_postgres():
        return
    from src.infra.storage.feedback.postgres import ensure_feedback_storage
    ensure_feedback_storage(load_legacy_feedback_for_migration)
    _pg_migrate_done = True

def save_feedback_record(req: FeedbackRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone()
    feedback_id = f"fb_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    attachment_path: str | None = None
    if req.image_base64 and req.image_base64.strip():
        attachment_path = local.save_attachment(feedback_id, req.image_base64, req.image_filename)
    record: dict[str, Any] = {'id': feedback_id, 'timestamp': now.isoformat(), 'session_id': req.session_id, 'user_id': req.user_id, 'rating': req.rating, 'feedback_reason': req.feedback_reason, 'attachment_path': attachment_path, 'question': req.question, 'answer': req.answer, 'agent_trace': req.agent_trace}
    if _use_postgres():
        _ensure_postgres_migrated()
        from src.infra.storage.feedback.postgres import insert_feedback
        with local.lock:
            insert_feedback(record)
        return record
    local.insert_local(record)
    return record

def get_all_feedback() -> list[dict[str, Any]]:
    if _use_postgres():
        _ensure_postgres_migrated()
        from src.infra.storage.feedback.postgres import fetch_all_feedback
        return fetch_all_feedback()
    return local.fetch_all_local()

__all__ = [
    'ATTACHMENTS_DIR',
    'FEEDBACK_DB',
    'FEEDBACK_FILE',
    'get_all_feedback',
    'load_legacy_feedback_for_migration',
    'save_feedback_record',
]
