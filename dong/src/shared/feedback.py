"""Human Feedback — Postgres agent DB (production); SQLite file khi test/offline."""
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
from src.infra.llm.schemas import FeedbackRequest
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
FEEDBACK_DB = DATA_DIR / 'feedback.db'
FEEDBACK_FILE = DATA_DIR / 'feedback.json'
ATTACHMENTS_DIR = DATA_DIR / 'feedback' / 'attachments'
_lock = threading.Lock()
_pg_migrate_done = False

def _get_target_db_path() -> Path:
    if FEEDBACK_FILE.name != 'feedback.json' or FEEDBACK_FILE.parent != DATA_DIR:
        return FEEDBACK_FILE.with_suffix('.db')
    return FEEDBACK_DB

def _use_postgres() -> bool:
    from src.infra.feedback.store import postgres_feedback_enabled
    if not postgres_feedback_enabled():
        return False
    return FEEDBACK_DB.parent == DATA_DIR and FEEDBACK_FILE.parent == DATA_DIR

def _get_connection(db_path: Path | None=None) -> sqlite3.Connection:
    target_db = db_path or _get_target_db_path()
    conn = sqlite3.connect(str(target_db), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode = WAL;')
    except Exception:
        pass
    return conn

def _init_sqlite_db(conn: sqlite3.Connection) -> None:
    conn.execute('\n        CREATE TABLE IF NOT EXISTS feedback (\n            id TEXT PRIMARY KEY,\n            timestamp TEXT NOT NULL,\n            session_id TEXT NOT NULL,\n            user_id TEXT NOT NULL,\n            rating TEXT NOT NULL,\n            feedback_reason TEXT,\n            attachment_path TEXT,\n            question TEXT NOT NULL,\n            answer TEXT NOT NULL,\n            agent_trace TEXT,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        );\n        ')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback (timestamp);')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback (rating);')
    conn.commit()

def _migrate_json_to_sqlite(conn: sqlite3.Connection) -> None:
    if not FEEDBACK_FILE.exists():
        return
    try:
        content = FEEDBACK_FILE.read_text(encoding='utf-8').strip()
        if not content:
            return
        records = json.loads(content)
        if not isinstance(records, list) or not records:
            return
        cursor = conn.cursor()
        migrated = 0
        for rec in records:
            if not isinstance(rec, dict) or not (rec['id'] if 'id' in rec else None):
                continue
            cursor.execute('SELECT 1 FROM feedback WHERE id = ?', (rec['id'],))
            if cursor.fetchone():
                continue
            trace_val = rec['agent_trace'] if 'agent_trace' in rec else None
            trace_str = json.dumps(trace_val, ensure_ascii=False) if trace_val is not None and (not isinstance(trace_val, str)) else trace_val if isinstance(trace_val, str) else None
            cursor.execute('\n                INSERT OR IGNORE INTO feedback (\n                    id, timestamp, session_id, user_id, rating, feedback_reason,\n                    attachment_path, question, answer, agent_trace\n                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                ', (rec['id'] if 'id' in rec else None, (rec['timestamp'] if 'timestamp' in rec else None) or datetime.now(timezone.utc).isoformat(), (rec['session_id'] if 'session_id' in rec else None) or 'default', (rec['user_id'] if 'user_id' in rec else None) or 'default', (rec['rating'] if 'rating' in rec else None) or 'positive', rec['feedback_reason'] if 'feedback_reason' in rec else None, rec['attachment_path'] if 'attachment_path' in rec else None, (rec['question'] if 'question' in rec else None) or '', (rec['answer'] if 'answer' in rec else None) or '', trace_str))
            migrated += 1
        if migrated > 0:
            conn.commit()
            logger.info('Đã migrate %d bản ghi từ feedback.json sang SQLite.', migrated)
    except Exception as exc:
        logger.warning('Không thể migrate feedback.json sang SQLite: %s', exc)

