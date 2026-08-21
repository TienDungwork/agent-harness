"""Detect destructive remote shell commands that require explicit confirmation."""

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
