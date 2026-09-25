"""Human Feedback persistence module — VMS KCN Hưng Phú (dong v8).

Lưu trữ đánh giá tốt/xấu kèm lý do, ảnh đính kèm và agent trace vào SQLite (data/feedback.db).
Đồng thời hỗ trợ đồng bộ xuất data/feedback.json để đảm bảo tính tương thích ngược.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any
import uuid

from src.llm.schemas import FeedbackRequest

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FEEDBACK_DB = DATA_DIR / "feedback.db"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
ATTACHMENTS_DIR = DATA_DIR / "feedback" / "attachments"

_lock = threading.Lock()


def _get_target_db_path() -> Path:
    """Trả về đường dẫn database SQLite tương ứng (hỗ trợ monkeypatch trong test)."""
    if FEEDBACK_FILE.name != "feedback.json" or FEEDBACK_FILE.parent != DATA_DIR:
        return FEEDBACK_FILE.with_suffix(".db")
    return FEEDBACK_DB


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Khởi tạo kết nối SQLite với timeout và WAL mode."""
    target_db = db_path or _get_target_db_path()
    conn = sqlite3.connect(str(target_db), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    """Tạo bảng feedback và chỉ mục nếu chưa tồn tại."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rating TEXT NOT NULL,
            feedback_reason TEXT,
            attachment_path TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            agent_trace TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback (timestamp);
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback (rating);
        """
    )
    conn.commit()


def _migrate_json_to_sqlite(conn: sqlite3.Connection) -> None:
    """Tự động migrate dữ liệu từ file feedback.json cũ sang SQLite (nếu có)."""
    if not FEEDBACK_FILE.exists():
        return
    try:
        content = FEEDBACK_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return
        records = json.loads(content)
        if not isinstance(records, list) or not records:
            return

        cursor = conn.cursor()
        migrated = 0
        for rec in records:
            if not isinstance(rec, dict) or not rec.get("id"):
                continue
            cursor.execute("SELECT 1 FROM feedback WHERE id = ?", (rec["id"],))
            if cursor.fetchone():
                continue
            trace_val = rec.get("agent_trace")
            trace_str = (
                json.dumps(trace_val, ensure_ascii=False)
                if trace_val is not None and not isinstance(trace_val, str)
                else (trace_val if isinstance(trace_val, str) else None)
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO feedback (
                    id, timestamp, session_id, user_id, rating, feedback_reason,
                    attachment_path, question, answer, agent_trace
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.get("id"),
                    rec.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                    rec.get("session_id") or "default",
                    rec.get("user_id") or "default",
                    rec.get("rating") or "positive",
                    rec.get("feedback_reason"),
                    rec.get("attachment_path"),
                    rec.get("question") or "",
                    rec.get("answer") or "",
                    trace_str,
                ),
            )
            migrated += 1
        if migrated > 0:
            conn.commit()
            logger.info("Đã migrate thành công %d bản ghi từ feedback.json sang SQLite feedback.db", migrated)
    except Exception as exc:
        logger.warning("Không thể tự động migrate feedback.json sang SQLite: %s", exc)


def _ensure_dirs() -> None:
    """Đảm bảo các thư mục lưu trữ data/feedback/attachments và DB SQLite đã khởi tạo."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    target_db = _get_target_db_path()
    target_db.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _get_connection(target_db) as conn:
            _init_db(conn)
            _migrate_json_to_sqlite(conn)


def _fetch_all_records(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Lấy danh sách tất cả các bản ghi feedback theo thứ tự thời gian từ SQLite."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, timestamp, session_id, user_id, rating, feedback_reason,
               attachment_path, question, answer, agent_trace
        FROM feedback
        ORDER BY timestamp ASC
        """
    )
    rows = cursor.fetchall()
    results: list[dict[str, Any]] = []
    for r in rows:
        trace_obj = None
        if r["agent_trace"]:
            try:
                trace_obj = json.loads(r["agent_trace"])
            except Exception:
                trace_obj = r["agent_trace"]
        results.append(
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "session_id": r["session_id"],
                "user_id": r["user_id"],
                "rating": r["rating"],
                "feedback_reason": r["feedback_reason"],
                "attachment_path": r["attachment_path"],
                "question": r["question"],
                "answer": r["answer"],
                "agent_trace": trace_obj,
            }
        )
    return results


