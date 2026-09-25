"""In-memory Session Store for agent dong v6."""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any
import uuid

_lock = threading.Lock()
# Structure: {user_id: {session_id: session_dict}}
_SESSIONS_STORE: dict[str, dict[str, dict[str, Any]]] = {}


def _now_iso() -> str:
    """Trả về timestamp hiện tại dạng chuẩn ISO8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def clear_sessions_store() -> None:
    """Xóa sạch session store phục vụ unit tests và resets."""
    with _lock:
        _SESSIONS_STORE.clear()


def list_sessions(user_id: str) -> list[dict[str, Any]]:
    """Liệt kê danh sách phiên chat của user_id, sắp xếp theo updated_at giảm dần."""
    if not user_id:
        return []
    with _lock:
        user_sessions = _SESSIONS_STORE.get(user_id, {})
        sessions = [dict(s) for s in user_sessions.values()]
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def create_session(user_id: str, title: str | None = None) -> dict[str, Any]:
    """Tạo phiên chat mới cho user_id."""
    if not user_id or not user_id.strip():
        raise ValueError("user_id is required")
    now = _now_iso()
    session_id = str(uuid.uuid4())
    session_data: dict[str, Any] = {
        "id": session_id,
        "user_id": user_id.strip(),
        "title": title.strip() if (title and title.strip()) else "Phiên chat mới",
        "preview": "",
        "messages": [],
        "updated_at": now,
        "created_at": now,
    }
    with _lock:
        if user_id.strip() not in _SESSIONS_STORE:
            _SESSIONS_STORE[user_id.strip()] = {}
        _SESSIONS_STORE[user_id.strip()][session_id] = session_data
        return dict(session_data)


def get_session(session_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    """Lấy thông tin phiên chat theo session_id (và tuỳ chọn user_id)."""
    if not session_id:
        return None
    with _lock:
        if user_id:
            sess = _SESSIONS_STORE.get(user_id, {}).get(session_id)
            return dict(sess) if sess else None
        for _u_id, sessions in _SESSIONS_STORE.items():
            if session_id in sessions:
                return dict(sessions[session_id])
    return None


def delete_session(session_id: str, user_id: str) -> bool:
    """Xóa phiên chat theo session_id và user_id.
    
    Trả về True nếu tìm thấy và xóa thành công, False nếu không tồn tại hoặc sai user_id.
    """
    if not session_id or not user_id:
        return False
    with _lock:
        user_sessions = _SESSIONS_STORE.get(user_id)
        if user_sessions is not None and session_id in user_sessions:
            del user_sessions[session_id]
            return True
    return False


def get_session_messages(session_id: str, user_id: str) -> list[dict[str, Any]] | None:
    """Lấy lịch sử tin nhắn của phiên; None nếu session không tồn tại."""
    sess = get_session(session_id, user_id)
    if not sess:
        return None
    messages = sess.get("messages")
    if not isinstance(messages, list):
        return []
    return [dict(m) for m in messages]


def append_session_messages(
    session_id: str,
    user_id: str,
    new_messages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Append tin nhắn vào phiên; cập nhật preview/title khi cần."""
    if not session_id or not user_id or not new_messages:
        return None
    with _lock:
        user_sessions = _SESSIONS_STORE.get(user_id)
        if not user_sessions or session_id not in user_sessions:
            return None
        sess = user_sessions[session_id]
        if not isinstance(sess.get("messages"), list):
            sess["messages"] = []
        sess["messages"].extend(new_messages)
        now = _now_iso()
        sess["updated_at"] = now

        if sess.get("title") == "Phiên chat mới":
            for msg in new_messages:
                if msg.get("role") == "user" and msg.get("content"):
                    text = str(msg["content"])
                    sess["title"] = text[:32] + "…" if len(text) > 32 else text
                    break

        for msg in reversed(sess["messages"]):
            if msg.get("role") == "assistant" and msg.get("content"):
                preview = str(msg["content"]).replace("\n", " ").strip()
                sess["preview"] = preview[:45] + "…" if len(preview) > 45 else preview
                break

        return dict(sess)


def update_session_meta(
    session_id: str,
    user_id: str,
    title: str | None = None,
    preview: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any] | None:
    """Cập nhật tiêu đề hoặc preview hoặc updated_at của session."""
    if not session_id or not user_id:
        return None
    with _lock:
        user_sessions = _SESSIONS_STORE.get(user_id)
        if not user_sessions or session_id not in user_sessions:
            return None
        sess = user_sessions[session_id]
        if title is not None:
            sess["title"] = title
        if preview is not None:
            sess["preview"] = preview
        sess["updated_at"] = updated_at or _now_iso()
        return dict(sess)
