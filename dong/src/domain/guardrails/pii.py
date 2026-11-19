"""PII redaction — SĐT, email, CCCD/CMND."""

from __future__ import annotations

import re

_PHONE = re.compile(r"(?:\+84|84|0)(?:3|5|7|8|9)\d{8}\b|\b0\d{9,10}\b")
_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_ID_CARD = re.compile(r"\b(?:CCCD|CMND|ID|Số định danh)[:\s]*(\d{9}|\d{12})\b", re.IGNORECASE)


def redact_pii(text: str) -> str:
    """Che giấu thông tin cá nhân nhạy cảm (SĐT, Email, CCCD/CMND)."""
    if not text:
        return ""
    text = _PHONE.sub("[SĐT ẩn]", text)
    text = _EMAIL.sub("[email ẩn]", text)
    text = _ID_CARD.sub(lambda m: m.group(0).replace(m.group(1), "[CCCD ẩn]"), text)
    return text