def save_feedback_record(req: FeedbackRequest) -> dict[str, Any]:
    """Lưu bản ghi human feedback vào SQLite (data/feedback.db) và ảnh vào attachments.

    Đồng thời đồng bộ xuất sang data/feedback.json để duy trì tương thích ngược.
    """
    _ensure_dirs()

    now = datetime.now(timezone.utc).astimezone()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    feedback_id = f"fb_{ts_str}_{short_id}"
    iso_timestamp = now.isoformat()

    attachment_path: str | None = None
    if req.image_base64 and req.image_base64.strip():
        try:
            raw_b64 = req.image_base64.strip()
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(raw_b64)
            if req.image_filename and req.image_filename.strip():
                clean_name = re.sub(r"[^a-zA-Z0-9_\.-]", "_", req.image_filename.strip())
                img_filename = f"{feedback_id}_{clean_name}"
            else:
                img_filename = f"{feedback_id}.png"
            img_path = ATTACHMENTS_DIR / img_filename
            img_path.write_bytes(img_bytes)
            attachment_path = f"data/feedback/attachments/{img_filename}"
        except Exception as exc:
            logger.warning("Không thể lưu ảnh đính kèm feedback: %s", exc)
            raise ValueError("Không thể lưu ảnh đính kèm. Vui lòng thử lại.") from exc

    record: dict[str, Any] = {
        "id": feedback_id,
        "timestamp": iso_timestamp,
        "session_id": req.session_id,
        "user_id": req.user_id,
        "rating": req.rating,
        "feedback_reason": req.feedback_reason,
        "attachment_path": attachment_path,
        "question": req.question,
        "answer": req.answer,
        "agent_trace": req.agent_trace,
    }

    target_db = _get_target_db_path()
    with _lock:
        saved_to_sqlite = False
        try:
            with _get_connection(target_db) as conn:
                _init_db(conn)
                cursor = conn.cursor()
                trace_str = (
                    json.dumps(req.agent_trace, ensure_ascii=False)
                    if req.agent_trace is not None
                    else None
                )
                cursor.execute(
                    """
                    INSERT INTO feedback (
                        id, timestamp, session_id, user_id, rating, feedback_reason,
                        attachment_path, question, answer, agent_trace
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feedback_id,
                        iso_timestamp,
                        req.session_id,
                        req.user_id,
                        req.rating,
                        req.feedback_reason,
                        attachment_path,
                        req.question,
                        req.answer,
                        trace_str,
                    ),
                )
                conn.commit()
                saved_to_sqlite = True
                try:
                    target_db.chmod(0o666)
                except Exception:
                    pass

                # Đồng bộ dữ liệu sang file FEEDBACK_FILE (JSON) để tương thích ngược
                try:
                    all_records = _fetch_all_records(conn)
                    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
                    FEEDBACK_FILE.write_text(
                        json.dumps(all_records, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    try:
                        FEEDBACK_FILE.chmod(0o666)
                    except Exception:
                        pass
                except Exception as sync_exc:
                    logger.warning("Không thể đồng bộ feedback sang feedback.json: %s", sync_exc)
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as db_err:
            logger.error("Lỗi ghi SQLite (%s): %s. Kích hoạt fallback ghi file JSON trực tiếp.", type(db_err).__name__, db_err)
            _fallback_append_json(record)

    return record


def _fallback_append_json(record: dict[str, Any]) -> None:
    """Fallback lưu trực tiếp vào feedback.json nếu SQLite gặp sự cố phân quyền."""
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: list[dict[str, Any]] = []
        if FEEDBACK_FILE.exists():
            try:
                content = FEEDBACK_FILE.read_text(encoding="utf-8").strip()
                if content:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        data = parsed
            except Exception:
                data = []
        data.append(record)
        FEEDBACK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            FEEDBACK_FILE.chmod(0o666)
        except Exception:
            pass
        logger.info("Đã lưu bản ghi feedback thành công vào file JSON (chế độ fallback).")
    except Exception as exc:
        logger.error("Fallback ghi JSON thất bại: %s", exc)


def get_all_feedback() -> list[dict[str, Any]]:
    """Đọc toàn bộ bản ghi feedback từ SQLite (data/feedback.db), có fallback JSON."""
    _ensure_dirs()
    target_db = _get_target_db_path()
    with _lock:
        if target_db.exists():
            try:
                with _get_connection(target_db) as conn:
                    _init_db(conn)
                    records = _fetch_all_records(conn)
                    if records:
                        return records
            except Exception as exc:
                logger.warning("Lỗi đọc feedback từ SQLite (%s), thử fallback JSON: %s", type(exc).__name__, exc)

        # Fallback đọc từ JSON
        if FEEDBACK_FILE.exists():
            try:
                content = FEEDBACK_FILE.read_text(encoding="utf-8").strip()
                if content:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        return parsed
            except Exception as exc:
                logger.warning("Lỗi đọc feedback.json: %s", exc)

        return []
