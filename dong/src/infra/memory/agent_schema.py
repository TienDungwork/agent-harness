"""DDL agent — đọc từ resource/db/agent/init.sql (một nguồn với Docker init)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_INIT_SQL = Path(__file__).resolve().parents[3] / "resource" / "db" / "agent" / "init.sql"


@lru_cache(maxsize=1)
def load_agent_storage_ddl() -> str:
    if not _INIT_SQL.is_file():
        raise FileNotFoundError(f"Thiếu agent DDL: {_INIT_SQL}")
    return _INIT_SQL.read_text(encoding="utf-8")


AGENT_STORAGE_DDL = load_agent_storage_ddl()
