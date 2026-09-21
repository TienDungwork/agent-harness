from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_CATALOG = Path(__file__).with_name("datasets.yaml")
_STOP = {
    "có", "bao", "nhiêu", "nào", "trong", "của", "và", "the", "a", "an", "là",
    "đang", "cho", "tôi", "những", "các", "một", "ngày",
}

# Cụm tiếng Việt / nghiệp vụ — giữ nguyên, không tách (tránh "ô tô" → "tô").
_PHRASES = sorted(
    [
        "ô tô",
        "xe máy",
        "xe tải",
        "xe buýt",
        "xe hơi",
        "biển số",
        "biển số xe",
        "phương tiện",
        "camera phương tiện",
        "camera biển số",
        "camera xe",
        "đang hoạt động",
        "bất thường",
        "khuôn mặt",
        "chấm công",
        "ra vào",
        "license plate",
        "smart face",
        "virtual fence",
    ],
    key=len,
    reverse=True,
)

# Ép domain trước khi chấm điểm alias — tránh "ra vào" kéo sang face khi hỏi xe.
_DOMAIN_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"ô\s*tô|o\s*to|xe\s*máy|xe\s*đạp|xe\s*tải|xe\s*buýt|xe\s*hơi|"
            r"biển\s*số|phương\s*tiện|alpr|license\s*plate|"
            r"\bcar\b|\bcars\b|\bmotorcycle\b|\bmotorcycles\b|"
            r"\btruck\b|\bbus\b|\bvehicle\b|vehicle_type|"
            r"camera\s+(?:phương\s*tiện|biển\s*số|xe)\b",
            re.IGNORECASE,
        ),
        "its.plate_events",
    ),
    (
        re.compile(
            r"vi\s*phạm\s*giao\s*thông|phạt\s*nguội|vượt\s*đèn|"
            r"plate_violation|\bviolation\b",
            re.IGNORECASE,
        ),
        "its.plate_violations",
    ),
    (
        re.compile(r"khuôn\s*mặt|\bface\b|chấm\s*công|smart\s*face", re.IGNORECASE),
        "smart_face.events",
    ),
    (
        re.compile(r"bất\s*thường|\banomaly\b|xâm\s*nhập|loitering|lảng\s*vảng", re.IGNORECASE),
        "anomaly.events",
    ),
]


@lru_cache
def load_datasets() -> list[dict]:
    data = yaml.safe_load(_CATALOG.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError("datasets.yaml phải là list")
    return data


def force_dataset_id(question: str) -> str | None:
    q = question or ""
    for pattern, dataset_id in _DOMAIN_RULES:
        if pattern.search(q):
            return dataset_id
    return None


def retrieve_datasets(question: str, limit: int = 4) -> list[dict]:
    forced_id = force_dataset_id(question)
    if forced_id:
        forced = next((ds for ds in load_datasets() if ds.get("id") == forced_id), None)
        if forced is not None:
            return [forced][:limit]

    q = (question or "").lower()
    scored: list[tuple[int, dict]] = []
    for ds in load_datasets():
        hay = " ".join(
            [
                str(ds.get("id", "")),
                str(ds.get("name", "")),
                str(ds.get("description", "")),
                str(ds.get("database", "")),
                str(ds.get("table", "")),
                " ".join(str(a) for a in ds.get("aliases") or []),
            ]
        ).lower()
        aliases = [str(a).lower() for a in ds.get("aliases") or []]
        score = 0
        for alias in aliases:
            a = alias.strip()
            if a and a in q:
                score += 10 if " " in a or len(a) >= 4 else 6
        for token in _tokens(q):
            if not token:
                continue
            if token in aliases or any(a == token for a in aliases):
                score += 6
            elif any(token in a.split() for a in aliases):
                score += 2
            elif token in hay:
                score += 1
        if score:
            scored.append((score, ds))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    if not scored:
        return [ds for ds in load_datasets() if ds.get("id") in {"vms.cameras", "vms.ai_events"}][:limit]
    top_score, top_ds = scored[0]
    top_db = top_ds.get("database")
    min_score = max(1.0, top_score * 0.5)
    picked: list[dict] = []
    for score, ds in scored:
        if ds.get("database") != top_db:
            continue
        if score < min_score:
            continue
        picked.append(ds)
        if len(picked) >= limit:
            break
    return picked or [top_ds]


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
    # Ưu tiên cụm dài hơn khi chồng nhau.
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


def _word_tokens(text: str) -> list[str]:
    return [
        t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if len(t) >= 2 and t not in _STOP
    ]
