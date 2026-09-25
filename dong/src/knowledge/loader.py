"""Loader đọc YAML task cards VMS & AIOC (index.yaml + cards published)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config import get_settings


def docs_root() -> Path:
    """Đường dẫn thư mục docs YAML VMS."""
    return get_settings().effective_docs_root


def aioc_docs_root() -> Path:
    """Đường dẫn thư mục docs YAML AIOC."""
    project_root = Path(__file__).resolve().parent.parent.parent
    return (project_root / "resource" / "docs" / "aioc_yaml").resolve()


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
def _load_cards_from_root(root: Path) -> tuple[dict[str, Any], ...]:
    """Đọc toàn bộ cards published từ một thư mục root docs (có index.yaml)."""
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


@lru_cache
def load_vms_cards() -> tuple[dict[str, Any], ...]:
    """Load danh sách cards published từ thư mục docs VMS."""
    return _load_cards_from_root(docs_root())


@lru_cache
def load_aioc_cards() -> tuple[dict[str, Any], ...]:
    """Load danh sách cards published từ thư mục docs AIOC."""
    return _load_cards_from_root(aioc_docs_root())


@lru_cache
def load_published_cards(root_path: Path | None = None) -> tuple[dict[str, Any], ...]:
    """Load danh sách card published; mặc định merge cả VMS và AIOC cards."""
    if root_path is not None:
        return _load_cards_from_root(root_path)
    return tuple(list(load_vms_cards()) + list(load_aioc_cards()))


def clear_docs_cache() -> None:
    """Xóa cache bộ nhớ của loader (hỗ trợ tests hoặc reload runtime)."""
    load_index.cache_clear()
    _load_cards_from_root.cache_clear()
    load_vms_cards.cache_clear()
    load_aioc_cards.cache_clear()
    load_published_cards.cache_clear()
