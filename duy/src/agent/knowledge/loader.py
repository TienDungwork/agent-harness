from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# duy/VMS_doc/VMS_documentation
_DOCS_ROOT = Path(__file__).resolve().parents[3] / "VMS_doc" / "VMS_documentation"
_INDEX = _DOCS_ROOT / "index.yaml"


@lru_cache
def docs_root() -> Path:
    return _DOCS_ROOT


@lru_cache
def load_index() -> dict[str, Any]:
    if not _INDEX.exists():
        raise FileNotFoundError(f"Không tìm thấy {_INDEX}")
    data = yaml.safe_load(_INDEX.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("index.yaml phải là object")
    return data


@lru_cache
def load_published_cards() -> tuple[dict, ...]:
    """Load card published; mỗi phần tử là dict đầy đủ từ file YAML."""
    index = load_index()
    include = set((index.get("ingestion") or {}).get("include_statuses") or ["published"])
    cards: list[dict] = []
    for meta in index.get("cards") or []:
        if not isinstance(meta, dict):
            continue
        status = str(meta.get("status") or "")
        if status not in include:
            continue
        rel = meta.get("file")
        if not rel:
            continue
        path = _DOCS_ROOT / str(rel)
        if not path.exists():
            continue
        body = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(body, dict):
            continue
        if str(body.get("status") or status) not in include:
            continue
        # Meta index bổ sung nếu body thiếu
        card = {**body}
        card.setdefault("id", meta.get("id"))
        card.setdefault("type", meta.get("type"))
        card.setdefault("title", meta.get("title"))
        card.setdefault("module", meta.get("module"))
        card["_file"] = str(rel)
        cards.append(card)
    return tuple(cards)


def clear_docs_cache() -> None:
    load_index.cache_clear()
    load_published_cards.cache_clear()
    docs_root.cache_clear()
