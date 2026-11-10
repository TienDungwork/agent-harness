"""IAM HTTP client — login + GET /api/v1/auth/me (B2B)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from src.shared.config import settings

logger = logging.getLogger(__name__)


class IamError(Exception):
    """Lỗi gọi IAM."""

    def __init__(self, message: str, *, status_code: int=502):
        super().__init__(message)
        self.status_code = status_code


def _iam_base() -> str:
    base = (settings.iam_base_url or '').rstrip('/')
    if not base:
        raise IamError('IAM_BASE_URL chưa cấu hình', status_code=503)
    return base


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode('utf-8', errors='replace')[:200]
    except Exception:
        return ''


def login(username: str, password: str, *, remember: bool=True) -> dict[str, Any]:
    """POST IAM /auth/login → JSON có access_token."""
    url = f'{_iam_base()}/api/v1/auth/login'
    payload = json.dumps({'username': username, 'password': password, 'remember': remember}).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    timeout = float(settings.iam_timeout_s or 5.0)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode() or '{}')
            if not isinstance(data, dict) or 'access_token' not in data or not data['access_token']:
                raise IamError('IAM login thiếu access_token', status_code=502)
            return data
    except urllib.error.HTTPError as exc:
        body = _read_http_error(exc)
        if exc.code in (401, 403):
            raise IamError('Sai tên đăng nhập hoặc mật khẩu', status_code=exc.code) from exc
        raise IamError(f'IAM login HTTP {exc.code}: {body}', status_code=502) from exc
    except urllib.error.URLError as exc:
        raise IamError(f'Không kết nối được IAM: {exc}', status_code=503) from exc
    except TimeoutError as exc:
        raise IamError('IAM timeout', status_code=503) from exc


def fetch_auth_me(token: str) -> dict[str, Any]:
    """Gọi IAM /auth/me với Bearer token; trả JSON user_ctx."""
    url = f'{_iam_base()}/api/v1/auth/me'
    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/json')
    timeout = float(settings.iam_timeout_s or 5.0)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise IamError('IAM trả về payload không hợp lệ', status_code=502)
            return data
    except urllib.error.HTTPError as exc:
        body = _read_http_error(exc)
        if exc.code in (401, 403):
            raise IamError(f'IAM từ chối token ({exc.code})', status_code=exc.code) from exc
        raise IamError(f'IAM HTTP {exc.code}: {body}', status_code=502) from exc
    except urllib.error.URLError as exc:
        raise IamError(f'Không kết nối được IAM: {exc}', status_code=503) from exc
    except TimeoutError as exc:
        raise IamError('IAM timeout', status_code=503) from exc
