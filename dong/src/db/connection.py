"""Kết nối Postgres read-only — 5 database nguồn thống kê thật:

    its           — plate_event (lượt ra/vào + biển số + loại xe, camera ITS)
    virtual_fence — zone_event (xâm nhập khu vực hàng rào ảo)
    smart_face    — smf_face_events (nhận diện khuôn mặt) [Phase 2, mới]
    firesmoke     — fire_smoke_event (cháy/khói) [Phase 2, mới]
    anomaly       — anomaly_event (ẩu đả/đám đông/leo trèo/mực nước) [Phase 2, mới]

Dùng role riêng CHỈ có quyền SELECT trên 5 DB này (không phải superuser/dev) —
xem README mục "Tạo DB role read-only" + specs/change-log.md 2026-09-17 (đã
GRANT SELECT cho 3 DB mới trên role agent_readonly có sẵn). Mỗi connection
còn tự set `default_transaction_read_only = on` làm lớp chặn thứ hai ở tầng
DB, độc lập với việc validate SQL ở tầng code (src/agent/tools.py, Phase 4-5).
"""

from __future__ import annotations

from contextlib import contextmanager

from src.config import settings


def is_configured() -> bool:
    return settings.db_configured


def _allowed_dbnames() -> set[str]:
    return {
        settings.db_name_its,
        settings.db_name_fence,
        settings.db_name_face,
        settings.db_name_fire,
        settings.db_name_anomaly,
    }


@contextmanager
def get_connection(dbname: str):
    """Context manager — 1 connection Postgres read-only, đóng khi xong.

    `dbname` PHẢI là 1 trong 5 DB đã khai báo (its/virtual_fence/smart_face/
    firesmoke/anomaly) — chặn ở code trước khi mở connection, không dựa hoàn
    toàn vào quyền Postgres của
    role `agent_readonly` (vốn cũng chặn SELECT ở DB khác, nhưng CONNECT vẫn
    qua — xem README mục "Tạo DB role read-only"). Lớp chặn thêm ở đây tránh
    lỗi gõ sai tên DB âm thầm mở connection tới nơi không định trước.

    Không dùng connection pool (psycopg2 pool) ở MVP này — traffic thấp, mỗi
    request 1-2 query ngắn; thêm pool sau nếu cần (đa người dùng, xem
    product-spec.md mục Out of Scope).
    """
    if dbname not in _allowed_dbnames():
        raise ValueError(f"dbname='{dbname}' không hợp lệ — chỉ chấp nhận {sorted(_allowed_dbnames())}.")

    import psycopg2

    tz = (settings.db_timezone or "Asia/Ho_Chi_Minh").strip().strip("'\"")
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        dbname=dbname,
        connect_timeout=5,
        options=f"-c timezone={tz}",
    )
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(settings.db_query_timeout_s * 1000)};")
            cur.execute("SET timezone = %s;", (tz,))
        yield conn
    finally:
        conn.close()
