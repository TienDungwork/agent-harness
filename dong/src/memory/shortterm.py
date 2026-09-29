"""Short-term memory checkpointer module for LangGraph (v9).

Cung cấp checkpointer phiên cho LangGraph:
1. Khi có cấu hình PostgreSQL và kết nối thành công:
   Khởi tạo PostgresSaver (sử dụng psycopg_pool.ConnectionPool) để lưu phiên bền vững,
   tự động gọi .setup() để bảo đảm schema checkpoints đã tồn tại.
2. Graceful Degradation:
   Nếu PostgreSQL chưa được cấu hình, kết nối thất bại hoặc gặp lỗi,
   tự động fallback sang MemorySaver() trong RAM mà không làm gián đoạn ứng dụng.
3. Thread-safe Singleton:
   Đảm bảo chỉ có một instance checkpointer duy nhất được dùng xuyên suốt phiên làm việc.
4. Tôn trọng cấu hình:
   Khi settings.short_term_memory_enabled là False, get_checkpointer() trả về None.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_checkpointer_instance: Optional[BaseCheckpointSaver] = None
_pool_instance: Optional[ConnectionPool] = None
_lock = threading.Lock()


def is_using_postgres_checkpointer() -> bool:
    """Kiểm tra xem checkpointer hiện tại có phải là PostgresSaver hay không."""
    if _checkpointer_instance is None:
        return False
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        if isinstance(_checkpointer_instance, PostgresSaver):
            return True
    except Exception:
        pass
    cls_name = getattr(_checkpointer_instance, "__class__", type(_checkpointer_instance)).__name__
    return cls_name == "PostgresSaver"


def _create_postgres_checkpointer() -> Optional[BaseCheckpointSaver]:
    """Cố gắng kết nối PostgreSQL và khởi tạo PostgresSaver với ConnectionPool."""
    from src.config import settings
    from src.memory.db import is_postgres_configured

    if not is_postgres_configured():
        logger.info("PostgreSQL chưa được cấu hình. Fallback sang MemorySaver.")
        return None

    try:
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        dbname = getattr(settings, "db_name_memory", None) or settings.db_name_its or "its"
        conn_string = (
            f"postgresql://{settings.db_user}:{settings.db_password}@"
            f"{settings.db_host}:{settings.db_port}/{dbname}"
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
        logger.info("Khởi tạo PostgresSaver checkpointer thành công trên PostgreSQL.")
        return saver
    except Exception as exc:
        logger.warning(
            "Không thể kết nối hoặc khởi tạo PostgresSaver: %s. Chuyển sang in-memory fallback (MemorySaver).",
            exc,
        )
        return None


def get_checkpointer() -> Optional[BaseCheckpointSaver]:
    """Trả về checkpointer singleton cho LangGraph.

    - Trả về None nếu short_term_memory_enabled bị tắt.
    - Trả về PostgresSaver nếu kết nối DB thành công.
    - Fallback sang MemorySaver trong RAM nếu DB không sẵn sàng hoặc gặp lỗi.
    """
    from src.config import settings

    if not settings.short_term_memory_enabled:
        return None

    global _checkpointer_instance
    if _checkpointer_instance is not None:
        return _checkpointer_instance

    with _lock:
        if _checkpointer_instance is not None:
            return _checkpointer_instance

        # Thử khởi tạo PostgresSaver an toàn
        saver = None
        try:
            saver = _create_postgres_checkpointer()
        except Exception as exc:
            logger.warning(
                "Ngoại lệ khi gọi _create_postgres_checkpointer: %s. Fallback MemorySaver.",
                exc,
            )

        if saver is None:
            saver = MemorySaver()
            logger.info("Sử dụng MemorySaver (in-memory) cho short-term memory.")

        _checkpointer_instance = saver
        return _checkpointer_instance


def reset_checkpointer() -> None:
    """Reset checkpointer singleton (phục vụ test suite và reload cấu hình)."""
    global _checkpointer_instance, _pool_instance
    with _lock:
        if _pool_instance is not None:
            try:
                _pool_instance.close()
            except Exception:
                pass
            _pool_instance = None
        _checkpointer_instance = None
