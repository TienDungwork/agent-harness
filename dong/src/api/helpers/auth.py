"""Optional API access key — bảo vệ /api/* khi API_ACCESS_KEY được set."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from src.shared.config import settings

_PUBLIC_API_SUFFIXES = ("/api/health", "/api/llm/ping")


def api_access_required(request: Request) -> JSONResponse | None:
    """Trả về 401 JSONResponse nếu thiếu/sai key; None nếu cho qua."""
    path = request.url.path
    if not path.startswith("/api/"):
        return None
    if any(path == p or path.rstrip("/") == p for p in _PUBLIC_API_SUFFIXES):
        return None

    expected = (settings.api_access_key or "").strip()
    if not expected:
        return None

    provided = (request.headers.get("x-api-key") or "").strip()
    if provided != expected:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing X-API-Key"})
    return None
