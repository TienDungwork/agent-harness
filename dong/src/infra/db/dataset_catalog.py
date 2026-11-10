"""Dataset catalog cho Golden-30 v2 cases và eval hints."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
import yaml
_DATASET_CATALOG_PATH = Path(__file__).resolve().parents[3] / 'resource' / 'db' / 'dataset_catalog.yaml'

@lru_cache(maxsize=1)
def load_dataset_catalog(path: Path | None=None) -> dict[str, Any]:
    """Đọc cấu hình dataset catalog từ file YAML."""
    p = path or _DATASET_CATALOG_PATH
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}

def get_case_hints(case_id: str) -> dict[str, Any]:
    """Lấy thông tin gợi ý (hints) cho một eval case theo case_id."""
    catalog = load_dataset_catalog()
    cases = (catalog['cases'] if 'cases' in catalog else None) or {}
    if isinstance(cases, dict):
        hint = cases[case_id] if case_id in cases else None
        if isinstance(hint, dict):
            return dict(hint)
    return {}

def get_table_for_keywords(question: str) -> str | None:
    """Tìm tên bảng phù hợp dựa trên keywords cấu hình trong dataset_catalog."""
    low = (question or '').lower()
    catalog = load_dataset_catalog()
    cases = (catalog['cases'] if 'cases' in catalog else None) or {}
    if not isinstance(cases, dict):
        return None
    for _, hint in cases.items():
        if not isinstance(hint, dict):
            continue
        table = hint['table'] if 'table' in hint else None
        if not table:
            continue
        keywords = (hint['keywords'] if 'keywords' in hint else None) or []
        for kw in keywords:
            if str(kw).lower() in low:
                return str(table)
    return None

def clear_dataset_catalog_cache() -> None:
    """Xóa cache bộ nhớ của dataset catalog."""
    load_dataset_catalog.cache_clear()
