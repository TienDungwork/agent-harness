"""Loader đọc YAML task cards VMS (index.yaml + cards published theo duy)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config import get_settings


def docs_root() -> Path:
    """Đường dẫn thư mục docs YAML VMS."""
    return get_settings().effective_docs_root


@lru_cache
def load_index(root_path: Path | None = None) -> dict[str, Any]:
    """Đọc file index.yaml từ thư mục docs."""
    root = root_path or docs_root()
    index_file = root / "index.yaml"
    if not index_file.exists():
        return {}
    try:
        data = yaml.safe_load(index_file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


@lru_cache
def load_published_cards(root_path: Path | None = None) -> tuple[dict[str, Any], ...]:
    """Load danh sách card published; mỗi phần tử là dict đầy đủ từ file YAML."""
    root = root_path or docs_root()
    index = load_index(root)
    if not index:
        return ()

    include = set((index.get("ingestion") or {}).get("include_statuses") or ["published"])
    cards: list[dict[str, Any]] = []

    for meta in index.get("cards") or []:
        if not isinstance(meta, dict):
            continue
        status = str(meta.get("status") or "")
        if status not in include:
            continue
        rel = meta.get("file")
        if not rel:
            continue
        path = root / str(rel)
        if not path.exists():
            continue
        try:
            body = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(body, dict):
            continue
        if str(body.get("status") or status) not in include:
            continue

        card = {**body}
        card.setdefault("id", meta.get("id"))
        card.setdefault("type", meta.get("type"))
        card.setdefault("title", meta.get("title"))
        card.setdefault("module", meta.get("module"))
        card["_file"] = str(rel)
        cards.append(card)

    return tuple(cards)


def clear_docs_cache() -> None:
    """Xóa cache bộ nhớ của loader (hỗ trợ tests hoặc reload runtime)."""
    load_index.cache_clear()
    load_published_cards.cache_clear()
