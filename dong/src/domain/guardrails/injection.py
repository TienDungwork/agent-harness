"""Prompt injection + toxic content detection (regex, no LLM)."""

from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore (?:all |previous |above |prior )*(?:instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard (?:all |previous |above |prior )*(?:instructions|rules|prompts)", re.IGNORECASE),
    re.compile(r"bỏ qua (?:mọi |tất cả |các )*(?:hướng dẫn|chỉ dẫn|quy tắc|chỉ thị)", re.IGNORECASE),
    re.compile(r"quên (?:hết |mọi |tất cả |các )*(?:hướng dẫn|chỉ dẫn|quy tắc|lệnh trước)", re.IGNORECASE),
    re.compile(r"(?:reveal|dump|show|print|leak|get|output|display).*(?:system |developer )?(?:prompt|instructions|rules)", re.IGNORECASE),
    re.compile(r"(?:tiết lộ|in ra|hiển thị|cho xem|xem|xuất).*(?:system prompt|prompt hệ thống|chỉ dẫn hệ thống|hướng dẫn ban đầu)", re.IGNORECASE),
    re.compile(r"you are now (?:a|an|in) ", re.IGNORECASE),
    re.compile(r"act as (?:if you|a|an) ", re.IGNORECASE),
    re.compile(r"đóng vai (?:là|như|một) ", re.IGNORECASE),
    re.compile(r"(?:từ giờ|bây giờ) bạn là ", re.IGNORECASE),
    re.compile(r"\b(?:jailbreak|dan mode|developer mode enabled)\b", re.IGNORECASE),
    re.compile(r"bypass (?:all |safety |guardrail|security )*(?:filters|rules|checks)", re.IGNORECASE),
]

_TOXIC_WORDS = frozenset({"đụ", "địt", "đéo", "fuck", "shit", "cút", "óc chó", "dm", "dcm", "vcl"})

INJECTION_REJECT_MESSAGE = (
    "Không thể xử lý yêu cầu này vì có dấu hiệu tấn công prompt injection "
    "(cố gắng bỏ qua hướng dẫn hệ thống). "
    "Hãy đặt câu hỏi trực tiếp về thống kê camera VMS, hướng dẫn AIOC hoặc biểu đồ sự kiện."
)

TOXIC_REJECT_MESSAGE = (
    "Không thể xử lý yêu cầu vì có từ ngữ không phù hợp. "
    "Vui lòng đặt câu hỏi lịch sự về giám sát camera KCN Hưng Phú."
)


def detect_prompt_injection(text: str) -> bool:
    return any(p.search(text or "") for p in _INJECTION_PATTERNS)


def detect_toxicity(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _TOXIC_WORDS)
