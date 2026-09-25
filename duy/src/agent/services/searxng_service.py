from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from agent.config.settings import get_settings


def _clean_text(text: str, *, max_len: int = 320) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def format_web_excerpt(results: list[dict[str, Any]], *, max_items: int = 5) -> str:
    lines: list[str] = []
    for i, item in enumerate(results[:max_items], start=1):
        title = _clean_text(str(item.get("title") or "(không có tiêu đề)"), max_len=120)
        url = str(item.get("url") or "").strip()
        snippet = _clean_text(str(item.get("content") or item.get("snippet") or ""))
        lines.append(f"{i}. {title}\n   URL: {url}\n   Snippet: {snippet}")
    return "\n\n".join(lines)


def search_web(query: str, *, language: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    base = (settings.searxng_url or "").rstrip("/")
    if not base:
        raise RuntimeError("Chưa cấu hình SEARXNG_URL.")

    params: dict[str, str] = {
        "q": query.strip(),
        "format": "json",
    }
    lang = language or settings.searxng_language
    if lang:
        params["language"] = lang

    url = f"{base}/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DUY-Agent/0.1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.searxng_timeout_seconds) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"SearXNG HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Không kết nối SearXNG: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("SearXNG trả về JSON không hợp lệ.") from exc

    raw_results = payload.get("results") if isinstance(payload, dict) else []
    results: list[dict[str, Any]] = []
    if isinstance(raw_results, list):
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url_val = str(item.get("url") or "").strip()
            if not url_val:
                continue
            results.append(
                {
                    "title": str(item.get("title") or "").strip(),
                    "url": url_val,
                    "content": str(item.get("content") or "").strip(),
                    "engine": str(item.get("engine") or "").strip(),
                }
            )

    return {
        "query": query.strip(),
        "result_count": len(results),
        "results": results[: settings.searxng_max_results],
    }