def _fetch_all_sqlite(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute('\n        SELECT id, timestamp, session_id, user_id, rating, feedback_reason,\n               attachment_path, question, answer, agent_trace\n        FROM feedback\n        ORDER BY timestamp ASC\n        ')
    results: list[dict[str, Any]] = []
    for r in cursor.fetchall():
        trace_obj = None
        if r['agent_trace']:
            try:
                trace_obj = json.loads(r['agent_trace'])
            except Exception:
                trace_obj = r['agent_trace']
        results.append({'id': r['id'], 'timestamp': r['timestamp'], 'session_id': r['session_id'], 'user_id': r['user_id'], 'rating': r['rating'], 'feedback_reason': r['feedback_reason'], 'attachment_path': r['attachment_path'], 'question': r['question'], 'answer': r['answer'], 'agent_trace': trace_obj})
    return results

def load_legacy_feedback_for_migration() -> list[dict[str, Any]]:
    """Đọc SQLite/JSON cũ trên disk (một lần khi Postgres trống)."""
    records = _load_legacy_sqlite_records()
    if records:
        return records
    return _load_legacy_json_records()

def _load_legacy_sqlite_records() -> list[dict[str, Any]]:
    target_db = _get_target_db_path()
    if not target_db.exists():
        return []
    try:
        with _get_connection(target_db) as conn:
            _init_sqlite_db(conn)
            return _fetch_all_sqlite(conn)
    except Exception as exc:
        logger.warning('Đọc feedback SQLite legacy: %s', exc)
        return []

def _load_legacy_json_records() -> list[dict[str, Any]]:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        content = FEEDBACK_FILE.read_text(encoding='utf-8').strip()
        if not content:
            return []
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except Exception as exc:
        logger.warning('Đọc feedback.json legacy: %s', exc)
        return []

def _ensure_sqlite_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    target_db = _get_target_db_path()
    target_db.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _get_connection(target_db) as conn:
            _init_sqlite_db(conn)
            _migrate_json_to_sqlite(conn)

def _ensure_postgres_migrated() -> None:
    global _pg_migrate_done
    if _pg_migrate_done or not _use_postgres():
        return
    from src.infra.feedback.store import ensure_feedback_storage
    ensure_feedback_storage(load_legacy_feedback_for_migration)
    _pg_migrate_done = True

def _sync_json_export(records: list[dict[str, Any]]) -> None:
    if _use_postgres():
        return
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        FEEDBACK_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        logger.warning('Không thể đồng bộ feedback.json: %s', exc)

def save_feedback_record(req: FeedbackRequest) -> dict[str, Any]:
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone()
    ts_str = now.strftime('%Y%m%d_%H%M%S')
    short_id = uuid.uuid4().hex[:6]
    feedback_id = f'fb_{ts_str}_{short_id}'
    iso_timestamp = now.isoformat()
    attachment_path: str | None = None
    if req.image_base64 and req.image_base64.strip():
        try:
            raw_b64 = req.image_base64.strip()
            if ',' in raw_b64:
                raw_b64 = raw_b64.split(',', 1)[1]
            img_bytes = base64.b64decode(raw_b64)
            if req.image_filename and req.image_filename.strip():
                clean_name = re.sub('[^a-zA-Z0-9_\\.-]', '_', req.image_filename.strip())
                img_filename = f'{feedback_id}_{clean_name}'
            else:
                img_filename = f'{feedback_id}.png'
            img_path = ATTACHMENTS_DIR / img_filename
            img_path.write_bytes(img_bytes)
            attachment_path = f'data/feedback/attachments/{img_filename}'
        except Exception as exc:
            logger.warning('Không thể lưu ảnh đính kèm feedback: %s', exc)
            raise ValueError('Không thể lưu ảnh đính kèm. Vui lòng thử lại.') from exc
    record: dict[str, Any] = {'id': feedback_id, 'timestamp': iso_timestamp, 'session_id': req.session_id, 'user_id': req.user_id, 'rating': req.rating, 'feedback_reason': req.feedback_reason, 'attachment_path': attachment_path, 'question': req.question, 'answer': req.answer, 'agent_trace': req.agent_trace}
    if _use_postgres():
        _ensure_postgres_migrated()
        from src.infra.feedback.store import insert_feedback
        with _lock:
            insert_feedback(record)
        return record
    _ensure_sqlite_dirs()
    target_db = _get_target_db_path()
    with _lock:
        try:
            with _get_connection(target_db) as conn:
                _init_sqlite_db(conn)
                trace_str = json.dumps(req.agent_trace, ensure_ascii=False) if req.agent_trace is not None else None
                conn.execute('\n                    INSERT INTO feedback (\n                        id, timestamp, session_id, user_id, rating, feedback_reason,\n                        attachment_path, question, answer, agent_trace\n                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n                    ', (feedback_id, iso_timestamp, req.session_id, req.user_id, req.rating, req.feedback_reason, attachment_path, req.question, req.answer, trace_str))
                conn.commit()
                _sync_json_export(_fetch_all_sqlite(conn))
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as db_err:
            logger.error('Lỗi ghi SQLite feedback: %s', db_err)
            _fallback_append_json(record)
    return record

def _fallback_append_json(record: dict[str, Any]) -> None:
    try:
        data: list[dict[str, Any]] = []
        if FEEDBACK_FILE.exists():
            try:
                content = FEEDBACK_FILE.read_text(encoding='utf-8').strip()
                if content:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        data = parsed
            except Exception:
                data = []
        data.append(record)
        FEEDBACK_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as exc:
        logger.error('Fallback ghi JSON thất bại: %s', exc)

def get_all_feedback() -> list[dict[str, Any]]:
    if _use_postgres():
        _ensure_postgres_migrated()
        from src.infra.feedback.store import fetch_all_feedback
        return fetch_all_feedback()
    _ensure_sqlite_dirs()
    target_db = _get_target_db_path()
    with _lock:
        if target_db.exists():
            try:
                with _get_connection(target_db) as conn:
                    _init_sqlite_db(conn)
                    records = _fetch_all_sqlite(conn)
                    if records:
                        return records
            except Exception as exc:
                logger.warning('Lỗi đọc feedback SQLite: %s', exc)
        return _load_legacy_json_records()
