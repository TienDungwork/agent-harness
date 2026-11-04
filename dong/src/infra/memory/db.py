"""PostgreSQL — agent storage (memory + sessions). Tách AGENT_DB_* khỏi VMS DB_*."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from src.infra.memory.agent_schema import load_agent_storage_ddl
from src.shared.config import settings

logger = logging.getLogger(__name__)


class AgentStorageError(RuntimeError):
    """Agent Postgres chưa sẵn sàng."""


def agent_db_name() -> str:
    return (settings.db_name_agent or "kcn_agent").strip()


def is_postgres_configured() -> bool:
    return settings.agent_db_configured


def _connect_kwargs() -> dict:
    if not is_postgres_configured():
        raise AgentStorageError(
            "Agent DB chưa cấu hình — set AGENT_DB_HOST, AGENT_DB_USER, AGENT_DB_PASSWORD, DB_NAME_AGENT."
        )
    tz = (settings.db_timezone or "Asia/Ho_Chi_Minh").strip().strip("'\"")
    return {
        "host": settings.agent_db_host,
        "port": settings.agent_db_port,
        "user": settings.agent_db_user,
        "password": settings.agent_db_password,
        "dbname": agent_db_name(),
        "connect_timeout": int(settings.db_query_timeout_s or 5),
        "options": f"-c timezone={tz}",
    }


@contextmanager
def get_memory_connection(autocommit: bool = True) -> Generator:
    import psycopg2

    conn = psycopg2.connect(**_connect_kwargs())
    conn.autocommit = autocommit
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_memory_db() -> bool:
    return init_agent_storage()


def init_agent_storage() -> bool:
    ddl = load_agent_storage_ddl()
    try:
        with get_memory_connection(autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        logger.info("Agent storage schema OK (db=%s @ %s).", agent_db_name(), settings.agent_db_host)
        return True
    except AgentStorageError:
        raise
    except Exception as exc:
        raise AgentStorageError(f"Không khởi tạo được schema agent: {exc}") from exc
