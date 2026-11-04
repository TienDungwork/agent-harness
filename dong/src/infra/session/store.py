"""Session store — PostgreSQL (chat_sessions + chat_session_messages)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.infra.memory.db import AgentStorageError, get_memory_connection, init_agent_storage, is_postgres_configured


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_storage() -> None:
    if not is_postgres_configured():
        raise AgentStorageError("PostgreSQL chưa cấu hình cho sessions.")


def clear_sessions_store() -> None:
    _ensure_storage()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_session_messages;")
            cur.execute("DELETE FROM chat_sessions;")


def list_sessions(user_id: str) -> list[dict[str, Any]]:
    if not user_id:
        return []
    _ensure_storage()
    uid = user_id.strip()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, preview, created_at, updated_at
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY updated_at DESC;
                """,
                (uid,),
            )
            rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r[0],
            "user_id": r[1],
            "title": r[2],
            "preview": r[3] or "",
            "messages": [],
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            "updated_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
        })
    return out


def create_session(user_id: str, title: str | None = None) -> dict[str, Any]:
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required")
    _ensure_storage()
    uid = user_id.strip()
    now = _now_iso()
    session_id = str(uuid.uuid4())
    sess_title = title.strip() if (title and title.strip()) else "Phiên chat mới"
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, user_id, title, preview, created_at, updated_at)
                VALUES (%s, %s, %s, '', %s::timestamptz, %s::timestamptz);
                """,
                (session_id, uid, sess_title, now, now),
            )
    return {
        "id": session_id,
        "user_id": uid,
        "title": sess_title,
        "preview": "",
        "messages": [],
        "updated_at": now,
        "created_at": now,
    }


def get_session(session_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    if not session_id or not user_id:
        return None
    _ensure_storage()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, title, preview, created_at, updated_at
                FROM chat_sessions WHERE id = %s AND user_id = %s;
                """,
                (session_id.strip(), user_id.strip()),
            )
            r = cur.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "user_id": r[1],
        "title": r[2],
        "preview": r[3] or "",
        "messages": [],
        "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        "updated_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
    }


def delete_session(session_id: str, user_id: str) -> bool:
    if not session_id or not user_id:
        return False
    _ensure_storage()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s AND user_id = %s;",
                (session_id.strip(), user_id.strip()),
            )
            return cur.rowcount > 0


def get_session_messages(session_id: str, user_id: str) -> list[dict[str, Any]] | None:
    if get_session(session_id, user_id) is None:
        return None
    _ensure_storage()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload FROM chat_session_messages
                WHERE session_id = %s AND user_id = %s
                ORDER BY id ASC;
                """,
                (session_id.strip(), user_id.strip()),
            )
            rows = cur.fetchall()
    return [dict(r[0]) if isinstance(r[0], dict) else json.loads(r[0]) for r in rows]


def append_session_messages(
    session_id: str,
    user_id: str,
    new_messages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not session_id or not user_id or not new_messages:
        return None
    _ensure_storage()
    uid = user_id.strip()
    sid = session_id.strip()
    now = _now_iso()
    sess = get_session(sid, uid)
    if sess is None:
        with get_memory_connection(autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (id, user_id, title, preview, created_at, updated_at)
                    VALUES (%s, %s, 'Phiên chat mới', '', %s::timestamptz, %s::timestamptz)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    (sid, uid, now, now),
                )
        sess = get_session(sid, uid) or {"id": sid, "user_id": uid, "title": "Phiên chat mới", "preview": ""}

    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            for msg in new_messages:
                cur.execute(
                    """
                    INSERT INTO chat_session_messages (session_id, user_id, payload)
                    VALUES (%s, %s, %s::jsonb);
                    """,
                    (sid, uid, json.dumps(msg, ensure_ascii=False)),
                )

            title = sess.get("title") or "Phiên chat mới"
            if title == "Phiên chat mới":
                for msg in new_messages:
                    if msg.get("role") == "user" and msg.get("content"):
                        text = str(msg["content"])
                        title = text[:32] + "…" if len(text) > 32 else text
                        break

            preview = sess.get("preview") or ""
            all_msgs = get_session_messages(sid, uid) or []
            for msg in reversed(all_msgs):
                if msg.get("role") == "assistant" and msg.get("content"):
                    preview = str(msg["content"]).replace("\n", " ").strip()
                    preview = preview[:45] + "…" if len(preview) > 45 else preview
                    break

            cur.execute(
                """
                UPDATE chat_sessions
                SET title = %s, preview = %s, updated_at = %s::timestamptz
                WHERE id = %s AND user_id = %s;
                """,
                (title, preview, now, sid, uid),
            )

    sess = get_session(sid, uid) or {}
    sess["messages"] = get_session_messages(sid, uid) or []
    sess["title"] = title
    sess["preview"] = preview
    sess["updated_at"] = now
    return sess


def update_session_meta(
    session_id: str,
    user_id: str,
    title: str | None = None,
    preview: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any] | None:
    if not session_id or not user_id:
        return None
    _ensure_storage()
    if get_session(session_id, user_id) is None:
        return None
    now = updated_at or _now_iso()
    with get_memory_connection(autocommit=True) as conn:
        with conn.cursor() as cur:
            if title is not None and preview is not None:
                cur.execute(
                    """
                    UPDATE chat_sessions SET title = %s, preview = %s, updated_at = %s::timestamptz
                    WHERE id = %s AND user_id = %s;
                    """,
                    (title, preview, now, session_id.strip(), user_id.strip()),
                )
            elif title is not None:
                cur.execute(
                    """
                    UPDATE chat_sessions SET title = %s, updated_at = %s::timestamptz
                    WHERE id = %s AND user_id = %s;
                    """,
                    (title, now, session_id.strip(), user_id.strip()),
                )
            elif preview is not None:
                cur.execute(
                    """
                    UPDATE chat_sessions SET preview = %s, updated_at = %s::timestamptz
                    WHERE id = %s AND user_id = %s;
                    """,
                    (preview, now, session_id.strip(), user_id.strip()),
                )
            else:
                cur.execute(
                    """
                    UPDATE chat_sessions SET updated_at = %s::timestamptz
                    WHERE id = %s AND user_id = %s;
                    """,
                    (now, session_id.strip(), user_id.strip()),
                )
    sess = get_session(session_id, user_id)
    if sess:
        sess["messages"] = get_session_messages(session_id, user_id) or []
    return sess


def ensure_session_storage() -> None:
    """Gọi lúc startup — DDL sessions + messages."""
    init_agent_storage()
