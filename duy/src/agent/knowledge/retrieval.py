from __future__ import annotations

import re
from typing import Any

from agent.knowledge.loader import load_published_cards

_STOP = {
    "có", "bao", "nhiêu", "nào", "trong", "của", "và", "the", "a", "an", "là",
    "đang", "cho", "tôi", "những", "các", "một", "làm", "sao", "thế", "nào",
    "cách", "hướng", "dẫn", "giúp",
}

_PHRASES = sorted(
    [
        "thêm camera",
        "xóa camera",
        "sửa camera",
        "đăng nhập",
        "đăng xuất",
        "xem live",
        "trực tiếp",
        "playback",
        "phát lại",
        "biển số",
        "khuôn mặt",
        "chấm công",
        "không xem được live",
        "camera bị đen",
        "đổi mật khẩu",
        "đặt lại mật khẩu",
        "xe máy",
        "ô tô",
        "xem bao nhiêu",
        "số lượng xe",
        "làm thế nào để xem",
    ],
    key=len,
    reverse=True,
)


def _word_tokens(text: str) -> list[str]:
    return [
        t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if len(t) >= 2 and t not in _STOP
    ]


def _tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    spans: list[tuple[int, int, str]] = []
    for phrase in _PHRASES:
        start = 0
        while True:
            i = lowered.find(phrase, start)
            if i < 0:
                break
            spans.append((i, i + len(phrase), phrase))
            start = i + len(phrase)
    spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
    chosen: list[tuple[int, int, str]] = []
    occupied = [False] * (len(lowered) + 1)
    for a, b, phrase in spans:
        if any(occupied[a:b]):
            continue
        for i in range(a, b):
            occupied[i] = True
        chosen.append((a, b, phrase))
    chosen.sort(key=lambda s: s[0])
    tokens: list[str] = []
    cursor = 0
    for a, b, phrase in chosen:
        tokens.extend(_word_tokens(lowered[cursor:a]))
        tokens.append(phrase)
        cursor = b
    tokens.extend(_word_tokens(lowered[cursor:]))
    return tokens


def retrieve_docs(question: str, *, limit: int = 2, prefer_type: str | None = None) -> list[dict[str, Any]]:
    q = (question or "").lower()
    scored: list[tuple[int, dict]] = []
    for card in load_published_cards():
        if prefer_type and str(card.get("type") or "") != prefer_type:
            # Vẫn cho điểm nhưng thấp hơn nếu type lệch.
            type_penalty = 3
        else:
            type_penalty = 0

        aliases = [str(a).lower() for a in (card.get("aliases") or [])]
        tags = [str(t).lower() for t in (card.get("tags") or [])]
        hay = " ".join(
            [
                str(card.get("id") or ""),
                str(card.get("title") or ""),
                str(card.get("intent") or ""),
                str(card.get("summary") or ""),
                str(card.get("module") or ""),
                " ".join(aliases),
                " ".join(tags),
            ]
        ).lower()

        score = 0
        for alias in aliases:
            a = alias.strip()
            if not a:
                continue
            if a in q:
                score += 14 if " " in a or len(a) >= 6 else 10
        title = str(card.get("title") or "").lower()
        if title and title in q:
            score += 12

        for token in _tokens(q):
            if token in aliases:
                score += 8
            elif any(token in a.split() for a in aliases):
                score += 3
            elif token in tags:
                score += 4
            elif token in hay:
                score += 1

        score -= type_penalty
        if score > 0:
            scored.append((score, card))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
    return [c for _, c in scored[:limit]]


def card_excerpt_for_llm(card: dict[str, Any]) -> dict[str, Any]:
    """Rút gọn card trước khi gửi LLM."""
    steps = []
    for step in card.get("steps") or []:
        if not isinstance(step, dict):
            continue
        item = {"order": step.get("order"), "say": step.get("say")}
        ui = step.get("ui") or {}
        if isinstance(ui, dict) and ui.get("label"):
            item["ui_label"] = ui.get("label")
        steps.append(item)

    checks = []
    for chk in card.get("checks") or []:
        if not isinstance(chk, dict):
            continue
        checks.append(
            {
                "order": chk.get("order"),
                "if": chk.get("if"),
                "then": chk.get("then"),
                "stop_when": chk.get("stop_when"),
            }
        )

    return {
        "id": card.get("id"),
        "type": card.get("type"),
        "title": card.get("title"),
        "module": card.get("module"),
        "route": card.get("route"),
        "menu_path": card.get("menu_path"),
        "preconditions": card.get("preconditions"),
        "summary": card.get("summary"),
        "symptoms": card.get("symptoms"),
        "steps": steps or None,
        "checks": checks or None,
    }
