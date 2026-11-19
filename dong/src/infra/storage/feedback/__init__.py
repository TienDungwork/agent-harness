"""Human feedback persistence — postgres.py (production) / local.py (SQLite/JSON + attachments)."""

from src.infra.storage.feedback.postgres import (
    ensure_feedback_storage,
    fetch_all_feedback,
    insert_feedback,
    postgres_feedback_enabled,
)

__all__ = [
    "ensure_feedback_storage",
    "fetch_all_feedback",
    "insert_feedback",
    "postgres_feedback_enabled",
]
