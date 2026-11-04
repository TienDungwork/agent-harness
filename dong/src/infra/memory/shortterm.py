"""Short-term LangGraph checkpointer — PostgresSaver trên AGENT_DB_*."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

from src.infra.memory.db import AgentStorageError, _connect_kwargs, agent_db_name, is_postgres_configured

logger = logging.getLogger(__name__)

_checkpointer_instance: Optional[BaseCheckpointSaver] = None
_pool_instance: Optional[ConnectionPool] = None
_lock = threading.Lock()


def is_using_postgres_checkpointer() -> bool:
    return _checkpointer_instance is not None


def _create_postgres_checkpointer() -> BaseCheckpointSaver:
    from src.shared.config import settings

    if not settings.memory_enabled:
        raise AgentStorageError("MEMORY_ENABLED=false — không dùng checkpointer.")
    if not settings.short_term_memory_enabled:
        raise AgentStorageError("MEMORY_SHORT_TERM_ENABLED=false — short-term bắt buộc bật.")
    if not is_postgres_configured():
        raise AgentStorageError("Agent DB chưa cấu hình cho PostgresSaver.")

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    from urllib.parse import quote_plus

    kw = _connect_kwargs()
    conn_string = (
        f"postgresql://{quote_plus(kw['user'])}:{quote_plus(kw['password'])}@"
        f"{kw['host']}:{kw['port']}/{quote_plus(kw['dbname'])}"
    )
    pool = ConnectionPool(
        conninfo=conn_string,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=True,
        timeout=float(settings.db_query_timeout_s or 5.0),
    )
    saver = PostgresSaver(pool)
    saver.setup()
    global _pool_instance
    _pool_instance = pool
    logger.info("PostgresSaver OK (db=%s @ %s).", agent_db_name(), kw["host"])
    return saver


def get_checkpointer() -> BaseCheckpointSaver:
    from src.shared.config import settings

    if not settings.memory_enabled:
        raise AgentStorageError("MEMORY_ENABLED=false — bật memory để chạy agent.")

    global _checkpointer_instance
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    with _lock:
        if _checkpointer_instance is not None:
            return _checkpointer_instance
        _checkpointer_instance = _create_postgres_checkpointer()
        return _checkpointer_instance


def reset_checkpointer() -> None:
    global _checkpointer_instance, _pool_instance
    with _lock:
        if _pool_instance is not None:
            try:
                _pool_instance.close()
            except Exception:
                pass
            _pool_instance = None
        _checkpointer_instance = None
