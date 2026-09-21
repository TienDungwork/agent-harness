"""Test guardrail an toàn cho 3 DB mới (smart_face / firesmoke / anomaly).

Cần `.env` có DB_HOST + role read-only thật — skip nếu chưa cấu hình,
để `pytest` offline/CI vẫn sạch. Khớp specs/test-plan.md mục
"Test guardrail an toàn (2 lớp)" sau Phase 3.
"""

from __future__ import annotations

import pytest

from src.config import settings
from src.db.connection import get_connection

pytestmark = pytest.mark.skipif(
    not settings.db_configured,
    reason="Cần DB_HOST/DB_USER trong .env (Postgres thật)",
)

# (dbname settings key → table để SELECT/DELETE/UPDATE an toàn trên schema)
_NEW_DB_TABLES = (
    ("db_name_face", "smf_face_events"),
    ("db_name_fire", "fire_smoke_event"),
    ("db_name_anomaly", "anomaly_event"),
)


def _new_dbs() -> list[tuple[str, str]]:
    return [(getattr(settings, key), table) for key, table in _NEW_DB_TABLES]


def test_app_layer_select_tren_3_db_moi():
    """Lớp app: get_connection() + SELECT chạy được trên cả 3 DB mới."""
    for dbname, table in _new_dbs():
        with get_connection(dbname) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {table} LIMIT 1")
            cur.fetchall()  # rỗng (firesmoke) vẫn OK


def test_app_layer_delete_update_bi_readonly():
    """Lớp app: DELETE/UPDATE qua get_connection → ReadOnlySqlTransaction
    (conn.set_session(readonly=True)), giống v1 its/virtual_fence."""
    import psycopg2

    cases = [
        ("db_name_face", "DELETE FROM smf_face_events WHERE false"),
        ("db_name_fire", "UPDATE fire_smoke_event SET alert_level = alert_level WHERE false"),
        ("db_name_anomaly", "DELETE FROM anomaly_event WHERE false"),
    ]
    for key, sql in cases:
        dbname = getattr(settings, key)
        with get_connection(dbname) as conn, conn.cursor() as cur:
            with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
                cur.execute(sql)


def test_grant_layer_delete_bi_insufficient_privilege():
    """Lớp Postgres/GRANT: connect thô (không set_session readonly) →
    DELETE bị InsufficientPrivilege — chứng minh role không có quyền ghi
    dù bỏ lớp app."""
    import psycopg2

    for dbname, table in _new_dbs():
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=dbname,
            connect_timeout=5,
        )
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute(f"DELETE FROM {table} WHERE false")
        finally:
            conn.close()
