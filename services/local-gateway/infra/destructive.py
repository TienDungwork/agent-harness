"""Detect destructive / sudo remote shell commands that must not auto-run."""

from __future__ import annotations

import re

# Patterns that must not run without confirm_destructive=true.
_DESTRUCTIVE_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r'(^|[;&|]\s*|\n)\s*rm\b', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*rmdir\b', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*unlink\b', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*shred\b', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*dd\b', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*mkfs(\.\w+)?\b', re.I),
    re.compile(r'\bfind\b[^;\n]*\s-delete\b', re.I),
    re.compile(r'\bgit\s+clean\b[^;\n]*-[^\s]*f', re.I),
    re.compile(r'(^|[;&|]\s*|\n)\s*truncate\b', re.I),
    re.compile(r'>\s*/', re.I),  # redirect overwrite toward absolute paths
)

# Host Add-Host password is SSH login only; interactive sudo always fails in this harness.
_SUDO_RE = re.compile(r'(^|[;&|]\s*|\n)\s*sudo\b', re.I)

SUDO_BLOCKED_MESSAGE = (
    'Đã vào máy rồi — đừng dùng sudo. Bạn muốn chạy lệnh gì (không sudo)?'
)


def looks_destructive(command: str) -> bool:
    text = command or ''
    if not text.strip():
        return False
    return any(p.search(text) for p in _DESTRUCTIVE_RES)


def destructive_reason(command: str) -> str | None:
    if not looks_destructive(command):
        return None
    return (
        'Command looks destructive (rm/dd/mkfs/find -delete/git clean -f/…). '
        'Ask the user, then retry with confirm_destructive=true.'
    )


def looks_like_sudo(command: str) -> bool:
    text = command or ''
    if not text.strip():
        return False
    return bool(_SUDO_RE.search(text))


def sudo_blocked_reason(command: str) -> str | None:
    if not looks_like_sudo(command):
        return None
    return SUDO_BLOCKED_MESSAGE
