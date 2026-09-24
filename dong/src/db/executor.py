"""SQL executor — thực thi câu truy vấn read-only trên Postgres (dong v5).

Sử dụng kết nối read-only có sẵn qua get_connection, trả về danh sách dòng dạng dict.
Bảo đảm kiểm tra cấu hình và validate SQL trước khi gửi tới DB.
"""

from __future__ import annotations

import re
from typing import Any

from src.config import settings
from src.db.catalog import get_database_for_sql
from src.db.connection import get_connection
from src.db.validator import validate_sql

_TABLE_REF = re.compile(
    r'\b(?:from|join)\s+(?:only\s+)?(?:(?:"?[a-zA-Z_][\w]*"?)\.)?"?([a-zA-Z_][\w]*)"?',
    re.IGNORECASE,
)


def execute_sql(
    sql: str,
    params: list | tuple | None = None,
    dbname: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Thực thi câu SQL SELECT read-only trên Postgres.

    Trả về tuple (rows, columns):
    - rows: danh sách các dòng dạng dict (cột -> giá trị).
    - columns: danh sách tên cột từ cursor.description (không rỗng kể cả khi 0 dòng).
    Nếu DB chưa được cấu hình, raise RuntimeError rõ ràng.
    """
    # 1. Kiểm tra an toàn SQL
    val = validate_sql(sql)
    if not val.ok:
        raise ValueError(f"SQL không hợp lệ: {val.reason}")

    # 2. Kiểm tra cấu hình kết nối DB
    if not settings.db_configured:
        raise RuntimeError("Database chưa được cấu hình (DB_HOST/DB_USER trống).")

    # 3. Xác định database nguồn nếu chưa truyền vào
    if not dbname:
        dbname = get_database_for_sql(sql)

    # 4. Mở kết nối read-only và thực thi
    import psycopg2.extras

    with get_connection(dbname) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params) if params else ())
            if cur.description:
                col_names = [desc[0] for desc in cur.description]
                rows = [dict(r) for r in cur.fetchall()]
                return rows, col_names
            return [], []
