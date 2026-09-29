"""PostgreSQL database persistence manager for Memory System (v9).

Cung cấp kết nối và cơ chế tự động khởi tạo bảng `user_memories` trong PostgreSQL.
Hỗ trợ cơ chế an toàn tuyệt đối (Graceful Degradation): Nếu không có kết nối DB,
hàm sẽ log warning và trả về False, tuyệt đối không ném exception làm crash app.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from src.config import settings

logger = logging.getLogger(__name__)

DDL_CREATE_USER_MEMORIES = """
CREATE TABLE IF NOT EXISTS user_memories (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    fact TEXT NOT NULL,
    category VARCHAR(32) DEFAULT 'general',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_user_memories_uid ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_user_memories_uid_created ON user_memories(user_id, created_at DESC);
"""


def is_postgres_configured() -> bool:
    """Kiểm tra xem thông tin kết nối PostgreSQL có được cấu hình hay không."""
    return bool(settings.db_host and settings.db_user)


@contextmanager
def get_memory_connection(autocommit: bool = True) -> Generator:
    """Context manager mở 1 kết nối tới PostgreSQL để thao tác với bảng memory.

    Tự động đóng kết nối khi kết thúc khối with.
    Nếu xảy ra lỗi kết nối, ném exception để caller trong longterm xử lý fallback.
    """
    if not is_postgres_configured():
        raise RuntimeError("PostgreSQL chưa được cấu hình (DB_HOST hoặc DB_USER trống).")

    import psycopg2

    dbname = getattr(settings, "db_name_memory", None) or settings.db_name_its or "its"
    tz = (settings.db_timezone or "Asia/Ho_Chi_Minh").strip().strip("'\"")

    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=dbname,
        connect_timeout=int(settings.db_query_timeout_s or 5),
        options=f"-c timezone={tz}",
    )
    conn.autocommit = autocommit
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_memory_db() -> bool:
    """Khởi tạo schema bảng `user_memories` trong PostgreSQL nếu chưa tồn tại.

    Trả về:
        True: nếu khởi tạo hoặc bảng đã sẵn sàng trong DB.
        False: nếu DB chưa cấu hình hoặc không kết nối được (fallback chế độ in-memory).
    """
    if not is_postgres_configured():
        logger.info("PostgreSQL chưa được cấu hình. Sử dụng in-memory fallback cho Memory System.")
        return False

    try:
        with get_memory_connection(autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(DDL_CREATE_USER_MEMORIES)
        logger.info("Khởi tạo schema bảng `user_memories` thành công trên PostgreSQL.")
        return True
    except Exception as exc:
        logger.warning(
            "Không thể kết nối hoặc khởi tạo bảng memory trên PostgreSQL: %s. Chuyển sang in-memory fallback.",
            exc,
        )
        return False
