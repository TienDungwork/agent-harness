"""LLM gateway OpenAI-compatible — đọc /v1/models (id + limits)."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any

from src.shared.config import settings

logger = logging.getLogger(__name__)

_catalog_cache: dict[str, Any] | None = None
_catalog_cached_at: float = 0.0


def clear_gateway_catalog_cache() -> None:
    """Xóa cache catalog (dùng trong test hoặc sau khi gateway hồi phục)."""
    global _catalog_cache, _catalog_cached_at
    _catalog_cache = None
    _catalog_cached_at = 0.0


def _catalog_ttl_s() -> int:
    ttl = int(getattr(settings, "gateway_catalog_ttl_s", 300) or 300)
    return ttl if ttl > 0 else 300


def _auth_token() -> str:
    if settings.llm_backend == "self_hosted":
        return settings.model_api_key or ""
    return settings.llm_api_key or (settings.api_keys[0] if settings.api_keys else "")


def fetch_gateway_catalog() -> dict[str, Any]:
    """GET {MODEL_BASE_URL}/models — model ids và limits (theo schema gateway)."""
    global _catalog_cache, _catalog_cached_at
    if _catalog_cache is not None and (time.time() - _catalog_cached_at) < _catalog_ttl_s():
        return _catalog_cache

    base = (settings.model_base_url or settings.effective_base_url or "").rstrip("/")
    if not base:
        empty: dict[str, Any] = {"models": [], "limits": {}}
        _catalog_cache = empty
        _catalog_cached_at = time.time()
        return empty

    url = f"{base}/models"
    req = urllib.request.Request(url, method="GET")
    token = _auth_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=float(settings.llm_request_timeout_s or 10)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _catalog_cache = data
        _catalog_cached_at = time.time()
        return data
    except Exception as exc:
        logger.warning("Không đọc được gateway /models: %s", exc)
        return {"models": [], "limits": {}, "error": str(exc)}


def gateway_model_ids() -> list[str]:
    data = fetch_gateway_catalog()
    rows = data.get("data") or []
    return [str(m["id"]) for m in rows if isinstance(m, dict) and m.get("id")]


def gateway_limits() -> dict[str, Any]:
    return dict(fetch_gateway_catalog().get("limits") or {})


def gateway_max_output_tokens(default: int = 8192) -> int:
    lim = gateway_limits().get("max_output_tokens")
    if isinstance(lim, int) and lim > 0:
        return lim
    if isinstance(lim, float) and lim > 0:
        return int(lim)
    return default


def cap_output_tokens(requested: int | None) -> int | None:
    if requested is None:
        return None
    return min(requested, gateway_max_output_tokens())


def resolve_self_hosted_model(preferred: str | None = None) -> str:
    """Model id gửi lên /v1/chat/completions — ưu tiên env, khớp catalog gateway."""
    want = (preferred or settings.model_name or "").strip()
    ids = gateway_model_ids()
    if want and want in ids:
        return want
    if ids:
        if want and want not in ids:
            logger.warning("MODEL_NAME=%r không có trên gateway, dùng %r", want, ids[0])
        return ids[0]
    return want or "bonsai-27b"
