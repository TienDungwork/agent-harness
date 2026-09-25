from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent.config.settings import get_settings

_pools: dict[str, ConnectionPool] = {}


def _kwargs(dbname: str) -> dict:
    s = get_settings()
    if not s.db_host or not s.db_user:
        raise RuntimeError("Chưa cấu hình DB (thiếu DB_HOST/DB_USER trong .env).")
    return {
        "host": s.db_host,
        "port": s.db_port,
        "user": s.db_user,
        "password": s.db_password,
        "dbname": dbname,
        "connect_timeout": s.connect_timeout_seconds,
        "autocommit": True,
        "row_factory": dict_row,
    }


def get_pool(dbname: str) -> ConnectionPool:
    pool = _pools.get(dbname)
    if pool is None:
        s = get_settings()
        pool = ConnectionPool(
            min_size=1,
            max_size=4,
            timeout=s.connect_timeout_seconds,
            kwargs=_kwargs(dbname),
            open=True,
        )
        _pools[dbname] = pool
    return pool


@contextmanager
def connect(dbname: str) -> Iterator[psycopg.Connection]:
    s = get_settings()
    with get_pool(dbname).connection() as conn:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute(f"SET statement_timeout = '{int(s.query_timeout_seconds)}s'")
        yield conn


def ping() -> dict:
    with connect("postgres") as conn:
        row = conn.execute("SELECT 1 AS ok, current_user, current_database()").fetchone()
    return dict(row or {})
